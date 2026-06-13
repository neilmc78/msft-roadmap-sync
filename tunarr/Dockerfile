FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY static/ ./static/

ENV TUNARR_DATA_DIR=/config
ENV TUNARR_MUSIC_DIR=/music

VOLUME ["/config", "/music"]
EXPOSE 8686

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8686"]
