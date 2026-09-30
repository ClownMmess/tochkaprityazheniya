from pydantic import model_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore",hide_input_in_errors=True)
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://app:local_dev_only@db:5432/app"
    max_bot_token: str = ""
    max_bot_name: str = ""
    max_webhook_secret: str = ""
    session_secret: str = ""
    public_app_url: str = "http://localhost:8080"
    llm_base_url: str = "http://host.docker.internal:11434/v1"
    llm_model: str = "qwen2.5:7b"
    llm_enabled: bool = False
    llm_timeout_seconds: int = 25
    catalog_refresh_enabled: bool = True
    catalog_refresh_seconds: int = Field(default=21600,ge=300,le=604800)
    demo_mode: bool = False
    app_bindings_factory: str = "app.bindings:build"
    kudago_api_url: str = "https://kudago.com/public-api/v1.4"
    @model_validator(mode="after")
    def environment_safety(self):
        if self.app_env == "production":
            from urllib.parse import urlparse
            if self.demo_mode or len(self.session_secret)<32:
                raise ValueError("Production requires demo mode disabled and a session secret")
            if not self.max_bot_token or not self.max_bot_name or len(self.max_webhook_secret)<32:
                raise ValueError("Production requires MAX bot credentials and webhook secret")
            url=urlparse(self.public_app_url)
            if url.scheme!='https' or not url.hostname or url.hostname in {'localhost','127.0.0.1'}:
                raise ValueError("Production requires a public HTTPS application URL")
        return self
