FROM node:24-slim AS dev
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV API_URL=http://api:8000
CMD ["npm", "run", "dev"]

FROM dev AS build
RUN npm run build

FROM nginx:1.30.6-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
