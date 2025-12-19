# /home/sonthl/setup/docker/media-lite/Dockerfile

FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN apt-get update && apt-get install -y ffmpeg && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN chmod +x start.sh

CMD ["./start.sh"]