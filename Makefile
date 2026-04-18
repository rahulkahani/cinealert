.PHONY: build run stop purge logs

build:
	docker compose build

run:
	docker compose up -d

stop:
	docker compose down

purge:
	docker compose down --rmi all --volumes

logs:
	docker compose logs -f
