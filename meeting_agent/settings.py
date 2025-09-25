import enum
from pathlib import Path
from tempfile import gettempdir
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from yarl import URL

TEMP_DIR = Path(gettempdir())


class LiveAgentRoles(enum.Enum):
    software_development_manager = "software_development_manager"
    psychologist = "psychologist"
    heart_of_gold_computer = "heart_of_gold_computer"
    business_coach = "business_coach"


class LogLevel(str, enum.Enum):
    """Possible log levels."""

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class Settings(BaseSettings):
    """
    Application settings.

    These parameters can be configured
    with environment variables.
    """

    log_level: LogLevel = LogLevel.INFO

    llm_backend: str = "google-gla"
    llm_model: str = "gemini-2.5-flash"

    @property
    def pydantic_ai_model(self) -> str:
        return f"{self.llm_backend}:{self.llm_model}"

    agent_role: LiveAgentRoles = LiveAgentRoles.software_development_manager
    # Google Login config
    google_email: str = Field(..., description="Google Account Email")
    google_password: str = Field(..., description="Google Account Password")

    gm_link: Optional[str] = Field(
        None,
        description="Google Meet Link if we want to connect to already created meeting",
    )
    # --- URLs ---
    login_url: str = "https://accounts.google.com/v3/signin/identifier?continue=https%3A%2F%2Faccounts.google.com%2F&followup=https%3A%2F%2Faccounts.google.com%2F&ifkv=AdBytiN_tWgXcYS5qjOE2GEVJi5iSG_JeR9UeD1JVqDMwFElPDfnACIGY7ohPHB-IJcgLhfEBH0aCQ&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin&dsh=S-484575432%3A1750291214318700"

    # --- WebDriver Configuration ---
    # browser: str = Field("chrome", description="Browser to use (e.g., 'chrome', 'firefox')")
    # webdriver_executable_path: str | None = Field(None, description="Path to the webdriver executable (optional)")
    headless: bool = Field(False, description="Run browser in headless mode (no GUI)")

    # --- Wait Times (in seconds) ---
    implicit_wait_seconds: int = Field(
        10, description="Implicit wait time for elements"
    )
    explicit_wait_seconds: int = Field(
        120, description="Explicit wait time for specific conditions"
    )

    browser_profile_path: str = "browser_profiles/chrome"

    # Login check configuration
    login_check_url: str = "https://myaccount.google.com/"

    # A reliable element that indicates a logged-in state.
    # The user's account icon in the top right is a good choice.
    # Its aria-label usually contains "Google Account:".
    logged_in_indicator_strategy: str = "xpath"
    logged_in_indicator_value: str = "//a[contains(@aria-label, 'Google Account')]"
    # End Logic check configuration

    # --- Locators (Define strategies as strings, map to By later) ---
    # Example: export EMAIL_INPUT_STRATEGY="id"
    # Example: export EMAIL_INPUT_VALUE="identifierId"
    email_input_strategy: str = Field(
        "id", description="Locator strategy for email input"
    )
    email_input_value: str = Field(
        "identifierId", description="Locator value for email input"
    )

    email_next_button_strategy: str = Field(
        "id", description="Locator strategy for email Next button"
    )
    email_next_button_value: str = Field(
        "identifierNext", description="Locator value for email Next button"
    )

    password_input_strategy: str = Field(
        "name", description="Locator strategy for password input"
    )
    password_input_value: str = Field(
        "Passwd", description="Locator value for password input"
    )

    password_next_button_strategy: str = Field(
        "id", description="Locator strategy for password Next button"
    )
    password_next_button_value: str = Field(
        "passwordNext", description="Locator value for password Next button"
    )

    # Meeting config
    max_alone_in_the_call_time: int = Field(
        120,
        description="Time that agaent may stay in the call alone and wait new participants",
    )

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

    user_id: Optional[str] = Field(
        default=None,
        description="User ID from connection management system. "
        "We use it for notify proper user about meeting "
        "creation/connecting process",
    )
    technical_screenshots: Path = Field(
        default=Path("/tmp") / "technical_screenshots",
        description="GMPageParserAI can save screenshots with debug information."
        " If we enable debug for this module. Screenshots will save to "
        "this folder. This folder should be mounted from host machine or "
        "as separate volume",
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

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="MEET_", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
