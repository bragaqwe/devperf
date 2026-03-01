.PHONY: up down rebuild logs ps reset-seed

up:
	docker-compose up -d

down:
	docker-compose down

rebuild:
	docker-compose down
	docker-compose build --no-cache backend
	docker-compose up -d
	docker-compose logs -f backend

rebuild-all:
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

logs:
	docker-compose logs -f backend

ps:
	docker-compose ps

# Сбрасывает seed-данные: удаляет raw-таблицы и перезапускает бэкенд
reset-seed:
	docker-compose exec db psql -U devperf -d devperf -c "\
	  TRUNCATE jira_transitions, jira_issues, \
	           github_reviews, github_comments, \
	           github_pull_requests, github_commits, \
	           daily_metrics, performance_scores CASCADE;"
	docker-compose restart backend
