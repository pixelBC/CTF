#!/bin/sh
set -e
printf '%s' 'C404{yyyy@@@eee~~~~FasT!!!}' > /app/flag.txt
cd /app
exec socat TCP-LISTEN:10001,reuseaddr,fork EXEC:"python3 -u /app/1.py"
