import json
from pathlib import Path

import pandas as pd
import pytest

from src.extractors import aidedev
from src.scripts.prepare_aidedev_datasets import FILES, prepare_replacement
from src.staging.stg_normalize_columns import normalize_dataframe
from src.utils.extraction_evidence import EvidenceRun, evidence_context


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    # No body columns: the extractor must only read analytical projections.
    prs = pd.DataFrame([
        dict(id=1, title="One", agent="Google_Jules", user_id=7, repo_id=None,
             repo_url="https://api.github.com/repos/org/repo", html_url="https://github.com/org/repo/pull/1",
             created_at="2026-12-31T23:59:59Z", merged_at="2027-01-01T00:00:00Z"),
        dict(id=2, title="Two", agent="Google Jules", user_id=8, repo_id=10,
             repo_url="https://api.github.com/repos/org/repo", html_url="https://github.com/org/repo/pull/2",
             created_at="2025-02-01T00:00:00Z", merged_at=None),
        dict(id=3, title="Outside", agent="Google_Jules", user_id=7, repo_id=10,
             repo_url="https://api.github.com/repos/org/repo", html_url="https://github.com/org/repo/pull/3",
             created_at="2027-01-01T00:00:00Z", merged_at=None),
    ])
    repos = pd.DataFrame([dict(id=10, url="https://api.github.com/repos/org/repo",
                              license="MIT", full_name="org/repo", language="Python", forks=2, stars=3)])
    users = pd.DataFrame({"id": [7.0, None]})
    reviews = pd.DataFrame([
        dict(id=11, pr_id=1, state="APPROVED", user_type="User"),
        dict(id=12, pr_id=1, state="COMMENTED", user_type="Bot"),
        dict(id=13, pr_id=1, state="CHANGES_REQUESTED", user_type="User"),
    ])
    tasks = pd.DataFrame([dict(id=1, type="feat", confidence=9.0), dict(id=2, type="fix", confidence=7.0)])
    for filename, frame in zip(FILES, (prs, repos, users, reviews, tasks)):
        frame.to_parquet(tmp_path / filename, index=False)
    monkeypatch.setattr(aidedev, "PR_FILE", tmp_path / FILES[0])
    monkeypatch.setattr(aidedev, "REPO_FILE", tmp_path / FILES[1])
    monkeypatch.setattr(aidedev, "USER_FILE", tmp_path / FILES[2])
    monkeypatch.setattr(aidedev, "SOURCE_DIR", tmp_path)
    monkeypatch.setattr(aidedev, "RAW_DIR", tmp_path / "raw")
    return tmp_path


def test_enrichment_does_not_multiply_prs_or_confuse_confidence(dataset):
    records, stats = aidedev.build_aidedev_catalog()
    assert len(records) == 1
    row = records[0]
    assert row["agent"] == "Google Jules"
    assert row["repo_id"] == 10  # Missing ID resolved via unique repo URL.
    assert row["pull_requests_count"] == 2
    assert row["merged_pull_requests"] == 1
    assert row["merge_rate"] == .5
    assert row["last_activity"] == "2026-12-31T23:59:59Z"
    assert row["review_count"] == 3
    assert row["reviewed_pull_requests"] == 1
    assert row["human_review_count"] == 2
    assert row["bot_review_count"] == 1
    assert row["approved_review_count"] == row["changes_requested_review_count"] == 1
    assert row["known_contributors"] == 1
    assert row["unique_contributors"] == 2
    assert row["total_users_dataset"] == 1
    assert row["task_type_counts"] == {"feat": 1, "fix": 1}
    assert row["task_classified_pull_requests"] == 2
    assert row["task_confidence_mean"] == 8  # Original annotation scale, not 0..1.
    assert stats["pull_request_rows_input"] == 3
    assert stats["pull_request_rows_read"] == 2
    stg = normalize_dataframe(pd.DataFrame(records), {"fuente": "catalogo", "id": 1})
    assert stg.loc[0, "cantidad_menciones"] == 2
    assert "review_count=3" in stg.loc[0, "texto"]
    assert "task_type_counts=" in stg.loc[0, "texto"]


def test_duplicate_join_keys_and_prs_cannot_inflate_counts(dataset):
    for filename in FILES:
        path = dataset / filename
        frame = pd.read_parquet(path)
        pd.concat([frame, frame.iloc[:1]]).to_parquet(path, index=False)
    records, _ = aidedev.build_aidedev_catalog()
    assert records[0]["pull_requests_count"] == 2
    assert records[0]["review_count"] == 3
    assert records[0]["task_type_counts"] == {"feat": 1, "fix": 1}


def test_missing_supplements_and_empty_limit_are_supported(dataset):
    (dataset / "pr_reviews.parquet").unlink()
    (dataset / "pr_task_type.parquet").unlink()
    records, _ = aidedev.build_aidedev_catalog()
    assert records[0]["review_count"] == 0
    assert records[0]["task_type_counts"] == {}
    assert aidedev.build_aidedev_catalog(max_pr_rows=0)[0] == []
    assert aidedev.build_aidedev_catalog(max_pr_rows=1)[0][0]["pull_requests_count"] == 1
    with pytest.raises(ValueError):
        aidedev.build_aidedev_catalog(max_pr_rows=-1)


