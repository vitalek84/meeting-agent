from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from yarl import URL

BASE_DIR = Path(__file__).resolve().parent.parent


class GoogleAccount(BaseModel):
    """Represents a single Google account's credentials."""

    email: str = Field(..., description="Google Account Email")
    password: str = Field(..., description="Google Account Password")
    name: Optional[str] = Field(
        default=None,
        description="Account full name. Useful for an agent for "
        "understanding which person in the meeting is an agent",
    )


class Settings(BaseSettings):
    """Manages application settings."""

    host: str = "0.0.0.0"  # noqa S104
    port: int = 8000
    # quantity of workers for uvicorn
    workers_count: int = 1
    # Enable uvicorn reloading
    reload: bool = True

    manager_host_name: str = Field(
        default="connection-manager",
        description="Port for meeting creation progress callback",
    )
    manager_port: int = Field(
        default=8000, description="Port for meeting creation progress callback"
    )
    manager_path: str = Field(
        default="/internal/meeting_progress",
        description="Path for meeting creation progress callback",
    )

    @property
    def callback_url(self) -> URL:
        """
        Assemble database URL from settings.

        :return: database URL.
        """
        return URL.build(
            scheme="http",
            host=self.manager_host_name,
            port=self.manager_port,
            path=self.manager_path,
        )

    llm_backend: str = "google-gla"
    llm_model: str = "gemini-2.5-flash"

    @property
    def pydantic_ai_model(self) -> str:
        """Create full model like google-gla:gemini-2.5-flash.

        :return: pydantic model name with llm provider
        """
        return f"{self.llm_backend}:{self.llm_model}"

    google_accounts: List[GoogleAccount] = Field(
        default_factory=list, description="List of Google accounts"
    )

    app_root: Path = Field(
        default=Path("/app/src/"),
        description="App working directory inside container. "
        "IMPORTANT: Should be the same for connection"
        " manager and meeting agent apps. It uses for "
        "proper shared volumes mounting",
    )

    logs_root: Path = Field(
        default=Path("/app/logs/meeting-worker-logs"),
        description=(
            "Logs of meeting worker containers"
            "This is path should be available/mounted on the host machine"
        ),
    )
    browser_profile_volume: str = Field(
        default="meeting_bot_browser_profiles_volume",
        description="Volume name from docker compose. "
        "It should full name of the volume!",
    )

    browser_profile_relative: str = Field(
        default="browser_profiles",
        description="Path to the browser profiles directory. "
        "Defaults to 'browser_profiles' in the project root.",
    )

    @property
    def browser_profile_root(self) -> Path:
        """Browser profile root inside AI agent's machine."""
        return self.app_root / self.browser_profile_relative

    gemini_api_key: str = Field(..., description="Key for AI Agents")

    wireplumber_cache_src: Path = Field(
        default=BASE_DIR / "wireplumber" / "restore-stream"
    )
    wireplumber_cache_dst: Path = Field(
        default=Path("/root/.local/state/wireplumber/restore-stream")
    )

    technical_screenshots: Path = Field(
        default=Path("/tmp") / "technical_screenshots",  # noqa S108
        description="GMPageParserAI can save screenshots with debug information."
        " If we enable debug for this module. Screenshots will save to "
        "this folder on the host machine",
    )

    docker_image: str = Field(
        default="meeting-bot-v2", description="Google meet docker image"
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MANAGER_",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instantiate your settings
settings = Settings()
