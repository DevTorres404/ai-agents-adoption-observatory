.PHONY: install extract load-raw staging quality run run-github extract-github

VENV := ../.venv/Scripts/python

install:
	python -m venv ../.venv
	$(VENV) -m pip install -r requirements.txt

extract:
	PYTHONPATH=. $(VENV) -m src.scripts.run_pipeline --phase extract

extract-github:
	PYTHONPATH=. $(VENV) -m src.scripts.run_github_pipeline --phase extract

load-raw:
	PYTHONPATH=. $(VENV) -m src.loaders.load_raw_to_db

staging:
	PYTHONPATH=. $(VENV) -m src.staging.stg_build_unified

quality:
	PYTHONPATH=. $(VENV) -m src.quality.quality_metrics

run:
	PYTHONPATH=. $(VENV) -m src.scripts.run_pipeline

run-github:
	PYTHONPATH=. $(VENV) -m src.scripts.run_github_pipeline
