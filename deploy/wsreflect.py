"""把平台代理给出的 wss:// 地址映射成本地 TCP 端口，供 nc / pwntools 直连。

用法:
    python wsreflect.py <wss地址> [本地端口]
例:
    python wsreflect.py wss://c404ctf.jellyspot.cc/api/proxy/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx 10001
然后另开一个终端:
    nc 127.0.0.1 10001
"""
import base64
import os
import socket
import ssl
import struct
import sys
import threading
from urllib.parse import urlparse

OPCODE_BIN = 0x2
OPCODE_CLOSE = 0x8
OPCODE_PING = 0x9
OPCODE_PONG = 0xA


def send_frame(sock, opcode, data):
    length = len(data)
    header = bytearray([0x80 | opcode])
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header += struct.pack(">H", length)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", length)
    mask = os.urandom(4)
    header += mask
    sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))


class WebSocket:
    def __init__(self, url):
        parts = urlparse(url)
        host = parts.hostname
        port = parts.port or (443 if parts.scheme == "wss" else 80)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query

        sock = socket.create_connection((host, port))
        if parts.scheme == "wss":
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)

        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall((
            f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode())

        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocket 握手失败：连接被关闭")
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise ConnectionError("WebSocket 握手失败：" + head.decode(errors="replace"))

        self.sock = sock
        self.buf = bytearray(rest)

    def _take(self, count):
        while len(self.buf) < count:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("连接已关闭")
            self.buf += chunk
        out = bytes(self.buf[:count])
        del self.buf[:count]
        return out

    def recv(self):
        payload = b""
        while True:
            first, second = self._take(2)
            fin, opcode = first & 0x80, first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._take(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._take(8))[0]
            mask = self._take(4) if second & 0x80 else None
            data = self._take(length)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == OPCODE_CLOSE:
                raise ConnectionError("对端关闭了连接")
            if opcode == OPCODE_PING:
                send_frame(self.sock, OPCODE_PONG, data)
                continue
            if opcode == OPCODE_PONG:
                continue
            payload += data
            if fin:
                return payload

    def send(self, data):
        send_frame(self.sock, OPCODE_BIN, data)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def local_to_ws(local, ws):
    try:
        while True:
            data = local.recv(4096)
            if not data:
                break
            ws.send(data)
    except (OSError, ConnectionError):
        pass
    finally:
        ws.close()


def ws_to_local(ws, local):
    try:
        while True:
            local.sendall(ws.recv())
    except (OSError, ConnectionError):
        pass
    finally:
        try:
            local.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        local.close()


def serve(ws_url, port):
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", port))
    listener.listen(16)
    print(f"[*] 本地 127.0.0.1:{port}  ->  {ws_url}", flush=True)
    print(f"[*] 把脚本/工具指向 127.0.0.1:{port} 即可", flush=True)
    while True:
        local, addr = listener.accept()
        try:
            ws = WebSocket(ws_url)
        except Exception as exc:
            print(f"[!] 连接平台失败: {exc}", flush=True)
            local.close()
            continue
        print(f"[+] {addr[0]}:{addr[1]} 已接入", flush=True)
        threading.Thread(target=local_to_ws, args=(local, ws), daemon=True).start()
        threading.Thread(target=ws_to_local, args=(ws, local), daemon=True).start()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    serve(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10001)