"""Stage a validated AIDev replacement without modifying any source files.

Newest rows win overlapping IDs. Retain every legacy-only row, including
unjoinable null user IDs; these are reported and never counted as known people.
Activation is deliberately separate so a failed import leaves manual untouched.
"""
import argparse
import hashlib
import json
from pathlib import Path

from src.utils.aidedev_query import dataset_connection, sql_literal


FILES = ("all_pull_request.parquet", "all_repository.parquet", "all_user.parquet",
         "pr_reviews.parquet", "pr_task_type.parquet")


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def prepare_replacement(source_dir, current_dir, incoming_dir):
    source_dir, current_dir, incoming_dir = map(lambda p: Path(p).resolve(),
                                               (source_dir, current_dir, incoming_dir))
    if incoming_dir == source_dir or incoming_dir == current_dir:
        raise ValueError("Staging must be separate from source and current datasets")
    for filename in FILES:
        if not (source_dir / filename).is_file():
            raise FileNotFoundError(source_dir / filename)
        if (incoming_dir / filename).exists():
            raise FileExistsError(incoming_dir / filename)
    incoming_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"policy": "newest ID wins; retain legacy-only rows", "files": {}}
    with dataset_connection(incoming_dir / ".work") as con:
        for filename in FILES:
            source = source_dir / filename
            old = current_dir / filename
            target = incoming_dir / filename
            con.read_parquet(str(source)).create_view("new_rows", replace=True)
            new_count, unique, nulls = con.execute("SELECT count(*), count(DISTINCT id), count(*) FILTER(WHERE id IS NULL) FROM new_rows").fetchone()
            if unique + nulls != new_count or (nulls and filename != "all_user.parquet"):
                raise ValueError(f"Invalid or duplicated IDs in {source}")
            query = "SELECT * FROM new_rows"
            legacy_count = 0
            if old.is_file():
                con.read_parquet(str(old)).create_view("old_rows", replace=True)
                old_count, old_unique, old_nulls = con.execute("SELECT count(*), count(DISTINCT id), count(*) FILTER(WHERE id IS NULL) FROM old_rows").fetchone()
                if old_unique + old_nulls != old_count or (old_nulls and filename != "all_user.parquet"):
                    raise ValueError(f"Invalid or duplicated IDs in {old}")
                # Narrow anti-join on IDs, not full strings/bodies. UNION BY NAME
                # preserves expanded fields such as repositories.is_forked.
                legacy = "SELECT o.* FROM old_rows o WHERE o.id IS NULL OR NOT EXISTS (SELECT 1 FROM new_rows n WHERE n.id=o.id)"
                legacy_count = con.execute(f"SELECT count(*) FROM ({legacy})").fetchone()[0]
                query += " UNION ALL BY NAME " + legacy
            print(f"Preparing {filename}: new={new_count}, legacy_only={legacy_count}", flush=True)
            con.execute(f"COPY ({query}) TO {sql_literal(target)} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 16384)")
            con.read_parquet(str(target)).create_view("prepared", replace=True)
            final_count, final_unique, final_nulls = con.execute("SELECT count(*),count(DISTINCT id),count(*) FILTER(WHERE id IS NULL) FROM prepared").fetchone()
            if final_count != new_count + legacy_count or final_unique + final_nulls != final_count:
                raise RuntimeError(f"Validation failed for {target}")
            # Verify every new ID and legacy ID survives consolidation.
            missing = con.execute("SELECT count(*) FROM new_rows n ANTI JOIN prepared p ON n.id=p.id WHERE n.id IS NOT NULL").fetchone()[0]
            if old.is_file():
                missing += con.execute("SELECT count(*) FROM old_rows o ANTI JOIN prepared p ON o.id=p.id WHERE o.id IS NOT NULL").fetchone()[0]
            if missing:
                raise RuntimeError(f"Lost {missing} IDs while preparing {target}")
            manifest["files"][filename] = {
                "source_rows": new_count, "legacy_only_rows": legacy_count,
                "rows": final_count, "unique_ids": final_unique, "null_ids": final_nulls,
                "source_sha256": fingerprint(source), "sha256": fingerprint(target),
                "previous_sha256": fingerprint(old) if old.is_file() else None,
            }
            print(f"Validated {filename}: {final_count} rows", flush=True)
    (incoming_dir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--current-dir", required=True, type=Path)
    parser.add_argument("--incoming-dir", required=True, type=Path)
    args = parser.parse_args()
    prepare_replacement(args.source_dir, args.current_dir, args.incoming_dir)
