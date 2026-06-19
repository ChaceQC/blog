FROM node:24-alpine AS frontend-build

WORKDIR /workspace/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY deploy/nginx/nginx.conf /etc/nginx/nginx.conf
COPY deploy/nginx/templates /etc/nginx/templates
COPY --from=frontend-build /workspace/frontend/dist /usr/share/nginx/html

RUN mkdir -p /var/www/certbot
