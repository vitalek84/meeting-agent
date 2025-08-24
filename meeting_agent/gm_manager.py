# import required modules
import asyncio
import logging
import os
import sys
import time
from typing import Optional, List

import pyautogui
import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from meeting_agent.gm_helper import GMPageParserAIv3, ScreenActions, ControlFinder
from meeting_agent.gm_login import GoogleLoginAutomation
from meeting_agent.live_assistant import AssistantLive
from meeting_agent.schemas import GoogleMeetState, PageControls, ControlElem, MeetingProgress, StatusEnum
from meeting_agent.settings import Settings, settings


class MeetControllerBase:
    def __init__(
            self, driver, glogin_automation, gm_parser: GMPageParserAIv3,
            settings: Settings, gm_link: str = None, restart_tries=7, wait_approval_tries=7, meeting_host=False):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.driver = driver
        self.gm_parser = gm_parser
        self.settings = settings
        self.glogin_automation = glogin_automation
        self.current_state = None
        self.meeting_host = meeting_host
        self.gm_link = gm_link
        self.stopped = False
        self.restart_tries = restart_tries
        self.wait_approval_tries = wait_approval_tries
        self.states_history = []
        self.live_assistant = AssistantLive(settings)
        self.error_msg = None

    async def set_state(self, new_state):
        self.logger.info(f"[State Transition] {type(self.current_state).__name__} → {type(new_state).__name__}")
        self.current_state = new_state
        self.states_history.append(self.current_state)
        await self.current_state.enter()

    async def notify_management_back(self, status: StatusEnum):
        if self.settings.user_id:
            try:
                meet_progress = MeetingProgress(
                    user_id=self.settings.user_id,
                    status=status,
                    gm_link=self.gm_link if status == StatusEnum.meeting_ready else None
                )
                # StatusEnum.waiting_for_approve
                response = requests.post(settings.callback_url, json=meet_progress.model_dump())
                if response.status_code != 200:
                    self.logger.warning(f"Got error from callback_url: {response.text}")
            except Exception as ex:
                self.logger.info(f"Can't notify connection management API. Error: {str(ex)}")


class MeetConnectionController(MeetControllerBase):

    async def run(self):
        self.logger.info(f"Starting MeetController. Google Account: {self.settings.google_email}")
        if self.gm_link:
            # Notifying our management backend
            await self.notify_management_back(StatusEnum.connecting_to_the_meeting)
            self.current_state = JoinCurrentMeetingState(self)
        else:
            # Notifying our management backend
            await self.notify_management_back(StatusEnum.new_meeting_starting)
            self.current_state = LandingPageState(self)
        self.states_history.append(self.current_state)
        await self.current_state.enter()


class MeetInMeetingController(MeetControllerBase):
    def __init__(
            self, driver, glogin_automation, gm_parser: GMPageParserAIv3,
            settings: Settings, gm_link:str = None, restart_tries=3, meeting_host=False):
        super().__init__(driver, glogin_automation, gm_parser, settings, gm_link,
                         restart_tries=restart_tries, meeting_host=meeting_host)


    async def run(self):
        self.logger.info("Starting MeetInMeetingController")
        # Notifying our management backend
        self.gm_link = self.driver.current_url
        await self.notify_management_back(StatusEnum.meeting_ready)
        self.current_state = MeetingSubMachineStart(self)
        self.states_history.append(self.current_state)
        await self.current_state.enter()


class MeetState:
    def __init__(self, controller: Optional[MeetInMeetingController|MeetConnectionController], retry: int = 0):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.controller = controller
        self.cur_page = None
        self.retry = retry

    async def enter(self):
        raise NotImplementedError

# Sub Machine for meeting
class MeetingSubMachineStart(MeetState):
    async def enter(self):
        self.controller.cur_page = await self.controller.gm_parser.run()
        # Click on the screen to remove annoying Gemini advertisement in google meet.
        ScreenActions.click((640, 280))

        if self.controller.cur_page.state == GoogleMeetState.google_meet_meeting_page:
            # asyncio.create_task(self.controller.live_assistant.run())
            await self.controller.set_state(MeetingSubMachineInMeeting(self.controller))


