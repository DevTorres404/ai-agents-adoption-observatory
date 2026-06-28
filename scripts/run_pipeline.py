"""Compatibility wrapper for the current Entregable 3 pipeline.

The reproducible orchestrator lives in src.scripts.run_pipeline.
This file is kept only so older commands such as `python scripts/run_pipeline.py`
continue to execute the same validated flow used by the Makefile and README.
"""

from src.scripts.run_pipeline import main


if __name__ == "__main__":
    main()
