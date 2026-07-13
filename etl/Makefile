.PHONY: install extract load-raw staging quality run

VENV := ../.venv/Scripts/python

install:
	python -m venv ../.venv
	$(VENV) -m pip install -r requirements.txt

extract:
	PYTHONPATH=. $(VENV) -m src.extractors.github

load-raw:
	PYTHONPATH=. $(VENV) -m src.loaders.load_raw_to_db

staging:
	PYTHONPATH=. $(VENV) -m src.staging.stg_build_unified

quality:
	PYTHONPATH=. $(VENV) -m src.quality.quality_metrics

run:
	PYTHONPATH=. $(VENV) -m src.scripts.run_pipeline
