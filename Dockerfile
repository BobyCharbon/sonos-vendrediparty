FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV DATA_DIR=/data PORT=8000
# Reverse proxy de confiance (HAProxy sur pfSense) : sa X-Forwarded-For donne la vraie IP des invités.
# Surchargeable par la variable d'environnement de la stack.
ENV FORWARDED_ALLOW_IPS=127.0.0.1,192.168.50.1
VOLUME /data
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
