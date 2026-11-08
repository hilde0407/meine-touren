# Meine Touren als Container:  docker compose up -d   (siehe README, Abschnitt „Docker“)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data PHOTOS_DIR=/fotos MT_DOCKER=1 TZ=Europe/Berlin

RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends tzdata ca-certificates curl gosu \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/meine-touren
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY deploy ./deploy
COPY README.md LICENSE ./

# Daten im Volume /data. Der Start-Skript passt die Besitzrechte an und läuft danach ohne Root-Rechte
# (Benutzer PUID:PGID, Vorgabe 1000:1000 – bei TrueNAS z. B. 568:568).
RUN mkdir -p /data /fotos
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD curl -fsS http://127.0.0.1:8080/api/version || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
