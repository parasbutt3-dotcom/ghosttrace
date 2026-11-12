# Installation

## Development (SQLite default)

SQLite is the default for local development only. No external database is required.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ../.env.example ../.env  # edit values
# generate token key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Register an account, then connect integrations.

## Google OAuth setup

1. Create OAuth client in Google Cloud Console.
2. Add redirect URI: http://localhost:8000/api/v1/auth/google/callback
3. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.
4. In dashboard: Integrations -> Connect Google Account.

## Production (PostgreSQL default)

PostgreSQL is the documented production default. SQLite must not be used for production deployments. The compose stack provides a ready Postgres service.

### 1. Configure environment

Copy `.env.example` to `.env` and set production values, including:

```env
APP_ENV=production
DEBUG=false
DATABASE_URL=postgresql+psycopg2://ghosttrace:ghosttrace@db:5432/ghosttrace
REDIS_URL=redis://redis:6379/0
SECRET_KEY=<long-random-string>
TOKEN_ENCRYPTION_KEY=<generated-fernet-key>
```

### 2. Start the stack

```bash
cp .env.example .env  # edit values
docker compose up -d --build
```

### 3. Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

(or locally: `cd backend && alembic upgrade head` with `DATABASE_URL` pointing at Postgres)

### 4. Backups and restore

Nightly backup (retention 7 days):

```bash
./infra/backup.sh
```

Restore from a backup file:

```bash
./infra/restore.sh backups/ghosttrace_YYYYMMDD_HHMMSS.sql.gz
```

Override defaults via environment variables (`POSTGRES_USER`, `POSTGRES_DB`, `BACKUP_DIR`, `RETENTION_DAYS`, `DB_CONTAINER`).

### 5. CI / Postgres test run

The backend test suite can be run against a Postgres connection string for CI without changing the default (SQLite) test loop:

```bash
DATABASE_URL=postgresql+psycopg2://ghosttrace:ghosttrace@localhost:5432/ghosttrace python -m pytest -q
```

The default `python -m pytest -q` (run from `backend/`) uses SQLite and does not require a live Postgres instance.
