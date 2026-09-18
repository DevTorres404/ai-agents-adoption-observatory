"""Independent hackernews ETL with the shared processing contract."""
from src.scripts.run_pipeline import main as run_pipeline


def main(argv=None):
    return run_pipeline(argv, fixed_pipeline="hackernews")


if __name__ == "__main__":
    main()
