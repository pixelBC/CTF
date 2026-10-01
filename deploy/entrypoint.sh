#!/bin/sh
set -e
printf '%s' "${GZCTF_FLAG:-flag{set_GZCTF_FLAG_env}}" > /app/flag.txt
exec python3 -u /app/1.py
