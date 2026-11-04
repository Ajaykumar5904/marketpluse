FROM nginx:1.27-alpine
COPY src/ /usr/share/nginx/html/
COPY config.js.template /usr/share/nginx/html/config.js.template
COPY docker-entrypoint.sh /docker-entrypoint.d/40-marketpulse-config.sh
RUN chmod +x /docker-entrypoint.d/40-marketpulse-config.sh
EXPOSE 80
