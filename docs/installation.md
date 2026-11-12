# Installation

## Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ../.env.example ../.env  # edit values
# generate token key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
uvicorn app.main:app --reload --port 8000
```

## Frontend

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

## Docker

```bash
cp .env.example .env  # edit
docker compose up --build
```