class MeetingSubMachineInMeeting(MeetState):

    async def do_admit_all_sequence(self) -> bool:
        self.logger.info("Trying admit all. Screen actions sequence")
        result = ScreenActions.click_icon('admit_all.png')
        if not result:
            result = ScreenActions.click_icon_with_shift('deny_all_admit_all.png', 45)
        if not result:
            return False
        await asyncio.sleep(1)
        result = ScreenActions.click_icon_with_shift('cancel_admit.png', 40)
        return result
        # ScreenActions.click_icon('admit_white.png')


    async def admit_from_popup(self):
        # ScreenActions.click(control_elem)
        result = ScreenActions.click_icon('view.png')
        if result:
        # self.controller.cur_page = await self.controller.gm_parser.run()
        # for elem in self.controller.cur_page.elements:
        #     if elem.label == PageControls.admit_all_button.value:
            await self.do_admit_all_sequence()

    async def admit_participant(self, finder: ControlFinder) -> Optional[bool|None]:

        logging.info("trying admit via pyautogui icon search...")
        result = ScreenActions.click_icon_with_shift('admit_view.png', -15)
        if result:
            logging.info("Found admit button. Admitted via pyautogui icon search...")
            return True
        element, confidence = finder.find_element('someone_wants_to_join_this_call_admit_button')
        if element and confidence >= 80.00:
            self.logger.info("Found someone_wants_to_join_this_call_admit_button. Pressing admit button")
            # Because we don't know was our try successful or not we continue searching elements and try to admit with other logic.
            ScreenActions.click(element)

        element, confidence = finder.find_element('meet_callcontrol_viewparticipantsbutton',
                                                  aliases=['meet_call_controls_view_all_participants',
                                                           'meet_callcontrol_viewparticipants_button',
                                                           'meet_callcontrol_view_participants_button'
                                                           'someone_wants_to_join_this_call_view',
                                                           'call_control_view_button',
                                                           'someone_wants_to_join_this_call_view_button',
                                                           'meet_incoming_call_view_button',
                                                           'call_control_someone_wants_to_join_this_call_view_button',
                                                           'meet_someone_wants_to_join_this_call_view_button'])


        if element and confidence >= 60.00:
            self.logger.info("Found that someone wants to join the call. We need to open people popup")
            ScreenActions.click(element)
            await asyncio.sleep(1)
            self.logger.info("Trying to admit via admit all pyautogui sequence.")
            return await self.do_admit_all_sequence()


        element, confidence = finder.find_element('people_admit_button')
        if element and confidence > 66.00:
            self.logger.info("People popup: found that someone wants to join the call. Pressing admit personal")
            ScreenActions.click(element)

        element, confidence = finder.find_element('people_popup_admit_all_button',
                                                  aliases=[
                                                      'people_admit_all_button',
                                                      'people_admit_all',
                                                  ])
        if element and confidence > 75.00:
            self.logger.info("People popup: found that someone wants to join the call. Pressing people_popup_admit_all_button")
            ScreenActions.click(element)
            await asyncio.sleep(1)
            result = ScreenActions.click_icon_with_shift('cancel_admit.png', 40)
            if result:
                return True

        element, confidence = finder.find_element('admit_all_admit_button',
                                                  # aliases=[
                                                  #     'people_admit_all_button',
                                                  #     'people_admit_all',
                                                  #   ]
                                                  )
        if confidence == 100.00:
            self.logger.info("Admit all: Found that someone wants to join the call. Pressing admit_all_admit_button")
            ScreenActions.click(element)

        await self.admit_from_popup()
        return None

    async def leave_call(self, finder: ControlFinder) -> Optional[bool | None]:
        element, confidence = finder.find_element('meet_call_control_end_call_button',
                                                  aliases=[
                                                      'meet_leave_call_button',
                                                      'meet_call_control_leave_call_button'
                                                        ])
        if confidence >= 70.00:
            self.logger.info("Trying to leave the call via recognized button")
            ScreenActions.click(element)
        else:
            self.logger.warning("Call leaving requested but we can't find leave button")
        # Fallback logic
        ScreenActions.click_icon('leave_call.png')



    async def enter(self):

        # TODO Should be implemented as timer in separate task
        alone_in_the_call_timer = 0

        getting_ready_error_count = 0
        try:
            while True:
                self.controller.cur_page = await self.controller.gm_parser.run()
                if self.controller.cur_page.state == GoogleMeetState.google_meet_meeting_page:
                    self.logger.info(f"cur page object: {self.controller.cur_page}")
                    if self.controller.live_assistant.leave_call_event.is_set():
                        finder = ControlFinder(self.controller.cur_page.elements)
                        await self.leave_call(finder)
                        self.logger.info("Leave call asked!")
                        break

                    if self.controller.cur_page.alone_in_the_call:
                        alone_in_the_call_timer+=1
                        # TODO Move to the settings
                        if alone_in_the_call_timer >= 120:
                            finder = ControlFinder(self.controller.cur_page.elements)
                            await self.leave_call(finder)
                            self.logger.info("I am too long alone in this call! Quitting")
                            break
                    if self.controller.meeting_host:
                        finder = ControlFinder(self.controller.cur_page.elements)
                        # closing unnecessary windows.
                        element, confidence = finder.find_element('your_meeting_is_ready_close_button',
                                                                  aliases=['your_meeting_is_ready_close'])
                        if confidence == 100.00:
                            ScreenActions.click(element)
                        self.logger.info("Launching admit logic...")
                        await self.admit_participant(finder)
                    await asyncio.sleep(1)
                elif self.controller.cur_page.state == GoogleMeetState.google_meet_meeting_connection_page_getting_ready:
                    # Sometimes model detects this state rather than correct google_meet_meeting_page.
                    # We should wait and give it another shot.
                    if getting_ready_error_count > 2:
                        self.logger.error("We saw google_meet_meeting_connection_page_getting_ready more than 3 times. "
                                          "It seems there are some issues with a call ")
                        break
                    self.logger.warning("It seems we are in the call but google_meet_meeting_connection_page_getting_ready "
                                        "was detected")
                    getting_ready_error_count +=1
                else:
                    self.controller.error_msg = f"Unknown page state {self.controller.cur_page.state}. Closing connections!"
                    break
        except Exception as ex:
            self.logger.error(f"Something went wrong in the MeetingSubMachineInMeeting state. Error: {ex}")
            self.controller.error_msg = str(ex)
        await self.controller.set_state(MeetingSubMachineStop(self.controller))


