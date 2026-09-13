from src.quality.quality_metrics import run_quality_framework


if __name__ == "__main__":
    from src.scripts.run_pipeline import main
    main(["--phase", "quality"])
