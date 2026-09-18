"""Source isolation, temporal requests and durable audit contracts (offline)."""
import ast
import datetime as dt
import importlib
import json
from itertools import chain
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
import yaml

from src.extractors import google_trends, hackernews
from src.scripts import run_pipeline as runner
from src.staging.stg_dates import parse_dates
from src.utils.extraction_evidence import EvidenceRun, evidence_context
from src.utils.extraction_window import require_annual_window, resolve_window
from src.utils.pipeline_scope import includes_source, source_predicate
from src.utils.observatory_scope import ACTIVE_SOURCES, INACTIVE_SOURCES, SUPPORTED_AGENTS


SOURCES = {'github': 'extract_github_repos', 'catalogo': 'extract_aidedev_catalog',
           'google_trends': 'extract_trends', 'hackernews': 'extract_hackernews'}


@pytest.mark.parametrize('source', SOURCES)
def test_single_source_dispatch_and_window(monkeypatch, source):
    mocks = {name: MagicMock() for name in SOURCES.values()}
    for name, mock in mocks.items():
        monkeypatch.setattr(runner, name, mock)
    runner.run_extraction_phase(7, pipeline=source, start_date='2021-01-01', end_date='2022-12-31')
    for owned, name in SOURCES.items():
        assert mocks[name].call_count == int(owned == source)
    assert mocks[SOURCES[source]].call_args.kwargs['start_date'] == '2021-01-01'
    assert mocks[SOURCES[source]].call_args.kwargs['end_date'] == '2022-12-31'
    assert source_predicate(source) == f"f.fuente IN ('{source}')"
    assert all(not includes_source(source, other) for other in INACTIVE_SOURCES)


def test_stackoverflow_is_retired_but_hackernews_is_active():
    assert ACTIVE_SOURCES == set(SOURCES)
    assert 'stackoverflow' in INACTIVE_SOURCES
    assert all(not includes_source(p, 'stackoverflow') for p in ['main', 'all', *SOURCES])
    tree = ast.parse(Path(runner.__file__).read_text(encoding='utf-8'))
    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    assert len(names) == len(set(names)), 'No silently overridden orchestrator functions'


@pytest.mark.parametrize('source', SOURCES)
def test_year_cli_persists_requested_scope_even_when_empty(monkeypatch, tmp_path, source):
    configs = []
    monkeypatch.setattr(runner, 'start_pipeline_audit', lambda config: configs.append(config) or 7)
    monkeypatch.setattr(runner, 'end_pipeline_audit', MagicMock())
    monkeypatch.setattr(runner, 'EvidenceRun', lambda rid, **kw: EvidenceRun(rid, tmp_path/'runs', tmp_path/'latest.csv', **kw))
    extract = MagicMock()
    monkeypatch.setattr(runner, 'run_extraction_phase', extract)
    module = importlib.import_module(f'src.scripts.run_{source}_pipeline')
    module.main(['--phase', 'extract', '--from-year', '2021', '--to-year', '2022'])
    assert configs[0]['sources'] == [source]
    assert configs[0]['window'] == {'start': '2021-01-01', 'end': '2022-12-31', 'inclusive': True}
    assert extract.call_args.kwargs['pipeline'] == source
    summary = json.loads((tmp_path/'runs/7/summary.json').read_text())
    assert summary['run_config'] == configs[0]
    assert summary['status'] == 'empty'


@pytest.mark.parametrize('args', [
    ['--from-year','2024'], ['--from-year','2025','--to-year','2024'],
    ['--start-date','2024-01-01'], ['--start-date','2024-02-30','--end-date','2024-12-31'],
    ['--from-year','2024','--to-year','2024','--start-date','2024-01-01'],
    ['--phase','process','--from-year','2024','--to-year','2024'],
    ['--pipeline','stackoverflow'],
    ['--from-year','2024','--to-year','2024','--date=2024-12-31'],
    ['--start-date','2024-02-01','--end-date','2024-12-31'],
])
def test_invalid_cli_never_starts_a_run(monkeypatch, args):
    start = MagicMock()
    monkeypatch.setattr(runner, 'start_pipeline_audit', start)
    with pytest.raises(SystemExit) as error:
        runner.main(args)
    assert error.value.code == 2
    start.assert_not_called()


def test_calendar_boundaries_include_leap_day_and_last_second():
    window = resolve_window('2020-02-29', '2021-01-01')
    end = hackernews._epoch(hackernews._ec_midnight(2021, 1, 2)) - 1
    slices = hackernews._window_bounds(end, window.start)
    assert [year for year, _, _ in slices] == [2020, 2021]
    assert slices[0][1] == hackernews._epoch(hackernews._ec_midnight(2020, 2, 29))
    assert slices[0][2] + 1 == slices[1][1]
    assert slices[-1][2] == end


