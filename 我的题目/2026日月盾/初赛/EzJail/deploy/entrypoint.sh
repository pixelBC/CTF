#!/bin/sh
set -e

# 题目附件保持只读：选手可读、可探索，但不能篡改
chown -R root:root /opt/challenge
find /opt/challenge -type d -exec chmod 555 {} +
find /opt/challenge -type f -exec chmod 444 {} +

# 可选：把平台注入的 flag 写进容器（默认关闭）。
# 本题会给选手一个 Shell，容器内的 flag 文件会被直接读到，
# 因此只有确实需要时才设置 EZJAIL_INJECT_FLAG=1 打开。
if [ "${EZJAIL_INJECT_FLAG:-0}" = "1" ] && [ -n "${GZCTF_FLAG:-}" ]; then
    printf '%s' "$GZCTF_FLAG" > /flag
    chown root:root /flag
    chmod 400 /flag
fi

mkdir -p /home/player/work
chown -R player:player /home/player
cd /home/player
exec python3 -u /opt/ezjail/server.py
