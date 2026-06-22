FROM python:3.11-slim-bookworm

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

WORKDIR /opt/promotion

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY twitter_to_telegram_promotion.py .
COPY lib/ ./lib/

COPY aws/fargate/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PROMOTION_MOUNT=/promotion

ENTRYPOINT ["/entrypoint.sh"]
