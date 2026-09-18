"""Keep the agent scope aligned across the ten configured agents (offline)."""
import ast
import json
from pathlib import Path

import pandas as pd
import pytest

from src.extractors import aidedev, github, google_trends, hackernews
from src.staging.stg_agents import AGENTES_ESTANDAR, extract_agent
from src.utils.extraction_evidence import EvidenceRun, evidence_context
from src.utils.observatory_scope import SUPPORTED_AGENTS


EXPECTED_AGENTS = {
    "Codex", "GitHub Copilot Coding Agent", "Cursor Agent", "Windsurf Cascade", "Devin",
    "OpenCode", "Claude Code", "Cline", "Google Antigravity", "Google Jules",
}


@pytest.mark.parametrize("module,variable", [
    ("github", "queries"), ("aidedev", "valid_agents"), ("hackernews", "AGENT_QUERIES"),
])
def test_all_extractor_lists_preserve_the_configured_agents(module, variable):
    path = Path(aidedev.__file__).with_name(f"{module}.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lists = [
        ast.literal_eval(node.value) for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List)
        and any(isinstance(target, ast.Name) and target.id == variable for target in node.targets)
    ]
    assert len(lists) == 1
    assert len(lists[0]) == 10
    assert set(lists[0]) == EXPECTED_AGENTS == set(AGENTES_ESTANDAR.values()) == set(SUPPORTED_AGENTS)


@pytest.mark.parametrize("label", ["Google_Jules", "Google Jules", "GOOGLE JULES"])
def test_staging_recognizes_jules_alias_without_matching_person_names(label):
    result = extract_agent(pd.DataFrame([
        {"agente": label}, {"titulo": f"Testing {label}"},
        {"titulo": "Jules Verne"}, {"titulo": "Google Julesville"},
    ]))
    assert result["nombre_agente"].tolist() == [
        "Google Jules", "Google Jules", "Otro Agente IA", "Otro Agente IA",
    ]


def test_aidedev_includes_google_jules_and_preserves_existing_aliases(monkeypatch, tmp_path):
    labels = ["Google_Jules", "Google Jules", "OpenAI_Codex", "Copilot", "Claude_Code", "Unknown"]
    prs = pd.DataFrame([
        dict(id=i, title="Test", body="", agent=label, user_id=i, user="user",
             state="closed", created_at="2025-06-01T00:00:00Z",
             closed_at="2025-06-02T00:00:00Z", merged_at="2025-06-02T00:00:00Z",
             repo_id=1, repo_url="https://api.github.com/repos/org/repo",
             html_url=f"https://github.com/org/repo/pull/{i}")
        for i, label in enumerate(labels, 1)
    ])
    repos = pd.DataFrame([dict(id=1, url="https://api.github.com/repos/org/repo",
                              license="MIT", full_name="org/repo", language="Python", forks=0, stars=1)])
    users = pd.DataFrame([dict(id=1, login="user", followers=0, following=0, created_at="2024-01-01")])
    for variable, frame in [("PR_FILE", prs), ("REPO_FILE", repos), ("USER_FILE", users)]:
        path = tmp_path / f"{variable}.parquet"
        frame.to_parquet(path, index=False)
        monkeypatch.setattr(aidedev, variable, path)
    monkeypatch.setattr(aidedev, "_require_files", lambda: None)
    records, stats = aidedev.build_aidedev_catalog()
    by_agent = {item["agent"]: item for item in records}
    assert set(by_agent) == {"Google Jules", "Codex", "GitHub Copilot Coding Agent", "Claude Code"}
    assert by_agent["Google Jules"]["pull_requests_count"] == 2
    assert by_agent["Google Jules"]["merged_pull_requests"] == 2
    assert stats["pull_request_rows_read"] == 5


def test_google_trends_requests_two_batches_and_retains_jules(monkeypatch, tmp_path):
    batches, sleeps = [], []

    class FakeTrendReq:
        def __init__(self, **kwargs):
            pass

        def build_payload(self, keywords, **kwargs):
            self.keywords = keywords
            batches.append(keywords)

        def interest_over_time(self):
            return pd.DataFrame({keyword: [1] for keyword in self.keywords},
                                index=pd.DatetimeIndex(["2025-06-01"], name="date"))

    monkeypatch.setattr(google_trends, "TrendReq", FakeTrendReq)
    monkeypatch.setattr(google_trends, "RAW_DIR", tmp_path / "raw")
    run = EvidenceRun("jules-test", tmp_path / "evidence", tmp_path / "legacy.csv")
    with evidence_context(run):
        result = google_trends.extract_trends(run_id="jules-test", sleeper=sleeps.append)
    payload = json.loads(Path(result.raw_path).read_text(encoding="utf-8"))
    assert [len(batch) for batch in batches] == [5, 5]
    assert batches[-1] == ["OpenCode", "Claude Code", "Cline", "Google Antigravity", "Google Jules"]
    assert sleeps == [60]
    assert result.records_extracted == 10
    assert payload["items"][-1]["agente"] == "Google Jules"
