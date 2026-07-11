.PHONY: help build run stop purge test-alert logs

help:
	@echo Available targets:
	@echo build       Build the Docker image
	@echo run         Run the application
	@echo stop        Stop the application
	@echo purge       Stop and remove all containers
	@echo test-alert  Send a test alert through every configured channel
	@echo logs        Tail the watcher log

test-alert:
	docker-compose run --rm cinealert python /app/main.py --test-alert

logs:
	tail -f logs/main.log

build:
	docker-compose build

run:
	docker-compose up -d

stop:
	docker-compose down

purge:
	docker-compose kill
	docker-compose rm