def test_annual_catalog_rejects_partial_cohort():
    with pytest.raises(ValueError, match='AIDev'):
        require_annual_window(resolve_window('2021-01-01', '2021-06-30'))
    require_annual_window(resolve_window('2021-01-01', '2022-12-31'))


def test_hackernews_passes_requested_window_to_http_and_metadata(monkeypatch, tmp_path):
    calls = []
    start = hackernews._epoch(hackernews._ec_midnight(2021, 3, 1))
    end = hackernews._epoch(hackernews._ec_midnight(2021, 4, 1)) - 1

    class Client:
        last_status_code = 200

        def get(self, url, params=None, **kwargs):
            calls.append(params['numericFilters'])
            return {'hits': [{'objectID': '1', 'created_at_i': start, 'title': 'Cursor'}], 'nbHits': 1}

    monkeypatch.setattr(hackernews, 'HttpClient', lambda **kwargs: Client())
    monkeypatch.setattr(hackernews, 'AGENT_QUERIES', ['Cursor'])
    monkeypatch.setattr(hackernews, 'RAW_DIR', tmp_path/'raw')
    with evidence_context(EvidenceRun(4, tmp_path/'evidence', tmp_path/'latest.csv')):
        result = hackernews.extract_hackernews(run_id=4, sleeper=lambda _:None,
                                               start_date='2021-03-01', end_date='2021-03-31')
    assert calls == [f'created_at_i>={start},created_at_i<={end}']
    metadata = json.loads(Path(result.raw_path).read_text(encoding='utf-8'))['metadata']
    assert metadata['date_range_start'] == '2021-03-01'
    assert metadata['date_range_end'] == '2021-03-31'
    assert metadata['effective_end_timestamp'] == end


def test_staging_no_longer_discards_requested_years():
    frame = pd.DataFrame({'fecha_evento_raw': ['2021-07-12', '2028-06-10', None]})
    assert parse_dates(frame)['fecha_evento'].tolist() == ['2021-07-12', '2028-06-10']


def test_trends_passes_window_to_http_adapter_and_metadata(monkeypatch, tmp_path):
    class Client:
        def __init__(self, **kwargs):
            self.keywords = []
            self.batches = []
            self.timeframes = []

        def build_payload(self, keywords, **kwargs):
            self.keywords = keywords
            self.batches.append(keywords)
            self.timeframes.append(kwargs.get('timeframe'))

        def interest_over_time(self):
            return pd.DataFrame({keyword: [3] for keyword in self.keywords},
                                index=pd.DatetimeIndex(['2021-06-01'], name='date'))

    client = Client()
    monkeypatch.setattr(google_trends, 'TrendReq', lambda **kw: client)
    monkeypatch.setattr(google_trends, 'RAW_DIR', tmp_path/'raw')
    with evidence_context(EvidenceRun(3, tmp_path/'evidence', tmp_path/'latest.csv')):
        result = google_trends.extract_trends(run_id=3, sleeper=lambda _:None,
                                              start_date='2021-01-01', end_date='2021-12-31')
    assert client.timeframes and set(client.timeframes) == {'2021-01-01 2021-12-31'}
    metadata = json.loads(Path(result.raw_path).read_text(encoding='utf-8'))['metadata']
    assert metadata['date_range_start'] == '2021-01-01'
    assert metadata['date_range_end'] == '2021-12-31'
    assert metadata['records_extracted'] == sum(len(batch) for batch in client.batches)
    assert set(chain.from_iterable(client.batches)) == set(SUPPORTED_AGENTS)


@pytest.mark.parametrize('filename', ['docker-compose.yml', 'docker-compose.prod.yml'])
def test_each_source_has_separate_worker_and_artifacts(filename):
    root = Path(__file__).resolve().parents[2]
    services = yaml.safe_load((root/filename).read_text(encoding='utf-8'))['services']
    for source, service in [('catalogo','aidedev'),('github','github'),('google_trends','google-trends'),('hackernews','hackernews')]:
        worker = services[f'etl-{service}']
        assert worker['entrypoint'][-1] == f'src.scripts.run_{source}_pipeline'
        assert f'./etl/docs/{source}:/app/docs' in worker['volumes']
        assert f'./etl/logs/{source}:/app/logs' in worker['volumes']
    assert 'etl-stackoverflow' not in services


def test_run_config_migration_is_additive_and_matches_init():
    root = Path(__file__).resolve().parents[1]
    sql = (root/'sql/13_source_run_config.sql').read_text(encoding='utf-8')
    assert sql == (root/'initdb/14_source_run_config.sql').read_text(encoding='utf-8')
    assert 'ADD COLUMN IF NOT EXISTS run_config JSONB' in sql
    assert 'DROP ' not in sql and 'TRUNCATE ' not in sql
