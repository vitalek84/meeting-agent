import time
from typing import Any, Tuple, Type

# Assume pydantic and selenium are installed:
# pip install pydantic selenium
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from meeting_agent.settings import Settings


# Helper function to map strategy string to By enum
def _get_by_strategy(strategy_string: str) -> Type[By]:
    """Maps a strategy string to the selenium.webdriver.common.by.By enum."""
    strategy_map = {
        "id": By.ID,
        "name": By.NAME,
        "xpath": By.XPATH,
        "link text": By.LINK_TEXT,
        "partial link text": By.PARTIAL_LINK_TEXT,
        "tag name": By.TAG_NAME,
        "class name": By.CLASS_NAME,
        "css selector": By.CSS_SELECTOR,
    }
    by_strategy = strategy_map.get(strategy_string.lower())
    if by_strategy is None:
        raise ValueError(
            f"Unknown locator strategy: {strategy_string}. Supported strategies: {list(strategy_map.keys())}"
        )
    return by_strategy


# --- 2. Implement the GoogleLoginAutomation Class ---


class GoogleLoginAutomation:
    """
    Automates the Google sign-in process using Selenium and defined settings.
    Now accepts an external WebDriver instance.
    """

    def __init__(self, settings: Settings, driver: WebDriver):
        """
        Initializes the automation instance with settings and an existing WebDriver.

        Args:
            settings: An instance of the Settings class (pydantic BaseSettings).
            driver: An initialized Selenium WebDriver instance.
        """
        self.settings: Settings = settings
        self.driver: WebDriver = driver  # Receive driver as argument
        self._locators: dict[str, Tuple[By, str]] = {}
        self.driver.implicitly_wait(
            self.settings.implicit_wait_seconds
        )  # set implicit wait on passed object.

    # Context manager functionality is removed since the driver is managed externally.
    # The external code is now responsible for handling the driver's lifecycle.

    def prepare_locators(self) -> None:
        """Converts locator strings from settings to By tuples."""
        try:
            self._locators = {
                "email_input": (
                    _get_by_strategy(self.settings.email_input_strategy),
                    self.settings.email_input_value,
                ),
                "email_next_button": (
                    _get_by_strategy(self.settings.email_next_button_strategy),
                    self.settings.email_next_button_value,
                ),
                "password_input": (
                    _get_by_strategy(self.settings.password_input_strategy),
                    self.settings.password_input_value,
                ),
                "password_next_button": (
                    _get_by_strategy(self.settings.password_next_button_strategy),
                    self.settings.password_next_button_value,
                ),
                "logged_in_indicator": (
                    _get_by_strategy(self.settings.logged_in_indicator_strategy),
                    self.settings.logged_in_indicator_value,
                ),
            }
            print("Locators prepared.")
        except ValueError as e:
            print(f"Error preparing locators: {e}")
            # self.quit() # Don't quit, driver is managed externally
            raise  # Re-raise the exception

    def wait_for_element(
        self,
        locator: Tuple[By, str],
        condition: callable = EC.visibility_of_element_located,
    ) -> Any:
        """Waits for an element based on a condition and returns it."""
        try:
            print(f"Waiting for element located by {locator[0]}: {locator[1]}...")
            element = WebDriverWait(
                self.driver, self.settings.explicit_wait_seconds
            ).until(condition(locator))
            print("Element found.")
            return element
        except TimeoutException:
            print(f"Timeout waiting for element located by {locator[0]}: {locator[1]}")
            raise
        except NoSuchElementException:
            print(f"Element not found: {locator[0]}: {locator[1]} after implicit wait")
            raise

    def login(self) -> None:
        """Performs the automated Google login sequence."""
        if not self.driver or not self._locators:
            print("WebDriver not initialized or locators not prepared.")
            # This shouldn't happen if using the context manager correctly,
            # but add a check for safety.
            raise RuntimeError("Automation instance not properly set up.")

        try:
            # 1. Navigate to the login page
            print(f"Navigating to {self.settings.login_url}")
            self.driver.get(self.settings.login_url)

            # 2. Enter email
            email_input = self.wait_for_element(self._locators["email_input"])
            print("Entering email...")
            email_input.send_keys(self.settings.google_email)

            # 3. Click email Next button
            next_button_email = self.wait_for_element(
                self._locators["email_next_button"], EC.element_to_be_clickable
            )
            print("Clicking Next after email...")
            next_button_email.click()

            # TODO FIX Issiue with Relogin w/o password
            # 4. Enter password (this appears on the next page)
            password_input = self.wait_for_element(self._locators["password_input"])
            print("Entering password...")
            password_input.send_keys(self.settings.google_password)

            # 5. Click password Next button
            next_button_password = self.wait_for_element(
                self._locators["password_next_button"], EC.element_to_be_clickable
            )
            print("Clicking Next after password...")
            next_button_password.click()

            print("Login sequence steps executed.")

            time.sleep(3)  # Small final pause

            print(f"Current URL after login attempt: {self.driver.current_url}")

        except (TimeoutException, NoSuchElementException) as e:
            print(f"Automation failed: Could not interact with an element. {e}")
            raise  # Re-raise the exception

        except Exception as e:
            print(f"An unexpected error occurred during login: {e}")
            raise  # Re-raise the exception

        ### NEW ###

    def is_logged_in(self) -> bool:
        """
        Checks if the user is already logged into Google.

        Returns:
            True if logged in, False otherwise.
        """
        print(f"Checking login status at {self.settings.login_check_url}...")
        try:
            self.driver.get(self.settings.login_check_url)
            # Use a shorter timeout for the check, as the page should load quickly.
            self.wait_for_element(self._locators["logged_in_indicator"])
            print("Login status: Logged IN.")
            return True
        except TimeoutException:
            print("Login status: Logged OUT.")
            return False

    def check_and_login(self) -> None:
        """
        Public method to ensure the user is logged in.
        It first checks the login status and only performs the login if necessary.
        """
        if self.is_logged_in():
            print("Session is active. Skipping login.")
            return
        print("Session is not active. Proceeding with login.")
        self.login()

    def quit(self) -> None:
        """
        This method does nothing in the new implementation, as the driver is managed externally.
        You must close driver out from `automation_driver.quit()` outside of GoogleLoginAutomation object call
        """
        print(
            "Warning: GoogleLoginAutomation.quit() is no longer used. The driver is managed externally, outside of GoogleLoginAutomation object"
        )
        # Does nothing


