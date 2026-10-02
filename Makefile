.PHONY: install test dev-api dev-web simulate docker clean

install:
	pip install -r backend/requirements-dev.txt
	cd frontend && npm install

test:
	cd backend && python -m pytest

dev-api:
	cd backend && uvicorn app.main:app --reload

dev-web:
	cd frontend && npm run dev

simulate:
	cd backend && python -m app.evaluation.simulate --games 20 --provider mock

docker:
	docker compose up --build

clean:
	rm -rf frontend/dist frontend/node_modules backend/.pytest_cache simulation-report.json
	find backend -type d -name __pycache__ -exec rm -rf {} +
