# -*- coding: utf-8 -*-
"""EzJail 单条输入字节上限与连接行为测试。

开发机直接运行（无需 Docker / Linux）：
    "E:\\Python 3.13\\python.exe" -m unittest discover -s tests -v
"""
import os
import socket
import sys
import tempfile
import threading
import time
import unittest

os.environ.setdefault("EZJAIL_SHELL", sys.executable)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sandbox"))

from command_policy import CommandPolicy, denied_command  # noqa: E402
from session import BufferOverflow, LineReader, Session  # noqa: E402

MAX = 128
HARD_CAP = 64 * 1024


class FakeSock:
    """确定性喂数据的假 socket，用来单测字节级读取逻辑。"""

    def __init__(self, data, chunk=4096):
        self.buf = bytearray(data)
        self.chunk = chunk

    def recv(self, n):
        if not self.buf:
            return b""
        take = min(n, self.chunk, len(self.buf))
        out = bytes(self.buf[:take])
        del self.buf[:take]
        return out


def reader_for(data, max_bytes=MAX, chunk=4096):
    return LineReader(FakeSock(data, chunk), max_bytes,
                      buffer_hard_cap=HARD_CAP, recv_size=4096)


class LineLimitTest(unittest.TestCase):
    def test_one_byte_line(self):
        self.assertEqual(reader_for(b"x\n").read_event(), ("line", b"x"))

    def test_exactly_max_bytes_accepted(self):
        kind, payload = reader_for(b"A" * MAX + b"\n").read_event()
        self.assertEqual(kind, "line")
        self.assertEqual(len(payload), MAX)

    def test_max_plus_one_rejected(self):
        self.assertEqual(reader_for(b"A" * (MAX + 1) + b"\n").read_event(),
                         ("too_long", None))

    def test_lf_and_crlf_both_terminate(self):
        reader = reader_for(b"one\ntwo\r\n")
        self.assertEqual(reader.read_event(), ("line", b"one"))
        self.assertEqual(reader.read_event(), ("line", b"two"))

    def test_crlf_not_counted_towards_limit(self):
        kind, payload = reader_for(b"A" * MAX + b"\r\n").read_event()
        self.assertEqual(kind, "line")
        self.assertEqual(payload, b"A" * MAX)

    def test_empty_lines(self):
        reader = reader_for(b"\n\nhello\n")
        self.assertEqual(reader.read_event(), ("line", b""))
        self.assertEqual(reader.read_event(), ("line", b""))
        self.assertEqual(reader.read_event(), ("line", b"hello"))

    def test_line_split_across_chunks(self):
        reader = reader_for(b"A" * 80 + b"B" * 40 + b"\n", chunk=7)
        self.assertEqual(reader.read_event(), ("line", b"A" * 80 + b"B" * 40))

    def test_overlong_line_does_not_leak_tail(self):
        reader = reader_for(b"A" * 300 + b"\nnext\n")
        self.assertEqual(reader.read_event(), ("too_long", None))
        self.assertEqual(reader.read_event(), ("line", b"next"))

    def test_eof_on_partial_line(self):
        self.assertEqual(reader_for(b"partial").read_event(), ("eof", None))

    def test_eof_on_closed_socket(self):
        self.assertEqual(reader_for(b"").read_event(), ("eof", None))

    def test_unterminated_flood_hits_hard_cap(self):
        with self.assertRaises(BufferOverflow):
            reader_for(b"A" * (1 << 20)).read_event()

    def test_buffer_stays_bounded(self):
        reader = reader_for(b"A" * (1 << 20))
        with self.assertRaises(BufferOverflow):
            reader.read_event()
        self.assertLessEqual(len(reader._buf), HARD_CAP + 4096)


class CommandPolicyTest(unittest.TestCase):
    def test_denylist(self):
        self.assertEqual(denied_command("sudo ls"), "sudo")
        self.assertEqual(denied_command("ls | sudo cat"), "sudo")
        self.assertEqual(denied_command("cat /opt/challenge/challenge.py"), "cat")
        self.assertEqual(denied_command("find / -name x"), "find")
        self.assertEqual(denied_command("help"), "help")
        self.assertIsNone(denied_command("ls -la /opt/challenge"))
        self.assertIsNone(
            denied_command("sed -n '1,60p' /opt/challenge/challenge.py"))

    def test_streams_output(self):
        out = bytearray()
        with tempfile.TemporaryDirectory() as tmp:
            status, _ = CommandPolicy().run('print("hello")', cwd=tmp,
                                            on_output=out.extend, timeout=30)
        self.assertEqual(status, "ok")
        self.assertIn(b"hello", bytes(out))

    def test_timeout_kills_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, _ = CommandPolicy().run(
                "import time; time.sleep(30)", cwd=tmp,
                on_output=lambda _: None, timeout=2)
        self.assertEqual(status, "timeout")

    def test_output_limit_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, _ = CommandPolicy().run(
                'print("x" * 200000)', cwd=tmp,
                on_output=lambda _: None, output_limit=1000, timeout=30)
        self.assertEqual(status, "output_limit")


