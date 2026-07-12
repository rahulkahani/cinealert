.PHONY: help build run stop purge test-alert logs doctor

help:
	@echo Available targets:
	@echo build       Build the Docker image
	@echo run         Build if needed and run the application
	@echo stop        Stop the application
	@echo purge       Stop and remove all containers
	@echo test-alert  Send a test alert through every configured channel
	@echo logs        Tail the watcher log
	@echo doctor      Diagnose a container/UI that is not responding

test-alert:
	docker-compose run --rm cinealert python /app/main.py --test-alert

logs:
	tail -f logs/main.log

doctor:
	@echo "--- container state (should say Up) ---"
	@docker-compose ps || true
	@echo "--- web UI log ---"
	@tail -n 20 logs/webui.log 2>/dev/null || echo "(no logs/webui.log — the running image predates the UI: run 'make stop build run')"
	@echo "--- watcher log ---"
	@tail -n 10 logs/main.log 2>/dev/null || echo "(no logs/main.log yet)"
	@echo "--- UI reachability from this machine ---"
	@curl -s -o /dev/null -w "http://localhost:8080 -> HTTP %{http_code}\n" --max-time 5 http://localhost:8080/ \
		|| echo "not reachable on localhost:8080 (container down, old image, or you are on a different machine — use the docker host's IP)"

build:
	docker-compose build

# building first is cheap (layer cache) and prevents running a stale image
run: build
	docker-compose up -d

stop:
	docker-compose down

purge:
	docker-compose kill
	docker-compose rm
