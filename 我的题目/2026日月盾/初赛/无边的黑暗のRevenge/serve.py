"""无边的黑暗のRevenge —— nc 投递端

连接后先说一句「无边的黑暗!!!」，静默 DELAY 秒（默认 30），
再发「你窥到了黑暗的本质」并紧跟一行 Data URL，然后断开。

环境变量：
  PORT      监听端口（默认 10001）
  HOST      监听地址（默认 0.0.0.0）
  DELAY     连接后静默秒数（默认 30）
  URL_FILE  Data URL 文件（默认 url.txt；每次连接都重新读，可热替换）
  BANNER    连上时的问候语（默认 无边的黑暗!!!）
  LEAD      发送 URL 前的引语（默认 你窥到了黑暗的本质）
本机调试：python serve.py
"""
import os
import socket
import sys
import threading
import time

HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', '10001'))
DELAY = float(os.environ.get('DELAY', '30'))
URL_FILE = os.environ.get('URL_FILE', 'url.txt')
BANNER = os.environ.get('BANNER', '无边的黑暗!!!')
LEAD = os.environ.get('LEAD', '你窥到了黑暗的本质')


def log(msg):
    print(time.strftime('[%H:%M:%S] ') + msg, flush=True)


def load_url():
    """读 Data URL；文件缺失时返回 None（不把连接卡死）"""
    try:
        with open(URL_FILE, encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def handle(conn, addr):
    peer = '%s:%s' % addr
    try:
        conn.sendall((BANNER + '\n\n').encode())
        log('连接 %s：已问候，静默 %.0f 秒' % (peer, DELAY))
        time.sleep(DELAY)
        url = load_url()
        body = '%s\n%s\n' % (LEAD, url) if url else '%s\n（附件还未就位）\n' % LEAD
        conn.sendall(body.encode())
        log('向 %s 发送完毕（%d 字节%s）' % (peer, len(body), '' if url else '，URL 文件缺失'))
        time.sleep(0.3)
    except (BrokenPipeError, ConnectionResetError) as e:
        log('%s 提前断开：%s' % (peer, e))
    except OSError as e:
        log('%s 出错：%s' % (peer, e))
    finally:
        conn.close()


def main():
    if load_url() is None:
        log('警告：%s 不存在，客户端连上后拿不到 Data URL' % URL_FILE)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(64)
    log('监听 %s:%d（静默 %.0f 秒，URL 文件 %s）' % (HOST, PORT, DELAY, URL_FILE))
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