class MeetingSubMachineStop(MeetState):
    async def enter(self):
        self.controller.live_assistant.stop_event.set()
        self.logger.info("Stopping MeetingSubMachine - quiting from the meeting")


class PermitMicrophone(MeetState):

    async def enter(self):
        await asyncio.sleep(2)
        self.controller.cur_page = await self.controller.gm_parser.run()
        if self.controller.cur_page.state == GoogleMeetState.google_meet_allow_microphone:
            for elem in self.controller.cur_page.elements:
                if elem.label in (PageControls.use_microphone_and_camera.value, PageControls.allow_while_visiting_the_site.value):
                    ScreenActions.click(elem)
                    await self.controller.set_state(PermitMicrophone(self.controller))
                    break
            else:
                await self.controller.set_state(LandingPageState(self.controller))
        else:
            if self.controller.gm_link:
                await self.controller.set_state(JoinCurrentMeetingState(self.controller))
            else:
                await self.controller.set_state(InMeeting(self.controller))


class InMeeting(MeetState):
    MAX_RETRIES = 3

    async def enter(self):
        await asyncio.sleep(3)
        self.controller.cur_page = await self.controller.gm_parser.run()
        self.logger.debug(f"cur page object: {self.controller.cur_page}")
        if self.controller.cur_page.state == GoogleMeetState.google_meet_meeting_page:


            sub_controller = MeetInMeetingController(
                self.controller.driver,
                self.controller.glogin_automation,
                self.controller.gm_parser,
                settings=settings,
                gm_link=self.controller.gm_link,
                meeting_host=self.controller.meeting_host
            )
            await sub_controller.run()
        elif self.controller.current_state == GoogleMeetState.google_meet_meeting_connection_page_getting_ready:
            self.logger.warning("It seems we are in the call but google_meet_meeting_connection_page_getting_ready "
                                "was detected")
            if self.retry < self.MAX_RETRIES:
                self.retry += 1
                await asyncio.sleep(2)
                await self.controller.set_state(InMeeting(self.controller, retry=self.retry))
            else:
                self.controller.error_msg = ("Current state is google_meet_meeting_connection_page_getting_ready "
                                             "but should be google_meet_meeting_page "
                                             "Stopping the system!"
                                             f"Page state dump: {self.controller.current_state}")
                await self.controller.set_state(StopState(self.controller))
        elif self.controller.cur_page.state == GoogleMeetState.google_meet_allow_microphone:
            await self.controller.set_state(PermitMicrophone(controller=self.controller))
        elif self.controller.cur_page.state == GoogleMeetState.google_meet_loading_call:
            await self.controller.set_state(InMeeting(controller=self.controller))
        else:
            await self.controller.set_state(LandingPageState(controller=self.controller))


class StopState(MeetState):

    async def enter(self):
        if self.controller.error_msg:
            # TODO Add error description to notify_management_back
            await self.controller.notify_management_back(status=StatusEnum.error)
        self.logger.info(f"State chain {self.controller.states_history}")
        self.logger.warning("Stopping google meet manager")
        self.controller.driver.quit()
        self.controller.stopped = True
        sys.exit(0)