class SessionHarness:
    """在 socketpair 上跑一个真实会话，用于端到端验证交互行为。"""

    def __init__(self, cwd, max_line_bytes=MAX):
        self.client, server_side = socket.socketpair()
        self.server_side = server_side
        session = Session(server_side, policy=CommandPolicy(), home=cwd, cwd=cwd,
                          max_line_bytes=max_line_bytes, buffer_hard_cap=HARD_CAP,
                          idle_timeout=30, command_timeout=30, output_limit=65536)

        def target():
            try:
                session.run()
            finally:
                try:
                    server_side.close()
                except OSError:
                    pass

        self.thread = threading.Thread(target=target, daemon=True)
        self.thread.start()

    def send(self, data):
        self.client.sendall(data)

    def drain(self, until=None, timeout=20):
        self.client.settimeout(0.2)
        buf = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = self.client.recv(65536)
            except socket.timeout:
                if until is None and buf:
                    break
                continue
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            if until and until in buf:
                break
        return buf

    def close(self):
        try:
            self.client.close()
        except OSError:
            pass
        self.thread.join(timeout=5)
        try:
            self.server_side.close()
        except OSError:
            pass


def python_line(body_bytes):
    """构造长度为 9 + body_bytes 的合法 Python 单行命令。"""
    return b'print("' + b"A" * body_bytes + b'")'


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.harness = SessionHarness(self.tmp.name)
        self.harness.drain(until=b"$")

    def tearDown(self):
        self.harness.close()
        self.tmp.cleanup()

    def test_banner_and_simple_command(self):
        self.harness.send(b'print("hello-ezjail")\n')
        self.assertIn(b"hello-ezjail", self.harness.drain(until=b"hello-ezjail"))

    def test_exactly_max_bytes_is_executed(self):
        self.assertEqual(len(python_line(MAX - 9)), MAX)
        self.harness.send(python_line(MAX - 9) + b"\n")
        self.assertIn(b"A" * 32, self.harness.drain(until=b"AAAAAA"))

    def test_max_plus_one_is_rejected_then_next_command_runs(self):
        line = python_line(MAX + 1 - 9)
        self.assertEqual(len(line), MAX + 1)
        self.harness.send(line + b"\n")
        self.assertIn("整条丢弃".encode(), self.harness.drain(until="整条丢弃".encode()))
        self.harness.send(b'print("after-overlong")\n')
        self.assertIn(b"after-overlong", self.harness.drain(until=b"after-overlong"))

    def test_overlong_tail_is_not_executed(self):
        self.harness.send(b"A" * 292 + b'print("BOOM")' + b"\n")
        out = self.harness.drain(until="整条丢弃".encode())
        self.assertNotIn(b"BOOM", out)
        self.harness.send(b'print("still-alive")\n')
        self.assertIn(b"still-alive", self.harness.drain(until=b"still-alive"))

    def test_crlf_terminated_command(self):
        self.harness.send(b'print("crlf-ok")\r\n')
        self.assertIn(b"crlf-ok", self.harness.drain(until=b"crlf-ok"))

    def test_empty_line_then_command(self):
        self.harness.send(b"\n")
        self.harness.drain()
        self.harness.send(b'print("after-empty")\n')
        self.assertIn(b"after-empty", self.harness.drain(until=b"after-empty"))

    def test_multiple_commands_in_one_send(self):
        self.harness.send(b'print("one")\nprint("two")\n')
        out = self.harness.drain(until=b"two")
        self.assertIn(b"one", out)
        self.assertIn(b"two", out)

    def test_help_is_blocked_and_exit(self):
        self.harness.send(b"help\n")
        out = self.harness.drain(until="策略禁止".encode())
        self.assertIn(b"help", out)
        self.assertNotIn(b"cd <dir>", out)
        self.harness.send(b"exit\n")
        self.assertIn(b"bye", self.harness.drain(until=b"bye"))

    def test_cd_changes_prompt(self):
        os.makedirs(os.path.join(self.tmp.name, "sub"), exist_ok=True)
        self.harness.send(b"cd sub\n")
        self.assertIn(b"sub$", self.harness.drain(until=b"sub$"))

    def test_disconnect_ends_session(self):
        self.harness.client.close()
        self.harness.thread.join(timeout=5)
        self.assertFalse(self.harness.thread.is_alive())


if __name__ == "__main__":
    unittest.main(verbosity=2)
