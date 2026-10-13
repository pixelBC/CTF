# -*- coding: utf-8 -*-
"""EzJail 命令执行策略：粗粒度黑名单 + 资源限制 + 超时 + 输出上限。

注意：本模块不是安全边界。真正的隔离依赖容器权限、能力集、资源限制与网络策略；
这里只做进程级约束，保证单条命令不会拖垮容器，并挡掉明显的越权指令。
"""
import os
import re
import signal
import subprocess
import threading

try:
    import resource
except ImportError:  # 开发机（Windows）没有 resource，仅用于本地跑测试
    resource = None

SHELL = os.environ.get("EZJAIL_SHELL", "/bin/bash")

DENY = {
    "sudo", "su", "doas", "mount", "umount", "chroot", "nsenter", "unshare",
    "docker", "podman", "systemctl", "service", "passwd", "useradd", "usermod",
    "groupadd", "reboot", "shutdown", "poweroff", "init", "insmod", "modprobe",
    "iptables", "ip6tables", "nft", "apt", "apt-get", "dpkg","cat","echo","find",
}

_SEGMENT = re.compile(r"[|;&\n]")
_HEAD = re.compile(r"[A-Za-z0-9_./+-]+")


def denied_command(line):
    """返回被禁止的命令名，没有则返回 None（粗粒度：只看每段的首个 token）。"""
    for segment in _SEGMENT.split(line):
        segment = segment.strip()
        if not segment:
            continue
        match = _HEAD.match(segment)
        if not match:
            continue
        name = os.path.basename(match.group(0))
        if name in DENY:
            return name
    return None


def build_env(cwd):
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin",
        "HOME": os.environ.get("EZJAIL_HOME", "/home/player"),
        "PWD": cwd,
        "USER": os.environ.get("EZJAIL_USER", "player"),
        "LOGNAME": os.environ.get("EZJAIL_USER", "player"),
        "SHELL": SHELL,
        "TERM": "dumb",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PAGER": "cat",
        "GIT_PAGER": "cat",
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _preexec(cpu_seconds, addr_space, max_procs, file_size):
    def _apply():
        os.setsid()
        if resource is None:
            return
        for what, limit in (
            (resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 2)),
            (resource.RLIMIT_AS, (addr_space, addr_space)),
            (resource.RLIMIT_NPROC, (max_procs, max_procs)),
            (resource.RLIMIT_FSIZE, (file_size, file_size)),
            (resource.RLIMIT_CORE, (0, 0)),
        ):
            try:
                resource.setrlimit(what, limit)
            except (ValueError, OSError):
                pass
    return _apply


class CommandPolicy:
    """把一条命令行交给受限 shell 执行，并把输出流式回传给会话。"""

    def __init__(self, cpu_seconds=10, addr_space=1 << 30, max_procs=64,
                 file_size=64 << 20):
        self.cpu_seconds = cpu_seconds
        self.addr_space = addr_space
        self.max_procs = max_procs
        self.file_size = file_size

    def run(self, line, cwd, on_output, timeout=60, output_limit=256 * 1024):
        denied = denied_command(line)
        if denied:
            return "denied", denied
        preexec = None
        if os.name == "posix":
            preexec = _preexec(self.cpu_seconds, self.addr_space,
                               self.max_procs, self.file_size)
        try:
            proc = subprocess.Popen(
                [SHELL, "-c", line],
                cwd=cwd,
                env=build_env(cwd),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=preexec,
                close_fds=True,
            )
        except FileNotFoundError:
            return "error", "%s 不存在" % SHELL
        except OSError as exc:
            return "error", str(exc)
        return self._pump(proc, on_output, timeout, output_limit)

    def _pump(self, proc, on_output, timeout, output_limit):
        fd = proc.stdout.fileno()
        state = {"total": 0, "status": "ok", "pending": bytearray()}
        lock = threading.Lock()

        def flush():
            with lock:
                if state["pending"]:
                    on_output(bytes(state["pending"]))
                    state["pending"].clear()

        def reader():
            while True:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                with lock:
                    state["total"] += len(chunk)
                    overflow = state["total"] > output_limit
                    if overflow:
                        keep = len(chunk) - (state["total"] - output_limit)
                        state["pending"] += chunk[:keep] if keep > 0 else b""
                        state["status"] = "output_limit"
                    else:
                        state["pending"] += chunk
                if overflow:
                    self._kill(proc)
                    break
                if len(state["pending"]) >= 4096:
                    flush()

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._kill(proc)
            with lock:
                if state["status"] == "ok":
                    state["status"] = "timeout"
            proc.wait()
        thread.join(timeout=3)
        flush()
        try:
            proc.stdout.close()
        except OSError:
            pass
        return state["status"], None

    @staticmethod
    def _kill(proc):
        if hasattr(os, "killpg"):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
                return
            except (ProcessLookupError, PermissionError, OSError):
                pass
        try:
            proc.kill()
        except OSError:
            pass
