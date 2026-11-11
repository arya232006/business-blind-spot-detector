PY ?= .venv/bin/python

.PHONY: setup sample test demo api ui docker-up
setup:            ## create venv (Python 3.10-3.12) and install dependencies
	python3.11 -m venv .venv && $(PY) -m pip install -r requirements.txt
sample:           ## regenerate the synthetic NovaCart CSVs
	$(PY) data/generate_sample_data.py
test:             ## run the unit tests (offline)
	$(PY) -m pytest -q
demo:             ## run the full pipeline on the demo data in the terminal
	$(PY) scripts/run_demo.py
api:              ## FastAPI backend on :8000 (docs at /docs)
	$(PY) -m uvicorn backend.main:app --reload --port 8000
ui:               ## Streamlit dashboard on :8501
	$(PY) -m streamlit run frontend/app.py
docker-up:        ## PostgreSQL + API + dashboard
	docker compose up --build
