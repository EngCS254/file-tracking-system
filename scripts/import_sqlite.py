"""One-time import of a legacy SQLite DB into an already-migrated PostgreSQL DB.
Run with MIGRATION_DATABASE_URL. Target users/files tables must be empty.
"""
import argparse
import os
import sqlite3
from pathlib import Path
import sys

import psycopg
from psycopg import sql

TABLES = ["users", "files", "file_movements", "notifications", "auth_attempts", "file_requests", "audit_trail"]
ID_TABLES = ["users", "files", "file_movements", "notifications", "file_requests", "audit_trail"]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite_path", help="Path to the old filing_system.db")
    args = parser.parse_args()
    source_path = Path(args.sqlite_path).expanduser().resolve()
    if not source_path.is_file():
        raise SystemExit(f"SQLite file not found: {source_path}")
    url = os.getenv("MIGRATION_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("Set MIGRATION_DATABASE_URL to the dfts_owner URL.")

    src = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    try:
        with psycopg.connect(url) as dst:
            counts = {t: dst.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(t))).fetchone()[0]
                      for t in ("users", "files")}
            if counts["users"] or counts["files"]:
                raise SystemExit(f"Target is not empty (users={counts['users']}, files={counts['files']}). Import aborted.")
            for table in TABLES:
                exists = src.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                if not exists:
                    print(f"skip {table}: not present in source")
                    continue
                source_columns = [r[1] for r in src.execute(f'PRAGMA table_info("{table}")').fetchall()]
                target_columns = [r[0] for r in dst.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
                    (table,)).fetchall()]
                columns = [c for c in source_columns if c in target_columns]
                if not columns:
                    print(f"skip {table}: no shared columns")
                    continue
                rows = src.execute(f'SELECT {", ".join(chr(34)+c+chr(34) for c in columns)} FROM "{table}"').fetchall()
                if rows:
                    insert = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        sql.Identifier(table),
                        sql.SQL(", ").join(map(sql.Identifier, columns)),
                        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                    )
                    with dst.cursor() as cursor:
                        cursor.executemany(insert, [tuple(row[c] for c in columns) for row in rows])
                print(f"imported {len(rows)} rows into {table}")
            for table in ID_TABLES:
                dst.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE((SELECT MAX(id) FROM " + table + "), 1), (SELECT MAX(id) IS NOT NULL FROM " + table + "))", (f"public.{table}",))
            dst.commit()
    finally:
        src.close()
    print("Import complete. Reconcile counts and test RLS before switching users.")

if __name__ == "__main__":
    main()
