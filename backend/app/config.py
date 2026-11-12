import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    APP_NAME: str = "GHOSTTRACE"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production-please-32chars-min"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'ghosttrace.db'}"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Comma-separated emails that are granted admin on registration (bootstrap).
    ADMIN_EMAILS: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    # Encryption key for OAuth tokens at rest (Fernet). Generate with:
    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    TOKEN_ENCRYPTION_KEY: str = ""

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    GOOGLE_SCOPES: str = "openid email profile"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Android companion shared secret (per-device keys stored in DB)
    ANDROID_API_KEY_HEADER: str = "X-Device-Key"

    # Data retention
    EVENT_RETENTION_DAYS: int = 90

    # Email verification (SMTP). When disabled (default dev), registration behaves
    # exactly as before and no verification email is sent.
    EMAIL_VERIFY_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FRONTEND_VERIFY_URL: str = ""

    # Background sync loop
    AUTO_SYNC_ENABLED: bool = True
    SYNC_INTERVAL_MINUTES: int = 60

    # Wazuh TLS verification
    WAZUH_VERIFY_SSL: bool = True
    WAZUH_CA_BUNDLE: str = ""

    # Observability (optional)
    SENTRY_DSN: str = ""

    def cors_list(self):
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def admin_emails_list(self):
        return [e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()]


settings = Settings()
