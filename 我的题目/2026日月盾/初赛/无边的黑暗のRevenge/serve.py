"""无边的黑暗のRevenge —— nc 投递端

连接后先说一句「无边的黑暗!!!」，隔一下就甩一句假报错
「[*] Got EOF while reading in interactive」（坑：让人以为服务挂了而提前断开，
其实连接还好好的），静默到 DELAY 秒（默认 30，从连接时刻算起），
再发「在持之以恒地努力下，」+「你窥到了黑暗的本质」并紧跟一行 Data URL，然后断开。

环境变量：
  PORT      监听端口（默认 10001）
  HOST      监听地址（默认 0.0.0.0）
  DELAY     从连接算起的送达秒数（默认 30）
  EOF_LINE  坑位文本（默认 [*] Got EOF while reading in interactive；置空可关闭）
  EOF_DELAY 问候语到坑位之间的间隔秒数（默认 1）
  URL_FILE  Data URL 文件（默认 url.txt；每次连接都重新读，可热替换）
  BANNER    连上时的问候语（默认 无边的黑暗!!!）
  PRELUDE   引语前的那一句（默认 在持之以恒地努力下，；置空可关闭）
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
EOF_LINE = os.environ.get('EOF_LINE', '[*] Got EOF while reading in interactive')
EOF_DELAY = float(os.environ.get('EOF_DELAY', '1'))
URL_FILE = os.environ.get('URL_FILE', 'url.txt')
BANNER = os.environ.get('BANNER', '无边的黑暗!!!')
PRELUDE = os.environ.get('PRELUDE', '在持之以恒地努力下，')
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
        t0 = time.time()
        conn.sendall((BANNER + '\n\n').encode())
        if EOF_LINE:
            time.sleep(EOF_DELAY)
            conn.sendall((EOF_LINE + '\n').encode())        # 坑：假报错（行尾不带空行）
        log('连接 %s：已问候%s，等 %.0f 秒' % (peer, ' + 假 EOF' if EOF_LINE else '', DELAY))
        time.sleep(max(0.0, DELAY - (time.time() - t0)))     # DELAY 从连接时刻算起
        url = load_url()
        head = [PRELUDE, LEAD] if PRELUDE else [LEAD]
        body = '\n'.join(head + [url or '（附件还未就位）']) + '\n'
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
    log('监听 %s:%d（%.0f 秒后送达，坑位=%s，URL 文件 %s）'
        % (HOST, PORT, DELAY, '开' if EOF_LINE else '关', URL_FILE))
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
