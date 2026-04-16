FROM golang:1.25.5-alpine AS build

WORKDIR /app

COPY go.mod go.sum* ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /bin/compliance-engine ./cmd/server

FROM alpine:3.20

WORKDIR /app
RUN adduser -D runner && apk add --no-cache wget

COPY --from=build /bin/compliance-engine /usr/local/bin/compliance-engine

USER runner
EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/compliance-engine"]
