"""Independent GitHub ETL: python -m src.scripts.run_github_pipeline."""
from src.scripts.run_pipeline import main as run_pipeline


def main(argv=None):
    return run_pipeline(argv, fixed_pipeline="github")


if __name__ == "__main__":
    main()
