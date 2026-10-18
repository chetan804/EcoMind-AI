# Frontend image. Build context: repository root.
#   dev        Vite dev server (used by compose.yaml)
#   production static build served by nginx (independently deployable)
#     docker build -f deployment/docker/frontend.Dockerfile --target production \
#       --build-arg VITE_API_BASE_URL=https://api.example.org -t ecomind-frontend .
FROM node:22-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM deps AS dev
COPY frontend/ ./
EXPOSE 5173
CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "5173"]

FROM deps AS build
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
COPY frontend/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine AS production
COPY deployment/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
