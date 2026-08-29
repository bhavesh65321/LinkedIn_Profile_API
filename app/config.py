from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    li_at: str = ""
    jsessionid: str = ""
    li_a: str = ""
    bcookie: str = ""
    bscookie: str = ""
    request_timeout_seconds: float = 25.0
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    @property
    def csrf_token(self) -> str:
        return self.jsessionid.strip().strip('"')

    @property
    def has_credentials(self) -> bool:
        return bool(self.li_at.strip() and self.jsessionid.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
