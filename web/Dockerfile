FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
ARG LOOKOVER_API_BASE_URL=http://go-api:8080
ENV LOOKOVER_API_BASE_URL=$LOOKOVER_API_BASE_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ARG LOOKOVER_API_BASE_URL=http://go-api:8080
ENV LOOKOVER_API_BASE_URL=$LOOKOVER_API_BASE_URL
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/public ./public
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
EXPOSE 3000
CMD ["npm", "run", "start"]
