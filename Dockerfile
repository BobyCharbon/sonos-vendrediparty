FROM node:22.23.3-alpine AS events-web
WORKDIR /web/events
COPY web/events/package.json web/events/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/events/ ./
RUN npm run typecheck && npm run lint && npm run build

FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY --from=events-web /web/events/dist ./app/events-web
ENV DATA_DIR=/data PORT=8000
# Section Événements : 1 sur l'image de test (develop), 0 en production (main).
ARG EVENTS_ENABLED=0
ENV EVENTS_ENABLED=${EVENTS_ENABLED}
ENV FORWARDED_ALLOW_IPS=127.0.0.1,192.168.50.1
VOLUME /data
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
