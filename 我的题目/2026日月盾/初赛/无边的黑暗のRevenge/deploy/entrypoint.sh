#!/bin/sh
set -e
cd /app
# 纯标准库的 TCP 服务：连上问候 -> 静默 30 秒 -> 发引语 + 一行 Data URL
exec python3 -u /app/serve.py
