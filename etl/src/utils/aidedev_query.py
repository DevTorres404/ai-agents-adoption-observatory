"""Projected, disk-backed AIDev aggregation; never materialize PR/review bodies."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import duckdb


def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


@contextmanager
def dataset_connection(work_dir):
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="aidedev-", dir=work_dir) as temporary:
        con = duckdb.connect(str(Path(temporary) / "query.duckdb"))
        try:
            con.execute("SET memory_limit='1GB'")
            con.execute("SET threads=2")
            con.execute("SET preserve_insertion_order=false")
            con.execute("SET TimeZone='UTC'")
            con.execute(f"SET temp_directory={sql_literal(Path(temporary) / 'spill')}")
            yield con
        finally:
            con.close()


def prepare_catalog(con, files, agent_mapping, valid_agents, start_date, end_date, max_pr_rows=None, annual=False):
    """Return statistics and materialize one row per agent/repository, not per join."""
    for name in ("prs", "repos", "users"):
        con.read_parquet(str(files[name])).create_view(f"input_{name}")
    for name in ("reviews", "tasks"):
        if files.get(name) and Path(files[name]).is_file():
            con.read_parquet(str(files[name])).create_view(f"input_{name}")
        elif name == "reviews":
            con.execute("CREATE VIEW input_reviews AS SELECT NULL::BIGINT id, NULL::BIGINT pr_id, NULL::VARCHAR state, NULL::VARCHAR user_type WHERE false")
        else:
            con.execute("CREATE VIEW input_tasks AS SELECT NULL::BIGINT id, NULL::VARCHAR AS type, NULL::DOUBLE confidence WHERE false")
    stats = {f"{label}_rows_input": con.execute(f"SELECT count(*) FROM input_{name}").fetchone()[0]
             for name, label in [("prs", "pull_request"), ("repos", "repository"), ("users", "user"), ("reviews", "review"), ("tasks", "task")]}
    # Keys must be unique before enrichment. Null user IDs are not joinable people.
    con.execute("CREATE TABLE repos AS SELECT id::BIGINT id, url, license, full_name, language, forks, stars FROM input_repos WHERE id IS NOT NULL QUALIFY row_number() OVER(PARTITION BY id ORDER BY full_name NULLS LAST)=1")
    con.execute("CREATE TABLE users AS SELECT id::BIGINT id FROM input_users WHERE id IS NOT NULL GROUP BY id")
    con.execute("CREATE TABLE repo_urls AS SELECT url, min(id) id FROM repos WHERE url IS NOT NULL GROUP BY url HAVING count(*)=1")
    mapping = "CASE agent " + " ".join(f"WHEN {sql_literal(k)} THEN {sql_literal(v)}" for k, v in agent_mapping.items()) + " ELSE agent END"
    limit = ""
    if max_pr_rows is not None:
        if isinstance(max_pr_rows, bool) or not isinstance(max_pr_rows, int) or max_pr_rows < 0:
            raise ValueError("max_pr_rows must be a nonnegative integer")
        limit = f"ORDER BY id LIMIT {max_pr_rows}"
    year_suffix = " || ':year:' || year(created_at)::VARCHAR" if annual else ""
    con.execute(f"""
        CREATE TABLE prs AS
        WITH projected AS (
            SELECT id::BIGINT id, title, agent, user_id::BIGINT user_id,
                   repo_id::BIGINT repo_id, repo_url, html_url,
                   try_cast(created_at AS TIMESTAMPTZ) created_at,
                   try_cast(merged_at AS TIMESTAMPTZ) merged_at
            FROM input_prs {limit}
        ), unique_prs AS (
            SELECT * FROM projected WHERE id IS NOT NULL
            QUALIFY row_number() OVER(PARTITION BY id ORDER BY created_at DESC, html_url, agent)=1
        ), resolved AS (
            SELECT p.* EXCLUDE(agent, repo_id), {mapping} agent,
                   coalesce(p.repo_id, r.id) repo_id
            FROM unique_prs p LEFT JOIN repo_urls r ON p.repo_url=r.url
        )
        SELECT *, coalesce('id:' || repo_id::VARCHAR, 'url:' || nullif(repo_url,''), 'pr:' || id::VARCHAR){year_suffix} repo_key
        FROM resolved
        WHERE agent IN ({','.join(sql_literal(x) for x in valid_agents)})
          AND created_at >= {sql_literal(start_date)}::TIMESTAMPTZ
          AND created_at < {sql_literal(end_date)}::TIMESTAMPTZ + INTERVAL 1 DAY
    """)
    con.execute("""CREATE TABLE reviews AS
        SELECT pr_id, count(*) review_count,
               count(*) FILTER(WHERE user_type='User') human_review_count,
               count(*) FILTER(WHERE user_type='Bot') bot_review_count,
               count(*) FILTER(WHERE state='APPROVED') approved_review_count,
               count(*) FILTER(WHERE state='CHANGES_REQUESTED') changes_requested_review_count
        FROM (SELECT id, pr_id, state, user_type FROM input_reviews WHERE id IS NOT NULL
              QUALIFY row_number() OVER(PARTITION BY id ORDER BY pr_id, state, user_type)=1)
        GROUP BY pr_id""")
    con.execute("""CREATE TABLE tasks AS SELECT id, type, confidence FROM input_tasks
        WHERE id IS NOT NULL QUALIFY row_number() OVER(PARTITION BY id ORDER BY confidence DESC NULLS LAST, type)=1""")
    con.execute("""CREATE TABLE grouped AS
        SELECT p.agent, p.repo_key, any_value(p.repo_id) repo_id, min(p.repo_url) repo_url,
               count(*) pull_requests_count, count(p.merged_at) merged_pull_requests,
               count(DISTINCT p.user_id) unique_contributors,
               count(DISTINCT u.id) known_contributors,
               strftime(min(p.created_at), '%Y-%m-%dT%H:%M:%SZ') first_activity,
               strftime(max(p.created_at), '%Y-%m-%dT%H:%M:%SZ') last_activity,
               arg_min(p.title, p.id) sample_pr_title, arg_min(p.html_url,p.id) sample_pr_url,
               count(r.pr_id) reviewed_pull_requests,
               coalesce(sum(r.review_count),0)::BIGINT review_count,
               coalesce(sum(r.human_review_count),0)::BIGINT human_review_count,
               coalesce(sum(r.bot_review_count),0)::BIGINT bot_review_count,
               coalesce(sum(r.approved_review_count),0)::BIGINT approved_review_count,
               coalesce(sum(r.changes_requested_review_count),0)::BIGINT changes_requested_review_count,
               count(t.type) task_classified_pull_requests,
               avg(t.confidence) task_confidence_mean
        FROM prs p LEFT JOIN reviews r ON p.id=r.pr_id LEFT JOIN tasks t ON p.id=t.id
                   LEFT JOIN users u ON p.user_id=u.id
        GROUP BY p.agent, p.repo_key""")
    con.execute("""CREATE TABLE task_counts AS
        SELECT agent, repo_key, map(list(type ORDER BY type),list(n ORDER BY type)) task_type_counts
        FROM (SELECT p.agent, p.repo_key, t.type, count(*) n FROM prs p JOIN tasks t ON p.id=t.id
              WHERE t.type IS NOT NULL GROUP BY p.agent,p.repo_key,t.type)
        GROUP BY agent,repo_key""")
    con.execute("""CREATE TABLE catalog AS
        SELECT g.*, r.url repo_api_url,
               coalesce(nullif(r.full_name,''), nullif(regexp_replace(g.repo_url, '^https?://(api\\.)?github\\.com/(repos/)?', ''),''),g.repo_key) full_name,
               r.language, r.license, coalesce(r.stars,0)::BIGINT stars, coalesce(r.forks,0)::BIGINT forks,
               tc.task_type_counts
        FROM grouped g LEFT JOIN repos r ON g.repo_id=r.id
        LEFT JOIN task_counts tc ON g.agent=tc.agent AND g.repo_key=tc.repo_key""")
    stats.update({
        "pull_request_rows_read": con.execute("SELECT count(*) FROM prs").fetchone()[0],
        "repository_rows_read": con.execute("SELECT count(*) FROM repos").fetchone()[0],
        "user_rows_read": stats["user_rows_input"],
        "unique_users": con.execute("SELECT count(*) FROM users").fetchone()[0],
        "records_generated": con.execute("SELECT count(*) FROM catalog").fetchone()[0],
        "agents": dict(con.execute("SELECT agent,count(*) FROM prs GROUP BY agent ORDER BY agent").fetchall()),
        "review_rows_linked": con.execute("SELECT coalesce(sum(review_count),0)::BIGINT FROM grouped").fetchone()[0],
        "task_rows_linked": con.execute("SELECT coalesce(sum(task_classified_pull_requests),0)::BIGINT FROM grouped").fetchone()[0],
        "unresolved_repository_prs": con.execute("SELECT count(*) FROM prs WHERE repo_id IS NULL").fetchone()[0],
    })
    return stats


def iter_catalog(con, total_users, batch_size=2048):
    cursor = con.execute("SELECT * FROM catalog ORDER BY pull_requests_count DESC,agent,repo_key")
    columns = [item[0] for item in cursor.description]
    while batch := cursor.fetchmany(batch_size):
        for values in batch:
            record = dict(zip(columns, values))
            record["id"] = record["agent"] + ":" + record.pop("repo_key")
            if ":year:" in record["id"]:
                record["activity_year"] = int(record["id"].rsplit(":year:", 1)[1])
            record["merge_rate"] = round(record["merged_pull_requests"] / record["pull_requests_count"],4)
            record["dataset"] = "AIDev Dataset: AI Coding"
            record["total_users_dataset"] = total_users
            record["task_type_counts"] = record["task_type_counts"] or {}
            for field in ("repo_url", "repo_api_url", "full_name", "language", "license", "sample_pr_title", "sample_pr_url"):
                record[field] = record[field] or ""
            yield record
