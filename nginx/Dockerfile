FROM nginx:1.25-alpine

RUN rm /etc/nginx/conf.d/default.conf

# Create self-signed cert as fallback (so nginx can start before real cert exists)
RUN apk add --no-cache openssl && \
    mkdir -p /etc/letsencrypt/live/ngon-ngon.com && \
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
      -keyout /etc/letsencrypt/live/ngon-ngon.com/privkey.pem \
      -out /etc/letsencrypt/live/ngon-ngon.com/fullchain.pem \
      -subj '/CN=localhost' 2>/dev/null && \
    apk del openssl

HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget -q --spider http://localhost/health || exit 1

EXPOSE 80 443