# --- 3. Example Usage ---

if __name__ == "__main__":
    # How to create settings:
    # 1. Define environment variables (GOOGLE_EMAIL, GOOGLE_PASSWORD, etc.)
    # 2. Create a .env file in the same directory with variables like:
    #    GOOGLE_EMAIL="your_email@gmail.com"
    #    GOOGLE_PASSWORD="your_password"
    #    # etc.
    # 3. Pydantic's BaseSettings will automatically load from environment or the .env file.

    print("Loading settings...")
    # Load settings from environment variables or a .env file
    automation_settings = Settings()
    print("Settings loaded.")

    # --- Create the WebDriver instance EXTERNALY ---
    # The GoogleLoginAutomation class will now take this as an argument
    browser = "chrome"  # Or "firefox", etc.
    driver = None
    try:
        if browser == "chrome":
            options = webdriver.ChromeOptions()
            if automation_settings.headless:
                options.add_argument("--headless")
                options.add_argument("--no-sandbox")  # Recommended for headless
                options.add_argument(
                    "--disable-dev-shm-usage"
                )  # Recommended for headless
            driver = webdriver.Chrome(options=options)

        elif browser == "firefox":
            options = webdriver.FirefoxOptions()
            if automation_settings.headless:
                options.add_argument("--headless")
            driver = webdriver.Firefox(options=options)
        else:
            raise ValueError(f"Unsupported browser: {browser}")

        # --- Use GoogleLoginAutomation with the external driver ---
        automation = GoogleLoginAutomation(
            automation_settings, driver
        )  # Pass the driver here
        automation.prepare_locators()
        automation.login()

        # --- Now YOU are responsible for closing the driver ---
        print("Closing the WebDriver externally...")
        driver.quit()  # YOU need to close Driver out side of GoogleLoginAutomation object.
    except Exception as e:
        print(f"An error occurred: {e}")
        if driver:
            driver.save_screenshot("error_screenshot.png")
            driver.quit()
    finally:
        print("Script execution completed.")