def test_unknown_repositories_keep_distinct_business_keys(dataset):
    prs = pd.read_parquet(dataset / FILES[0]).iloc[:2].copy()
    prs["repo_id"] = None
    prs["repo_url"] = ["https://api.github.com/repos/missing/a", "https://api.github.com/repos/missing/b"]
    prs.to_parquet(dataset / FILES[0], index=False)
    records, _ = aidedev.build_aidedev_catalog()
    assert {r["full_name"] for r in records} == {"missing/a", "missing/b"}
    stg = normalize_dataframe(pd.DataFrame(records), {"fuente": "catalogo", "id": 1})
    assert stg["id_origen_registro"].nunique() == 2


def test_streamed_extraction_publishes_all_supplements(dataset):
    with evidence_context(EvidenceRun("parquet", dataset / "evidence", dataset / "legacy.csv")):
        result = aidedev.extract_aidedev_catalog(run_id="parquet")
    assert result.status.value == "success"
    payload = json.loads(Path(result.raw_path).read_text(encoding="utf-8"))
    assert len(payload["metadata"]["input_files"]) == 5
    assert payload["metadata"]["stats"]["records_generated"] == len(payload["items"]) == 2
    assert sum(r["review_count"] for r in payload["items"]) == 3
    assert not list((dataset / "raw").rglob("*.tmp"))


def test_failed_stream_never_publishes_partial_catalog(dataset, monkeypatch):
    def broken(*args, **kwargs):
        yield {"id": "partial"}
        raise RuntimeError("synthetic stream failure")
    monkeypatch.setattr(aidedev, "iter_catalog", broken)
    with evidence_context(EvidenceRun("broken", dataset / "evidence", dataset / "legacy.csv")):
        result = aidedev.extract_aidedev_catalog(run_id="broken")
    assert result.status.value == "failed"
    assert result.raw_path is None
    assert not list((dataset / "raw").rglob("*.json*"))


def test_prepare_replacement_preserves_legacy_only_and_prefers_new(dataset):
    current, incoming = dataset / "current", dataset / "incoming"
    current.mkdir()
    prs = pd.read_parquet(dataset / FILES[0]).iloc[:2].copy()
    prs.loc[0, "title"] = "obsolete annotation"
    prs.loc[1, "id"] = 99
    prs.to_parquet(current / FILES[0], index=False)
    report = prepare_replacement(dataset, current, incoming)
    final = pd.read_parquet(incoming / FILES[0])
    assert set(final["id"]) == {1, 2, 3, 99}
    assert final.set_index("id").loc[1, "title"] == "One"
    assert report["files"][FILES[0]]["legacy_only_rows"] == 1
    assert report["files"][FILES[2]]["null_ids"] == 1
    assert len(pd.read_parquet(current / FILES[0])) == 2  # no activation side effects
    assert len(pd.read_parquet(dataset / FILES[0])) == 3
    with pytest.raises(FileExistsError):
        prepare_replacement(dataset, current, incoming)


def test_prepare_replacement_rejects_duplicate_primary_ids(dataset):
    path = dataset / FILES[0]
    frame = pd.read_parquet(path)
    pd.concat([frame, frame.iloc[:1]]).to_parquet(path, index=False)
    with pytest.raises(ValueError, match="duplicated IDs"):
        prepare_replacement(dataset, dataset / "empty", dataset / "incoming")
    assert len(pd.read_parquet(path)) == 4  # failure never alters supplied data


def test_consolidated_snapshot_cannot_silently_fall_back_to_old_download(dataset, monkeypatch):
    (dataset / "dataset_manifest.json").write_text('{"files":{}}')
    (dataset / "pr_reviews.parquet").unlink()
    monkeypatch.setattr(aidedev, "_download_file", lambda *args: pytest.fail("must not download"))
    with pytest.raises(FileNotFoundError, match="Incomplete consolidated"):
        aidedev.build_aidedev_catalog()


def test_annual_catalog_has_stable_non_overlapping_keys(dataset):
    combined, _ = aidedev.build_aidedev_catalog(annual=True)
    years = {}
    for year in (2025, 2026):
        rows, _ = aidedev.build_aidedev_catalog(start_date=f"{year}-01-01", end_date=f"{year}-12-31", annual=True)
        assert len(rows) == 1
        assert rows[0]["activity_year"] == year
        assert rows[0]["id"].endswith(f":year:{year}")
        years[year] = rows[0]
    assert {r["id"] for r in combined} == {r["id"] for r in years.values()}
    assert sum(r["pull_requests_count"] for r in combined) == 2
    staging = normalize_dataframe(pd.DataFrame(combined), {"fuente": "catalogo", "id": 1})
    assert staging["id_origen_registro"].nunique() == 2
    assert set(staging["id_origen_registro"]) == {r["id"] for r in combined}