class GoogleLoginState(MeetState):
    MAX_RETRIES = 4

    async def enter(self):
        self.logger.debug(f"Entering to state: {self.__class__.__name__}")
        automation = self.controller.glogin_automation # Pass the driver here
        automation.prepare_locators()
        automation.login()
        self.controller.cur_page = await self.controller.gm_parser.run()
        if self.controller.cur_page.state == GoogleMeetState.google_chrome_workspace_popup:
            for elem in self.controller.cur_page.elements:
                if elem.label == PageControls.cancel.value:
                    ScreenActions.click(elem)
                    if self.controller.gm_link:
                        await self.controller.set_state(JoinCurrentMeetingState(self.controller))
                    else:
                        await self.controller.set_state(LandingPageState(self.controller))
                    break
            else:
                self.controller.error_msg = "Unhandled state. It seems we saw google_chrome_workspace_popup after login. But we can't skip it."
                self.logger.error(self.controller.error_msg)
                await self.controller.set_state(StopState(self.controller))
        elif self.controller.cur_page.state == GoogleMeetState.google_sign_in_to_chrome:
            for elem in self.controller.cur_page.elements:
                if elem.label == PageControls.cancel.value:
                    ScreenActions.click(elem)
                    if self.controller.gm_link:
                        await self.controller.set_state(JoinCurrentMeetingState(self.controller))
                    else:
                        await self.controller.set_state(LandingPageState(self.controller))
                    break
            else:
                self.controller.error_msg = "Unhandled state. It seems we saw google_sign_in_to_chrome after login. But we can't skip it."
                self.logger.error(self.controller.error_msg)
                await self.controller.set_state(StopState(self.controller))
        elif not self.controller.cur_page.logged_in:
            if self.MAX_RETRIES:
                self.MAX_RETRIES -= 1
                await asyncio.sleep(2)
                await self.controller.set_state(GoogleLoginState(self.controller))
            else:
                self.controller.error_msg = "Can't login"
                self.logger.error(self.controller.error_msg)
                await self.controller.set_state(StopState(self.controller))
        else:
            if self.MAX_RETRIES:
                self.MAX_RETRIES -= 1
                await asyncio.sleep(2)
                if self.controller.gm_link:
                    await self.controller.set_state(JoinCurrentMeetingState(self.controller))
                else:
                    await self.controller.set_state(LandingPageState(self.controller))
            else:
                self.controller.error_msg = f"Something went very wrong. Metadata of page: {self.controller.cur_page}"
                self.logger.error(self.controller.error_msg)
                await self.controller.set_state(StopState(self.controller))

class JoinCurrentMeetingAwaitApprovalState(MeetState):

    async def enter(self):
        self.logger.debug(f"Entering to state: {self.__class__.__name__}")

        self.controller.cur_page = await self.controller.gm_parser.run()
        if self.controller.wait_approval_tries == 0:
            # Stop StateMachine from JoinCurrentMeetingState. Do nothing here.
            self.logger.warning("We are waiting approval too long")
        if  self.controller.cur_page.state ==  GoogleMeetState.google_meet_awaiting_approval_page:
            await asyncio.sleep(3)
            self.controller.wait_approval_tries -= 1
            await self.controller.set_state(JoinCurrentMeetingAwaitApprovalState(self.controller))
        elif self.controller.cur_page.state == GoogleMeetState.google_meet_allow_microphone:
            await self.controller.set_state(PermitMicrophone(self.controller, retry=self.retry))
        elif self.controller.cur_page.state == GoogleMeetState.google_meet_meeting_connection_page:
            await asyncio.sleep(3)
            self.controller.wait_approval_tries -= 1
            await self.controller.set_state(JoinCurrentMeetingAwaitApprovalState(self.controller))
        elif self.controller.cur_page.state == GoogleMeetState.google_meet_loading_call:
            await asyncio.sleep(2)
            await self.controller.set_state(InMeeting(self.controller))
        elif self.controller.cur_page.state == GoogleMeetState.google_meet_meeting_page:
            await self.controller.set_state(InMeeting(self.controller))


class CreateNewMeetingState(MeetState):

    async def enter(self):
        self.logger.debug(f"Entering to state: {self.__class__.__name__}")
        await asyncio.sleep(1.5)
        self.controller.cur_page = await self.controller.gm_parser.run()
        if (
                self.controller.cur_page.state == GoogleMeetState.google_meet_initial_page
                and self.controller.cur_page.logged_in):
            for elem in self.controller.cur_page.elements:
                if elem.label == PageControls.start_an_instant_meeting.value:
                    ScreenActions.click(elem)
                    await self.controller.set_state(InMeeting(self.controller))
                    break
            else:
                await self.controller.set_state(LandingPageState(self.controller))


