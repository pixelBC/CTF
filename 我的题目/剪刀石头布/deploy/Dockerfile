FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir pycryptodome pwntools

COPY 1.py /app/1.py
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod 755 /app/entrypoint.sh

EXPOSE 10001
CMD ["/app/entrypoint.sh"]
