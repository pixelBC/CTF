# -*- coding: utf-8 -*-
"""EzJail 会话层：服务端按字节读取单条输入并执行允许的命令。

单行上限只按“命令正文”计算，不含行结束符（LF 或 CRLF）；
超长输入整条丢弃（绝不截断后执行），并丢弃该行的剩余字节直到行结束。
"""
import os
import socket

from command_policy import CommandPolicy

BANNER = """
  EzJail
  每条输入最多 {max_bytes} 字节
  输入 exit 断开连接。
"""


class BufferOverflow(Exception):
    """未遇到换行就超出缓冲区硬上限，直接断开，避免内存被占满。"""


class LineReader:
    """在字节层面读取输入行，并在服务端强制执行单行字节上限。"""

    def __init__(self, sock, max_line_bytes, buffer_hard_cap=64 * 1024, recv_size=4096):
        self.sock = sock
        self.max_line_bytes = max_line_bytes
        self.buffer_hard_cap = buffer_hard_cap
        self.recv_size = recv_size
        self._buf = bytearray()

    def read_event(self):
        """返回 (kind, payload)：('line', bytes) / ('too_long', None) / ('eof', None)。"""
        while True:
            nl = self._buf.find(b"\n")
            if nl != -1:
                raw = bytes(self._buf[:nl])
                del self._buf[:nl + 1]
                if raw.endswith(b"\r"):  # CRLF 的行结束符不计入长度上限
                    raw = raw[:-1]
                if len(raw) > self.max_line_bytes:
                    return "too_long", None
                return "line", raw
            if len(self._buf) > self.buffer_hard_cap:
                raise BufferOverflow("line buffer exceeded %d bytes" % self.buffer_hard_cap)
            chunk = self.sock.recv(self.recv_size)
            if not chunk:
                return "eof", None
            self._buf += chunk


class Session:
    """一次 nc 连接的完整会话：提示符、内建指令、单条命令执行。"""

    def __init__(self, conn, policy=None, home="/home/player", cwd=None,
                 max_line_bytes=30, buffer_hard_cap=64 * 1024, idle_timeout=600,
                 command_timeout=60, output_limit=256 * 1024):
        self.conn = conn
        self.policy = policy or CommandPolicy()
        self.home = home
        self.cwd = cwd or home
        self.max_line_bytes = max_line_bytes
        self.reader = LineReader(conn, max_line_bytes, buffer_hard_cap)
        self.idle_timeout = idle_timeout
        self.command_timeout = command_timeout
        self.output_limit = output_limit

    def send(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8", "replace")
        if not data:
            return 0
        self.conn.sendall(data)
        return len(data)

    def prompt(self):
        path = self.cwd
        if path == self.home:
            path = "~"
        elif path.startswith(self.home + "/"):
            path = "~" + path[len(self.home):]
        return "\nplayer@ezjail:%s$ " % path

    def run(self):
        self.send(BANNER.format(max_bytes=self.max_line_bytes))
        while True:
            self.conn.settimeout(self.idle_timeout)
            self.send(self.prompt())
            try:
                kind, payload = self.reader.read_event()
            except BufferOverflow:
                self.send("\n[!] 输入缓冲区超限，连接已关闭。\n")
                return
            except socket.timeout:
                self.send("\n[!] 会话空闲超时，连接已关闭。\n")
                return
            except OSError:
                return
            if kind == "eof":
                return
            if kind == "too_long":
                self.send("[!] 单条命令最多 %d 字节，本条输入已整条丢弃。\n"
                          % self.max_line_bytes)
                continue

            line = payload.decode("utf-8", "replace").strip()
            if not line:
                continue
            if line in ("exit", "quit"):
                self.send("bye\n")
                return
            if line == "cd" or line.startswith("cd ") or line.startswith("cd\t"):
                self.send(self.change_dir(line))
                continue

            status, detail = self.policy.run(
                line, cwd=self.cwd, on_output=self.send,
                timeout=self.command_timeout, output_limit=self.output_limit)
            if status == "timeout":
                self.send("\n[!] 命令执行超时（%ds），已终止。\n" % self.command_timeout)
            elif status == "output_limit":
                self.send("\n[!] 输出超过上限，已截断并终止。\n")
            elif status == "denied":
                self.send("[!] 指令被策略禁止：%s\n" % detail)
            elif status == "error":
                self.send("[!] 执行失败：%s\n" % detail)

    def change_dir(self, line):
        parts = line.split(None, 1)
        target = parts[1].strip() if len(parts) > 1 else ""
        if target in ("", "~"):
            target = self.home
        elif target == "-":
            target = self.home
        elif target.startswith("~/"):
            target = os.path.join(self.home, target[2:])
        elif not target.startswith("/"):
            target = os.path.join(self.cwd, target)
        target = os.path.realpath(target)
        if not os.path.isdir(target):
            return "cd: %s: 目录不存在\n" % target
        self.cwd = target
        return ""
