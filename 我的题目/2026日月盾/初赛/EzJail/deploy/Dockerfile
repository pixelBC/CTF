FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    MAX_LINE_BYTES=256 \
    EZJAIL_PORT=10001

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        coreutils findutils file grep sed gawk procps binutils bsdextrautils passwd \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir pycryptodome \
    && useradd -m -u 1000 -s /bin/bash player

COPY sandbox/ /opt/ezjail/
COPY challenge/challenge.py /opt/challenge/challenge.py
COPY challenge/challenge2.py /srv/backup/challenge2.py
COPY deploy/entrypoint.sh /usr/local/bin/ezjail-entrypoint
RUN chmod 755 /usr/local/bin/ezjail-entrypoint \
    && mkdir -p /home/player/work \
    && chown -R player:player /home/player

EXPOSE 10001
ENTRYPOINT ["/usr/local/bin/ezjail-entrypoint"]
