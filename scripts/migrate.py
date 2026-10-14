"""Run as a trusted deployment operator, never as the Streamlit runtime role."""
import os
from pathlib import Path
import psycopg

ROOT = Path(__file__).resolve().parents[1]
url = os.getenv("MIGRATION_DATABASE_URL", "").strip()
if not url:
    raise SystemExit("Set MIGRATION_DATABASE_URL to the dfts_owner PostgreSQL URL before migrating.")
os.environ["DATABASE_URL"] = url
os.environ["DFTS_MIGRATION_MODE"] = "1"
import sys
sys.path.insert(0, str(ROOT))
from database import initialize_database

initialize_database()
with psycopg.connect(url, autocommit=True) as conn:
    conn.execute((ROOT / "migrations" / "001_rls.sql").read_text(), prepare=False)
    # The RLS migration configures least-privilege table/column grants.
    conn.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO dfts_app")
    conn.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO dfts_app")
    conn.execute("ALTER DEFAULT PRIVILEGES FOR ROLE dfts_owner IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO dfts_app")
print("PostgreSQL schema and RLS policies installed successfully.")
