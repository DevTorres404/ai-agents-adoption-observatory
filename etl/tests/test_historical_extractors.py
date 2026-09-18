"""Offline contracts for the historical Hacker News backfill (Algolia windows)."""
import datetime
import json
from pathlib import Path

from src.extractors import hackernews
from src.utils.extraction_evidence import EvidenceRun, evidence_context


def _run(tmp_path, run_id):
    return EvidenceRun(run_id, tmp_path / "runs", tmp_path / "legacy.csv")


def test_hn_windows_cover_2023_2026_without_gaps():
    end_ts = hackernews._epoch(hackernews._ec_midnight(2026, 9, 16))
    windows = hackernews._window_bounds(end_ts)

    assert [year for year, _, _ in windows] == [2023, 2024, 2025, 2026]
    assert windows[0][1] == hackernews._epoch(
        datetime.datetime(2023, 1, 1, tzinfo=hackernews.ECUADOR_TZ)
    )
    assert windows[-1][2] == end_ts
    for (_, _, previous_end), (_, next_start, _) in zip(windows, windows[1:]):
        assert next_start == previous_end + 1


def test_hn_extract_uses_real_creation_date_and_deduplicates(monkeypatch, tmp_path):
    class FakeClient:
        last_status_code = 200

        def __init__(self, *args, **kwargs):
            pass

        def get(self, url, params=None, headers=None, is_json=None):
            if params["page"] == 0:
                return {
                    "hits": [
                        {"objectID": "1", "created_at_i": 1673000000, "title": "Cursor",
                         "url": "https://x/1", "points": 3, "num_comments": 1},
                        {"objectID": "2", "created_at_i": 1690000000, "title": "Cursor again",
                         "url": None, "points": None, "num_comments": None},
                    ],
                    "nbPages": 3,
                    "nbHits": 2,
                }
            return {"hits": [], "nbPages": 3, "nbHits": 2}

    monkeypatch.setattr(hackernews, "HttpClient", FakeClient)
    monkeypatch.setattr(hackernews, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(hackernews, "AGENT_QUERIES", ["Cursor"])
    monkeypatch.setattr(hackernews, "HITS_PER_PAGE", 2)

    run = _run(tmp_path, "hn")
    with evidence_context(run):
        result = hackernews.extract_hackernews(run_id="hn", sleeper=lambda *_: None)

    payload = json.loads(Path(result.raw_path).read_text(encoding="utf-8"))
    records = payload["items"]
    assert result.records_extracted == 2  # dedup por objectID entre ventanas
    assert {record["id"] for record in records} == {"1", "2"}
    assert records[0]["created_at"].startswith("2023-")
    fallback = next(record for record in records if record["id"] == "2")
    assert fallback["url"] == "https://news.ycombinator.com/item?id=2"
    assert fallback["points"] == 0


def test_hn_bisects_window_when_algolia_caps_hits(monkeypatch, tmp_path):
    """Algolia no pagina mas de 1000 hits: una ventana grande debe bisecarse en tiempo."""
    calls = []

    class FakeClient:
        last_status_code = 200

        def __init__(self, *args, **kwargs):
            pass

        def get(self, url, params=None, headers=None, is_json=None):
            assert params["page"] == 0  # nunca se pagina
            start = int(params["numericFilters"].split(",")[0].split(">=")[1])
            end = int(params["numericFilters"].split(",")[1].split("<=")[1])
            calls.append((start, end))
            hits = [
                {"objectID": f"call{len(calls)}-{i}", "created_at_i": start + i, "title": "Cursor",
                 "url": None, "points": 0, "num_comments": 0}
                for i in range(hackernews.HITS_PER_PAGE)
            ]
            return {"hits": hits, "nbHits": 2500}

    monkeypatch.setattr(hackernews, "HttpClient", FakeClient)
    monkeypatch.setattr(hackernews, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(hackernews, "AGENT_QUERIES", ["Cursor"])
    monkeypatch.setattr(hackernews, "HITS_PER_PAGE", 2)
    monkeypatch.setattr(hackernews, "MIN_WINDOW_SECONDS", 16_000_000)

    run = _run(tmp_path, "hn-bisect")
    with evidence_context(run):
        result = hackernews.extract_hackernews(run_id="hn-bisect", sleeper=lambda *_: None)

    # 4 ventanas anuales, cada una partida una vez (3 consultas por ventana). Los hits
    # del padre se descartan: las 8 subventanas hoja cubren el mismo rango y no se solapan.
    assert len(calls) == 12
    assert result.records_extracted == 8 * 2


