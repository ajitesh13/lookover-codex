PROJECT_ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

.PHONY: up down backend web python fmt

up:
	WEB_PORT=$${WEB_PORT:-3000} docker compose up --build

down:
	docker compose down -v

backend:
	cd backend && go run ./cmd/server

web:
	cd web && PORT=$${WEB_PORT:-3000} npm run dev

python:
	cd python && python3 -m prerun.cli --help

fmt:
	cd backend && gofmt -w $$(find . -name '*.go')
