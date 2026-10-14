#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EzJail 交互入口：自定义 TCP 会话服务器（不把宿主机 Bash 直接交给选手）。

- 每个连接 fork 一个子进程独立处理，会话之间互不影响；
- 以 root 启动时先降权到普通用户 player，再监听端口（LCX 内选手没有 root）；
- 单条输入字节上限由 session.LineReader 在服务端强制执行，先校验后执行。
"""
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from command_policy import CommandPolicy  # noqa: E402
from session import Session  # noqa: E402

LISTEN_HOST = os.environ.get("EZJAIL_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("EZJAIL_PORT", "10001"))
PLAYER_USER = os.environ.get("EZJAIL_USER", "player")
PLAYER_HOME = os.environ.get("EZJAIL_HOME", "/home/player")
MAX_LINE_BYTES = int(os.environ.get("MAX_LINE_BYTES", "12"))
BUFFER_HARD_CAP = int(os.environ.get("EZJAIL_BUFFER_CAP", str(64 * 1024)))
IDLE_TIMEOUT = int(os.environ.get("EZJAIL_IDLE_TIMEOUT", "600"))
COMMAND_TIMEOUT = int(os.environ.get("EZJAIL_COMMAND_TIMEOUT", "60"))
OUTPUT_LIMIT = int(os.environ.get("EZJAIL_OUTPUT_LIMIT", str(256 * 1024)))
MAX_CHILDREN = int(os.environ.get("EZJAIL_MAX_CHILDREN", "32"))


def drop_privileges():
    """以 root 启动时降权到普通用户，之后所有会话都以该身份运行。"""
    if os.geteuid() != 0:
        return
    import pwd
    try:
        info = pwd.getpwnam(PLAYER_USER)
    except KeyError:
        sys.stderr.write("user %s not found; keep current uid\n" % PLAYER_USER)
        return
    os.setgroups([])
    os.setgid(info.pw_gid)
    os.setuid(info.pw_uid)


def serve(conn):
    try:
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    session = Session(
        conn, policy=CommandPolicy(), home=PLAYER_HOME,
        max_line_bytes=MAX_LINE_BYTES, buffer_hard_cap=BUFFER_HARD_CAP,
        idle_timeout=IDLE_TIMEOUT, command_timeout=COMMAND_TIMEOUT,
        output_limit=OUTPUT_LIMIT)
    try:
        session.run()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass


def main():
    if not hasattr(os, "fork"):
        sys.stderr.write("server.py requires a POSIX host (fork/setuid)\n")
        return 1
    drop_privileges()
    try:
        os.makedirs(os.path.join(PLAYER_HOME, "work"), exist_ok=True)
        os.chdir(PLAYER_HOME)
    except OSError:
        pass

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(64)

    children = set()
    while True:
        conn, _ = server.accept()
        if len(children) >= MAX_CHILDREN:
            try:
                conn.sendall(b"[!] too many sessions, try later\n")
            except OSError:
                pass
            conn.close()
            continue
        pid = os.fork()
        if pid == 0:
            server.close()
            serve(conn)
            os._exit(0)
        conn.close()
        children.add(pid)
        while True:
            try:
                done, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                children.clear()
                break
            if done == 0:
                break
            children.discard(done)


if __name__ == "__main__":
    sys.exit(main())
