#!/bin/sh
set -e
FLAG="${GZCTF_FLAG:-flag{set_GZCTF_FLAG_env}}"
printf '%s' "$FLAG" > /app/flag.txt
cd /app
exec socat TCP-LISTEN:10001,reuseaddr,fork EXEC:"python3 -u /app/1.py"
