FROM python:3.13-slim

WORKDIR /app

COPY serve.py /app/serve.py
COPY ["data url.txt", "/app/url.txt"]
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod 755 /app/entrypoint.sh

ENV PORT=10001 DELAY=30 URL_FILE=url.txt

EXPOSE 10001
CMD ["/app/entrypoint.sh"]
