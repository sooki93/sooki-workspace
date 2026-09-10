from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: str = 'development'
    demo_mode: bool = True
    database_url: str = 'sqlite:///./studio.db'
    frontend_origin: str = 'http://localhost:3000'
    public_base_url: str = 'http://localhost:8000'
    token_encryption_key: str = ''
    operator_email: str = 'owner@local.test'
    operator_password_hash: str = ''
    cafe24_mall_id: str = ''
    cafe24_client_id: str = ''
    cafe24_client_secret: str = ''
    cafe24_redirect_uri: str = 'http://localhost:3000/api/cafe24/callback'
    cafe24_api_version: str = '2026-09-01'
    cafe24_shop_no: int = 1
    openai_api_key: str = ''
    openai_model: str = 'gpt-4.1'
    ai_provider: Literal['codex', 'openai'] = 'codex'
    demo_ai_enabled: bool = False
    codex_binary: str = 'codex'
    codex_timeout_seconds: int = Field(default=300, ge=15, le=900)
    storage_backend: str = 'local'
    upload_dir: str = './data/uploads'
    s3_endpoint_url: str = ''
    s3_bucket: str = ''
    s3_region: str = 'auto'
    s3_access_key_id: str = ''
    s3_secret_access_key: str = ''
    s3_addressing_style: Literal['auto','virtual','path'] = 'auto'

    @field_validator('database_url')
    @classmethod
    def use_installed_postgres_driver(cls, value):
        # Hosting providers supply plain PostgreSQL URLs; this app installs psycopg 3.
        for prefix in ('postgres://', 'postgresql://'):
            if value.startswith(prefix):
                return 'postgresql+psycopg://' + value[len(prefix):]
        return value

    def validate_runtime(self):
        if self.app_env == 'production':
            if self.demo_mode or not self.database_url.startswith('postgresql'):
                raise RuntimeError('Production requires PostgreSQL and DEMO_MODE=false')
            if not self.operator_password_hash or not self.token_encryption_key:
                raise RuntimeError('Production credentials not provisioned')
            if not self.frontend_origin.startswith('https://') or self.storage_backend != 's3':
                raise RuntimeError('Production requires HTTPS and S3-compatible storage')
settings = Settings()
