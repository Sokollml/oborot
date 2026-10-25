# Этап 1: сборка React-приложения.
# Debian (slim), а не alpine: npm в alpine не ставит musl-сборки нативных пакетов (lightningcss, rolldown).
FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY . .
RUN npm run build

# Этап 2: раздача статики через nginx (он же проксирует /api на бэкенд).
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
