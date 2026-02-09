FROM alpine:3.20

RUN apk add --no-cache \
    bash curl jq tzdata \
    postgresql16-client \
    samba-client \
    ca-certificates coreutils tar gzip

# supercronic = tiny cron runner for containers
ADD https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY backup.sh /app/backup.sh
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/*.sh

ENV TZ=Asia/Jerusalem
ENTRYPOINT ["/app/entrypoint.sh"]
