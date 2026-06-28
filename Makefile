.PHONY: db-up install extract load-raw staging quality run

# Levantar PostgreSQL
db-up:
	docker-compose up -d

# Instalar dependencias
install:
	python -m venv .venv
	.venv/Scripts/pip install -r requirements.txt

# Comandos individuales por fase
extract:
	.venv/Scripts/python -m src.extractors.github_api

load-raw:
	.venv/Scripts/python -m src.loaders.load_raw_to_db

staging:
	.venv/Scripts/python -m src.staging.stg_build_unified

quality:
	.venv/Scripts/python -m src.quality.quality_metrics

# Orquestador Maestro
run:
	.venv/Scripts/python -m src.scripts.run_pipeline
