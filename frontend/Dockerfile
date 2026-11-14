FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.29-alpine
# The image's entrypoint fills the template from these at start-up (see nginx.conf.template).
ENV BACKEND_URL=http://backend:8000 \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1 \
    NGINX_ENVSUBST_FILTER="^(BACKEND_URL|NGINX_LOCAL_RESOLVERS)$"
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --chmod=755 docker-entrypoint.d/16-check-proxy.envsh /docker-entrypoint.d/
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
