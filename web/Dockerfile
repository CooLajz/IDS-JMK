FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.28-alpine
ENV API_UPSTREAM=http://api:8080 NGINX_ENVSUBST_FILTER=API_UPSTREAM
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
COPY LICENSE /usr/share/nginx/html/LICENSE
LABEL org.opencontainers.image.source="https://github.com/CooLajz/IDS-JMK" \
      org.opencontainers.image.licenses="MIT"
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