class JoinCurrentMeetingState(MeetState):
    MAX_RETRIES = 5


    # TODO Check Timeouts
    async def enter(self):
        self.logger.debug(f"Entering to state: {self.__class__.__name__}")
        self.controller.restart_tries -= 1
        # We start live assistant on early stages because it takes some time to start it...
        if not self.controller.live_assistant.running:
            asyncio.create_task(self.controller.live_assistant.run())
        self.controller.driver.get(self.controller.gm_link)
        await asyncio.sleep(1)
        self.controller.cur_page = await self.controller.gm_parser.run()
        if self.controller.restart_tries == 0:
            self.controller.error_msg = "Too many retries in JoinCurrentMeetingState"
            self.logger.error(self.controller.error_msg)
            await self.controller.set_state(StopState(self.controller))
        elif (
                self.controller.cur_page.state == GoogleMeetState.google_meet_meeting_connection_page
                and  self.controller.cur_page.logged_in):
            for elem in self.controller.cur_page.elements:
                if elem.label == PageControls.join_meeting.value:
                    ScreenActions.click(elem)
                    await self.controller.set_state(JoinCurrentMeetingAwaitApprovalState(self.controller))
                    break

        elif self.controller.cur_page.state == GoogleMeetState.google_meet_allow_microphone:
            await self.controller.set_state(PermitMicrophone(self.controller, retry=self.retry))
        elif (self.controller.cur_page.state == GoogleMeetState.google_meet_meeting_connection_page_getting_ready
                and  self.controller.cur_page.logged_in):
            if self.retry < self.MAX_RETRIES:
                self.retry += 1
                await asyncio.sleep(2)
                await self.controller.set_state(JoinCurrentMeetingState(self.controller, retry=self.retry))
            else:
                self.logger.warning("Something went wrong we hang in "
                                    "{GoogleMeetState.google_meet_meeting_connection_page_getting_ready} state "
                                    "Returning to the landing page.")
                await self.controller.set_state(LandingPageState(self.controller))

        elif not self.controller.cur_page.logged_in:
            await self.controller.set_state(GoogleLoginState(self.controller))

        elif self.controller.cur_page.state == GoogleMeetState.google_meet_unknown_page:
            self.logger.debug(f"We are in unknow state (page): {self.controller.cur_page}")
            await self.controller.set_state(JoinCurrentMeetingState(self.controller))
        else:
            self.logger.warning(f"Can't find proper new state. Retrying to connect to the meeting")
            await self.controller.set_state(JoinCurrentMeetingState(self.controller))

        await self.controller.set_state(StopState(self.controller))


class LandingPageState(MeetState):


    async def enter(self):
        self.logger.debug(f"Entering to state: {self.__class__.__name__}")
        self.controller.restart_tries -= 1
        self.controller.driver.get("https://meet.google.com/")
        self.controller.driver.implicitly_wait(2)
        self.controller.cur_page = await self.controller.gm_parser.run()
        self.logger.info(f"Current page state: {self.controller.cur_page}")
        if self.controller.restart_tries == 0:
            self.controller.error_msg = "Too many retries in LandingPageState"
            self.logger.error(self.controller.error_msg)
            await self.controller.set_state(StopState(self.controller))

        elif (                self.controller.cur_page.state == GoogleMeetState.google_meet_initial_page
                and self.controller.cur_page.logged_in):
            # We start live assistant on early stages because it takes some time to start it...
            if not self.controller.live_assistant.running:
                asyncio.create_task(self.controller.live_assistant.run())

            if self.controller.gm_link:
                await self.controller.set_state(JoinCurrentMeetingState(self.controller))
            else:
                self.logger.info("google_meet_initial_page OK")
                self.logger.info(f"Creating new meeting")
                for elem in self.controller.cur_page.elements:
                    if elem.label == PageControls.new_meeting_button.value:
                        ScreenActions.click(elem)
                        await self.controller.set_state(CreateNewMeetingState(self.controller))
                        break
                else:
                    await self.controller.set_state(LandingPageState(self.controller))

        elif not self.controller.cur_page.logged_in:
            await self.controller.set_state(GoogleLoginState(self.controller))
        else:
            await self.controller.set_state(LandingPageState(self.controller))

        if not self.controller.stopped:
            await self.controller.set_state(StopState(self.controller))


class DriverConfigurator:

    @staticmethod
    def make_driver(settings: Settings):
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument(f"--user-data-dir={settings.browser_profile_path}")
        chrome_options.add_argument("--allow-running-insecure-content")
        return webdriver.Chrome(options=chrome_options)


