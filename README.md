# Digital File Tracking System — PostgreSQL + RLS

A Streamlit digital records/file tracking application with user roles, department/section scope, file movement tracking, approval/request workflows, barcode support, notifications and audit history. This edition replaces SQLite with PostgreSQL and adds database-enforced Row-Level Security (RLS).

> **Production security note:** RLS protects rows when queries are executed by the restricted `dfts_app` database role. Do not run Streamlit as `postgres`, `dfts_owner`, or any role with `BYPASSRLS`. Do not expose database credentials to the browser. The application uses transaction-local session settings to pass the authenticated application identity to PostgreSQL; this is intended for a trusted server-side application. A party holding the app database credentials can set custom session variables, so those credentials must remain secret and the database must not be directly accessible to end users.

## Stack

- Python 3.12+
- Streamlit
- PostgreSQL 16+
- Psycopg 3
- PostgreSQL RLS policies for users, files, file movements, notifications, file requests, audit trail and authentication attempts
- Docker Compose for repeatable deployment

## Security model

- `dfts_app`: runtime role; `NOBYPASSRLS`, not a table owner, and only granted the required table/sequence/function permissions.
- `dfts_owner`: migration/table owner; `BYPASSRLS`, never use this account for the running app.
- RLS is both `ENABLE`d and `FORCE`d on application tables.
- Users can see their own user record; administrators can see the user directory. File rows are scoped to department and, when assigned, section. Administrators can access all files.
- File deletion is a request/approval workflow; the application soft-deletes approved records and preserves audit history. RLS prevents non-admin users from changing a file into a deleted state or physically deleting a file row.
- Only administrators can provision/deactivate accounts through application workflows. The first administrator is provisioned during controlled setup.
- Audit rows are protected by RLS and a database trigger that rejects updates/deletes.
- OAuth/OIDC sign-in maps a verified provider email to an existing active account; it does not self-provision users.

### Trust boundary note

PostgreSQL RLS is defense in depth, not a replacement for application authentication. The server sets `app.user_id` transaction-locally after resolving the authenticated user. Anyone with the database login can issue SQL and set custom GUC variables themselves; therefore `dfts_app` credentials must never be given to staff/end users, and database network access should be restricted to the application service.

## Quick start with Docker Compose

1. Install Docker Desktop / Docker Engine with Compose v2.
2. Copy `.env.example` to `.env`.
3. Replace every sample password with a different, strong random secret. Keep `.env` out of source control.
4. Start PostgreSQL:

   ```bash
   docker compose up -d db
   ```

5. Apply schema and RLS migrations using the dedicated migration role:

   ```bash
   docker compose --profile tools run --rm migrate
   ```

6. Start the application:

   ```bash
   docker compose up -d --build app
   ```

7. Open `http://localhost:8501` for local testing. During first-account setup, the app requires `DFTS_BOOTSTRAP_TOKEN` from `.env`. Create the first administrator, then remove that variable from `.env` and recreate the app container (`docker compose up -d --force-recreate app`). For camera scanning and OAuth callback URLs in a deployed environment, configure HTTPS and the matching trusted domain.

The PostgreSQL initialization role script runs only when the database volume is first initialized. If you change role passwords after a volume already exists, update the PostgreSQL roles explicitly; editing `.env` alone does not rotate existing database credentials.

## Run locally without Docker

Requirements: Python 3.12+, PostgreSQL 16+, and a PostgreSQL database.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Set environment variables in the shell (do not commit them):

```text
DATABASE_URL=postgresql://dfts_app:...@localhost:5432/dfts
MIGRATION_DATABASE_URL=postgresql://dfts_owner:...@localhost:5432/dfts
```

Run migrations as a deployment operator:

```bash
python scripts/migrate.py
```

Then run the Streamlit app with only the runtime `DATABASE_URL` configured:

```bash
streamlit run app.py
```

The app validates that the schema exists on startup; it does not run schema migrations with the restricted runtime role. `DATABASE_URL` can also be placed in `.streamlit/secrets.toml` for Streamlit-managed deployments. Never commit real secrets.

## Migration from SQLite

This project now expects PostgreSQL. The schema migration creates new tables and does not automatically import the old SQLite data. To preserve existing records, export them from the old installation and import them into PostgreSQL using a reviewed one-time migration script. Before importing production data:

1. Back up the original SQLite database.
2. Map each table and validate IDs/foreign keys, timestamps, roles, file statuses and request statuses.
3. Import in dependency order: users, files, movements, notifications, requests, audit trail, authentication attempts.
4. Reconcile row counts and foreign-key relationships.
5. Re-seed identity sequences after preserving IDs.
6. Test RLS using the restricted `dfts_app` login and at least two users from different departments/sections.

Do not simply copy the SQLite database file or run SQLite SQL against PostgreSQL. A one-time import helper is included; after the target database has been migrated and backed up, run it from the project root with the old database path:

```bash
# Example for local Python (MIGRATION_DATABASE_URL must point to dfts_owner):
python scripts/import_sqlite.py ./data/filing_system.db
```

The import refuses to run if target `users` or `files` tables already contain rows. Run it only against a fresh target, reconcile every table count and test the application before cutover.

## OAuth/OIDC

The app's existing OAuth path expects the provider to return a verified email and maps it to an existing active user. Configure provider client ID/secret and redirect URI using `.streamlit/secrets.toml` (see `secrets.toml.example`). Use HTTPS in production, validate exact redirect URIs with the identity provider, rotate secrets, and disable accounts in this app when staff leave. OAuth does not replace application authorization or PostgreSQL RLS.

## Barcode camera

The camera API requires explicit user permission and a secure context (HTTPS, or localhost during development). The browser/device must have a supported camera. If camera access is denied or unavailable, use the manual barcode field.

## Tests and checks

Compile checks:

```bash
python -m compileall -q .
```

Database/RLS smoke testing should be performed against a disposable PostgreSQL database before deployment. Verify at minimum:

- a non-admin cannot query another department's files even with a hand-written SQL query;
- a non-admin cannot delete a file row or set `deleted_at`/`deleted_by`;
- a non-admin cannot register/deactivate users or review requests;
- a user cannot read another user's notifications or requests;
- administrators can review requests and soft-delete records;
- audit rows cannot be updated or deleted;
- the Streamlit app connects only as `dfts_app`.

## Important operational work before production

- Configure TLS at the reverse proxy and secure Streamlit's external URL.
- Store credentials in a secret manager and rotate all bootstrap passwords.
- Set backup, restore, retention, incident response and monitoring procedures.
- Test OAuth callback behavior and camera scanning in the actual deployment browser/device.
- Conduct an independent security review and RLS penetration test.
- If the existing SQLite installation contains records, complete and validate the one-time data migration before switching users over.
