# 多阶段：node 构建前端 → nginx 托管产物
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
# 使用国内 npm 镜像（服务器在国内，直连 npmjs.org 慢/不稳）
RUN npm config set registry https://registry.npmmirror.com && npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx-web.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
