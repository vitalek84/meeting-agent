import asyncio
import logging
import shutil
import sys

import requests  # Add this import
from selenium.common import SessionNotCreatedException

from meeting_agent.gm_helper import GMPageParserAIv3
from meeting_agent.gm_login import GoogleLoginAutomation
from meeting_agent.gm_manager import DriverConfigurator, MeetConnectionController
from meeting_agent.schemas import MeetingProgress, StatusEnum
from meeting_agent.settings import settings


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    driver = None
    final_meet_link = None
    error_message = None

    # For the login logic testing
    # shutil.rmtree(settings.browser_profile_path)
    try:
        driver = DriverConfigurator.make_driver(settings)
    except SessionNotCreatedException:
        logging.error(
            "It seems browser session was closed with issue. Recreating profile!"
        )
        shutil.rmtree(settings.browser_profile_path)
        logging.info(
            f"Profile {settings.browser_profile_path} was removed! Trying to start driver again!"
        )
        driver = DriverConfigurator.make_driver(settings)
    try:
        glogin_automation = GoogleLoginAutomation(settings, driver)

        # We will now create a new meeting by default if no link is provided.
        # The logic inside MeetConnectionController already handles this.
        meeting_host = True
        if settings.gm_link:
            meeting_host = False

        controller = MeetConnectionController(
            driver,
            glogin_automation,
            GMPageParserAIv3(settings),
            settings,
            settings.gm_link,
            meeting_host=meeting_host,
        )
        await controller.run()

    except Exception as e:
        logging.error(f"An unhandled exception occurred: {e}", exc_info=True)
        meet_progress = MeetingProgress(
            status=StatusEnum.error,
            user_id=settings.user_id,
            error="Something went wrong with an agent. Please try again!",
        )
        requests.post(str(settings.callback_url), json=meet_progress.model_dump())
        if driver:
            driver.quit()


if __name__ == "__main__":
    asyncio.run(main())
