# syntax=docker/dockerfile:1
# READY ROOM frontend — build the SPA, serve it with nginx, reverse-proxy /api.
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY tsconfig.json tsconfig.node.json vite.config.ts vitest.config.ts index.html ./
COPY src ./src

RUN npm run build

# --- runtime ---------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# nginx must listen on IPv4 and IPv6 (see nginx.conf). Health check targets
# 127.0.0.1 explicitly, not "localhost".
EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
