import asyncio
import base64
import datetime
import io
import logging
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import cv2
import mss
import numpy as np
import pyautogui
from google import genai
from google.genai import types
from google.genai.types import ThinkingConfig
from PIL import Image
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.settings import ModelSettings

from meeting_agent.schemas import (
    ControlElem,
    ControlElemList,
    GMState,
    GMStateWithControlElems,
    GoogleMeetState,
)
from meeting_agent.settings import LogLevel, Settings, settings


def parse_json(json_output: str):
    # Parsing out the markdown fencing
    lines = json_output.splitlines()
    for i, line in enumerate(lines):
        if line == "```json":
            json_output = "\n".join(
                lines[i + 1 :]
            )  # Remove everything before "```json"
            json_output = json_output.split("```")[
                0
            ]  # Remove everything after the closing "```"
            break  # Exit the loop once "```json" is found
    return json_output


class ScreenActions:
    @staticmethod
    def click(control_elem: Optional[ControlElem | Tuple[int, int]]):
        if isinstance(control_elem, tuple):
            x = control_elem[0]
            y = control_elem[1]
        else:
            x_min = control_elem.box_2d[1]
            y_min = control_elem.box_2d[0]
            x_max = control_elem.box_2d[3]
            y_max = control_elem.box_2d[2]
            x = int(x_min + (x_max - x_min) / 2)
            y = int(y_min + (y_max - y_min) / 2)
        # TODO add randomisation and more then one click
        pyautogui.click(x, y)

    @staticmethod
    def click_icon(icon_name: str) -> bool:
        try:
            pyautogui.click("./gm_control_elems/" + icon_name)
            return True
        except Exception as ex:
            print(f"Exception in ScreenActions: {ex}")
            return False

    @staticmethod
    def click_icon_with_shift(
        icon_name: str, shift_x: int = 0, shift_y: int = 0
    ) -> bool:
        try:
            icon_location = pyautogui.locateCenterOnScreen(
                "./gm_control_elems/" + icon_name, confidence=0.65
            )

            if icon_location:
                x, y = icon_location
                pyautogui.click(x + shift_x, y + shift_y)
            return True
        except Exception as ex:
            print(f"Exception in ScreenActions: {ex}")
            return False


class ScreenShotMaker:
    _singleton_instance = None

    def __new__(cls, *args, **kwargs):
        if cls._singleton_instance is None:
            cls._singleton_instance = super(ScreenShotMaker, cls).__new__(cls)
        return cls._singleton_instance

    def __init__(self):
        self.lock = Lock()
        # TODO Move to the settings
        self.mime_type = "image/jpeg"

    def _get_screen(self) -> Tuple[Image.Image, Tuple[int, int]]:
        with self.lock, mss.mss() as sct:
            monitor = sct.monitors[0]
            i = sct.grab(monitor)
            image_bytes = mss.tools.to_png(i.rgb, i.size)
            img = Image.open(io.BytesIO(image_bytes))
            image_size = img.size
            return img, image_size

    async def get_screen_pydantic(self) -> Tuple[BinaryContent, Tuple[int, int]]:
        screen, image_size = await asyncio.to_thread(self._get_screen)

        image_io = io.BytesIO()
        screen.save(image_io, format="jpeg")
        image_io.seek(0)
        image_bytes = image_io.read()
        return BinaryContent(image_bytes, media_type=self.mime_type), image_size

    async def get_screen_gemini(self, real_time: bool = False) -> Dict[str, Any]:
        screen, image_size = await asyncio.to_thread(self._get_screen)
        image_io = io.BytesIO()
        screen.save(image_io, format="jpeg")
        image_io.seek(0)
        image_bytes = image_io.read()
        if real_time:
            return {
                "mime_type": self.mime_type,
                "data": base64.b64encode(image_bytes).decode(),
            }
        return {
            "mime_type": self.mime_type,
            "data": base64.b64encode(image_bytes).decode(),
            "image": screen,
            "image_size": image_size,
        }


class ControlFinder:
    """
    A generalized class to find control elements with dynamic fallbacks,
    custom aliases, and a confidence score.
    """

    def __init__(self, elements: List[ControlElem]):
        """
        Initializes the ControlFinder with a list of ControlElem objects.

        Args:
            elements: A list of ControlElem objects to search through.
        """
        self.elements = elements

    def _generate_fallbacks(self, base_label: str) -> List[str]:
        """
        Generates a list of fallback labels from a base label.
        It avoids creating single-word fallbacks to prevent overly generic matches.

        For example, 'a_b_c_d' -> ['a_b_c', 'a_b']

        Args:
            base_label: The string to generate fallbacks from.

        Returns:
            A list of progressively shorter label parts.
        """
        parts = base_label.split("_")
        # Generate fallbacks from most specific to least, stopping at 2 parts.
        # This prevents fallbacks that are too generic (e.g., 'call').
        fallbacks = ["_".join(parts[:i]) for i in range(len(parts) - 1, 1, -1)]
        return fallbacks

    def find_element(
        self, base_label: str, aliases: List[str] = None
    ) -> Tuple[Optional[ControlElem | None], float]:
        """
        Finds a control element and returns it with a confidence score.

        The search priority is:
        1. Exact match with `base_label` (100% confidence).
        2. Exact match with any `aliases` (100% confidence).
        3. Partial match using generated fallbacks (confidence based on match length).

        Args:
            base_label: The primary label to search for.
            aliases: A list of alternative, high-priority labels.

        Returns:
            A tuple containing the found ControlElem (or None) and a confidence
            score (0.0 to 100.0).
        """
        # 1. High-confidence search (base_label and aliases)
        high_priority_labels = [base_label] + (aliases or [])
        for elem in self.elements:
            if elem.label in high_priority_labels:
                return (elem, 100.0)

        # 2. Fallback search with calculated confidence
        fallback_labels = self._generate_fallbacks(base_label)
        for fallback in fallback_labels:
            for elem in self.elements:
                if fallback in elem.label:
                    # Calculate confidence based on the ratio of lengths
                    confidence = round((len(fallback) / len(base_label)) * 100.0, 2)
                    return (elem, confidence)

        # 3. If no element is found at all
        return (None, 0.0)


class GMPagePrompts:
    find_gm_state_prompt = """
        Objective:
        Your task is to analyze Google Meet screenshots and accurately determine the current 
        state of the Google Meet call or related Google page, and infer the user's login status.

        Instructions for State Detection:

        Analyze the screenshot by identifying key visual cues, prominent text, interface layouts, 
        and the presence/absence of distinct UI components.

        google_login_page:

            Description: A page with a central form prompting for 'Email or phone or password' for initial Google account login.

            Distinguishing Cues: Large input field for account identification, "Next" button.

            Login Status: logged_in: False

        google_relogin_page:

            Description: A page where you need to re-confirm your identity or re-enter your password for a previously logged-in Google account.

            Distinguishing Cues: Often displays a user's profile picture or name with a password input field.

            Login Status: logged_in: False (or transitioning from logged in)

        google_chrome_workspace_popup:

            Description: A distinct modal popup or dialog box, often overlaying other content, related to Google Workspace.

            Distinguishing Cues: Contains text such as 'Set up a work profile...', 'Your organization will manage this profile', or similar corporate management Typically includes options to proceed or decline.
            
            Login Status: logged_in: True (implicitly, as it's within a browser/account context, even if the specific web page behind it might not be fully logged in yet)
        
        google_sign_in_to_chrome:
        
            Description: A distinct modal popup or dialog box, often overlaying other content, related to Chrome profile management
        
            Distinguishing Cues: Contains text such as 'Sign in to Chrome?', or similar profile setup messages. Typically includes options to proceed or decline.

            Login Status: logged_in: True (implicitly, as it's within a browser/account context, even if the specific web page behind it might not be fully logged in yet)
            
        google_meet_landing_page:

            Description: The public-facing introductory page for Google Meet.

            Distinguishing Cues: Displays general information about Google Meet. It lacks direct "New meeting" or "Join a meeting" controls. The top-right corner typically shows options to "Sign in" or indicates no active user session.

            Login Status: logged_in: False

        google_meet_initial_page:

            Description: The main Google Meet dashboard presented after a user has logged in.

            Distinguishing Cues: Prominent buttons for "New meeting" and "Join a meeting" (or "Join with a code"). Text like "Video calls and meetings for everyone" is often present. A user's circular profile icon is clearly visible in the top right.

            Login Status: logged_in: True

        google_meet_loading_call:

            Description: A transitional screen displayed immediately when connecting to a Google Meet call.

            Distinguishing Cues: Primarily a black screen with text like 'loading…' or 'joining…' centrally displayed.

            Login Status: logged_in: True (implicitly, as connection requires login)

        google_meet_meeting_connection_page_getting_ready:

            Description: The pre-meeting "green room" page where audio/video are tested, but the user is not yet in the meeting and don't see any Joining buttons. Be careful if you see ‘Leave call button’ or/and ‘Raise hand button’ or other call control button it is not this state it is highly likely google_meet_meeting_page but please check its description.

            Distinguishing Cues: Displays the user's self-preview video. Key text: "Getting ready...", "You're about to join," or "Check your audio and video." It often includes controls for mic/camera setup.

            Login Status: logged_in: True (implicitly)

        google_meet_meeting_connection_page:

            Description: The final prompt page before actively joining a meeting.

            Distinguishing Cues: Displays the user's self-preview video. Key text: "Ready to join?" Prominent buttons: "Ask to join" or "Join now" (or "Join"). In this status one of suggested buttons should be (text maybe slightly different with the same sence)

            Login Status: logged_in: True (implicitly)

        google_meet_awaiting_approval_page:

            Description: A page displayed when you are waiting for the meeting host to admit you.

            Distinguishing Cues: Text such as "Someone will let you in soon," "Waiting for host to admit you," or "Please wait, the meeting host will let you in." No active call controls visible. If you aren't sure which status you should select. Remember you don't have Join button here

            Login Status: logged_in: True (implicitly)

        google_meet_meeting_page:

            Description: An active Google Meet video conference call.

            Distinguishing Cues: Displays participant video feeds (or avatars/names), a visible control bar at the bottom (mute, camera, present, leave), and potentially open chat/participant side panels.

            Login Status: logged_in: True (implicitly)

            Special Condition (alone_in_the_call): If this state is detected, and you observe only one participant icon (usually the user's own, or an avatar/initials for self) and no other distinct participant video tiles or names, set alone_in_the_call to True. Otherwise, set it to False.

        google_meet_call_finishing_page:

            Description: A brief transitional screen seen just as a Google Meet call concludes or is disconnected.

            Distinguishing Cues: Simple text like "Call ended" or "Disconnecting..." displayed, typically without immediate "Rejoin" or "Return to home" options. This state is typically momentary.

            Login Status: logged_in: True (implicitly)

        google_meet_rejoin_page:

            Description: The page displayed after you have left a Google Meet meeting.

            Distinguishing Cues: Prominent text indicating the meeting has been left, e.g., "You've left the meeting," or "Meeting over." Features distinct buttons like "Rejoin" and "Return to home screen" (or "Go to home screen").

            Login Status: logged_in: True (implicitly)

        google_meet_allow_microphone:

            Description: An in-page prompt from Google Meet asking for specific permissions.

            Distinguishing Cues: A Google Meet interface element (not a browser-native pop-up) clearly asking for microphone access. Typically has "Allow" or "Block" buttons within the Google Meet page.

            Login Status: logged_in: True (implicitly, as it's part of a Meet flow)
            
        google_meet_cant_join_this_call:
            
            Description: The page with text like: You can't join this call/video call. It may looks like page when you quit from gogole meet. 
            
            Distinguishing Cues: Text like in description. But be careful text may be slightly different. 
            
            Login Status: logged_in: False - the main cause of this page - you aren't logged in. So logged_in should be False always!
            
        google_meet_unknown_page:

            Description: If the screenshot is clearly related to Google Meet or other Google services, but does not fit any of the defined states above.Please note if you see call control interface elements it shouldn't be this state

            Distinguishing Cues: Any Google-branded page that doesn't match specific descriptions.

            Login Status: Determine based on the presence of a user's account icon in the top right of the web page.

    General Rules for logged_in Detection:

        Primary Indicator: Look for a circular user account icon (often displaying an initial or profile picture) in the top right corner of the web page content (not the browser's UI). This is a standard indicator across most Google web services.

        Implicit Login: If the detected state is google_meet_loading_call, google_meet_meeting_connection_page_getting_ready, google_meet_meeting_connection_page, google_meet_awaiting_approval_page, google_meet_meeting_page, google_meet_call_finishing_page, google_meet_rejoin_page, or google_meet_allow_microphone, the user is implicitly considered logged_in: True. You cannot reach these states without a Google login.

        Specific Logout Indicator: If the state is google_meet_landing_page AND there are no "New meeting" or "Join a meeting" controls visible (only informational text or "Sign in" options), the user is almost certainly logged_in: False.

        Caution: Do not confuse login status in the Google Chrome browser (which might show a profile icon even if not logged into a Google web page) with login status on the Google web page itself. Always verify the login indicator *within the web page content`.
        """

    interface_detection_common = """
    Objective:
    Your task is to identify specific interface elements within Google Meet screenshots and provide 
    their precise bounding box coordinates. 
    
    Bounding Box Format: The box_2d coordinates must be provided as a list of four integers: [y_min, x_min, y_max, x_max].
    Please use relative coordinates from 0 to 1000. You should return coordinates and labels from the description below.
    
    List of Controls to Detect and Their Characteristics:
    
    """

    google_meet_initial_page = """
    
    new_meeting_button: A prominent button with the text "New meeting" or "Start a new meeting". Typically found on Google Meet's main dashboard after login.
        
    start_an_instant_meeting: An item found within a dropdown menu (e.g., accessed after clicking "New meeting"), explicitly labelled "Start an instant meeting".

    join_meeting_button: A button found on Google Meet pre-join or connection pages, or potentially a text input field, with text like "Join now", "Ask to join", "Join meeting", or other combinations including "Join".
    
    join_meeting_input: A input field where you may enter google meet meeting id or nickname/username
    
    """

    google_meet_allow_microphone = """    
    
    use_microphone_and_camera: The primary action button on a Google Meet permission request page, prompting to grant access to mic/camera. Examples of text include "Allow access", "Continue", or similar.

    allow_while_visiting_the_site: A button specifically labelled "Allow while visiting the site" or similar text, found on a permissions request page in Google Meet (often related to microphone/camera access).

    """

    google_chrome_workspace_popup = """
        
    cancel: A button or icon, often on a modal dialog or popup that manages browser profiles, accounts, or organizational settings. This control typically dismisses or declines an action. Examples of text include "Cancel", "No thanks", "Use Chrome without an account", or a close icon. This control should always be sought if such a popup is present.

    continue_button: A button or icon, often on a modal dialog or popup that manages browser profiles, accounts, or organizational settings. This control typically confirms or proceeds with an action. Examples of text include "Continue", "Next", "Done", or "Continue as [User Name]". This control should always be sought if such a popup is present.
    
    """

    google_sign_in_to_chrome = """
    
    cancel: A button or icon, often on a modal dialog or popup that manages browser profiles, accounts, or organizational settings. This control typically dismisses or declines an action. Examples of text include "Cancel", "No thanks", "Use Chrome without an account", or a close icon. This control should always be sought if such a popup is present.

    continue_button: A button or icon, often on a modal dialog or popup that manages browser profiles, accounts, or organizational settings. This control typically confirms or proceeds with an action. Examples of text include "Continue", "Next", "Done", or "Continue as [User Name]". This control should always be sought if such a popup is present.
     
    """

    google_meet_meeting_connection_page = """
        join_meeting: A button found on Google Meet pre-join or connection pages, or potentially a text input field, with text like "Join now", "Ask to join", "Join meeting", or other combinations including "Join".
    
    """
    # This prompt is the best for in meeting interface elements detection!
    google_meet_meeting_page = """
    Objective:
    Your primary task is to accurately identify all interactive control elements in the provided Google Meet screenshot and return their bounding box coordinates. 
    
    Bounding Box Format: The box_2d coordinates must be provided as a list of four integers: [y_min, x_min, y_max, x_max].
    Please use relative coordinates from 0 to 1000. You should return coordinates and labels from the description below.
    
    Please use next naming convention:

    label elements with their window/popup window belongs then action name please combine everything in lowcase separated by _
     """


class GMPageParserAIv3:
    find_control_elements_system_prompt = """
    Objective:
    Your task is to identify specific interface elements within Google Meet screenshots and provide 
    their precise bounding box coordinates.     
    Never return masks or code fencing. Limit to 25 objects.

    For each screenshot, identify all visible interface controls from the PageControls enum and provide their bounding box coordinates.

    Bounding Box Format: The box_2d coordinates must be provided as a list of four integers: [y_min, x_min, y_max, x_max].

    Limit: You must detect and return no more than 25 ControlElem objects.

    List of Controls to Detect and Their Characteristics:


    mute_video: A button (often circular) displaying a video camera icon, found in the control bar during an active Google Meet call. It may have a slash through it when muted.

    mute_audio: A circular button, typically white, displaying a microphone icon. Located in the central control bar at the bottom of the screen during an active Google Meet call. It may have a slash through it when muted.

    live_call: A prominent, typically red, circular button displaying a phone receiver icon. This button is located in the center of the control bar at the bottom of the screen, indicating the action to end the call in Google Meet.

    rise_hand: A button displaying an icon of a raised hand, typically found in the control bar during an active Google Meet call.

    chat_send_message_input: A text input field located within an open chat panel or sidebar in Google Meet, where a user can type messages to send. This is detected when a chat box is active and visible.

    
    """

    def __init__(self, settings: Settings):
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.thinkingDisabledConfig = ThinkingConfig(
            include_thoughts=False, thinking_budget=0
        )

        self.gm_state_client = genai.Client()
        self.gm_bb_client = genai.Client()
        self.screen_shot_maker = ScreenShotMaker()

    async def run(
        self, image: Optional[Image.Image | None] = None
    ) -> GMStateWithControlElems:
        # TODO Add try except logic maybe via proxy function!
        """

        :param image: screenshot of the current screen
        :param debug: should we draw image with metadata in the debuging folder or not.
        :return: metadata about page and controls.
        """
        debug = True if self.settings.log_level == LogLevel.DEBUG else False
        if not image:
            image_data = await self.screen_shot_maker.get_screen_gemini()
            image_size = image_data["image_size"]
            image = image_data["image"]

        else:
            image.thumbnail([1024, 1024], Image.Resampling.LANCZOS)
            image_size = image.size
        gm_state = await self.gm_state_client.aio.models.generate_content(
            model=settings.llm_model,
            contents=[
                image,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GMState,
                system_instruction=GMPagePrompts.find_gm_state_prompt,
                temperature=0.5,
                thinking_config=self.thinkingDisabledConfig,
            ),
        )
        # TODO May be not needed in our case
        safety_settings = [
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_ONLY_HIGH",
            ),
        ]
        if gm_state.parsed.state == GoogleMeetState.google_meet_meeting_page:
            """Why is this logic so different? 
            
                    For the main Google Meet call page, which is visually dense with many
                    small, similar icons in the control bar, simpler prompts yield
                    significantly more accurate bounding box detection.

                    Empirical testing showed that overly detailed system prompts with long,
                    prescriptive lists of labels caused 'instruction overload'. The model
                    would shift its focus from precise visual localization to trying to
                    'check off' all items from the list. This resulted in inaccurate,
                    shifted, or merged bounding boxes for the main controls. A shorter,
                    more direct prompt allows the model to prioritize its core visual
                    detection strength first ('see the object'), and then apply a name.

                    Additionally, this special path avoids using the structured JSON output
                    feature (`response_mime_type` and `response_schema`). While structured
                    output is great for guaranteeing a parseable result, it adds another
                    layer of constraint on the model. For this visually complex task, we
                    remove that constraint and perform manual JSON validation. This gives
                    the model maximum freedom to return the most accurate coordinates,
                    even if the raw text output requires careful parsing.

                    The higher temperature (0.7) is also intentional, encouraging the
                    model to be more 'creative' in identifying elements in the cluttered
                    interface, whereas simpler screens benefit from a lower, more
                    deterministic temperature (0.2).
            """
            bb_prompt = getattr(GMPagePrompts, gm_state.parsed.state.value)
            temperature = 0.7
            prompt = (
                "Please detect all call control element in the google meet screenshot"
            )
            gm_bbs_raw = await self.gm_bb_client.aio.models.generate_content(
                model=settings.llm_model,
                contents=[prompt, image],
                config=types.GenerateContentConfig(
                    system_instruction=bb_prompt,
                    temperature=temperature,
                    thinking_config=self.thinkingDisabledConfig,
                    safety_settings=safety_settings,
                ),
            )
            from pydantic import TypeAdapter

            adapter = TypeAdapter(List[ControlElem])
            gm_bbs_pydantic = adapter.validate_json(parse_json(gm_bbs_raw.text))
        else:
            # general logic
            bb_prompt = GMPagePrompts.interface_detection_common + getattr(
                GMPagePrompts, gm_state.parsed.state.value, ""
            )
            temperature = 0.2
            prompt = "Please find all available control elements."

            gm_bbs = await self.gm_bb_client.aio.models.generate_content(
                model=settings.llm_model,
                contents=[prompt, image],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ControlElemList,
                    system_instruction=bb_prompt,
                    temperature=temperature,
                    thinking_config=self.thinkingDisabledConfig,
                    safety_settings=safety_settings,
                ),
            )
            gm_bbs_pydantic = gm_bbs.parsed
            for element in gm_bbs_pydantic.elements:
                # Sometimes we have wrong answer from a model like "Raise hand button"
                element.label = element.label.lower().replace(" ", "_")

        output = GMStateWithControlElems(
            state=gm_state.parsed.state,
            logged_in=gm_state.parsed.logged_in,
            alone_in_the_call=gm_state.parsed.alone_in_the_call,
            elements=gm_bbs_pydantic.elements
            if not isinstance(gm_bbs_pydantic, list)
            else gm_bbs_pydantic,
        )
        img_buf = np.array(image)
        cv_img = cv2.cvtColor(img_buf, cv2.COLOR_RGB2BGR)
        logging.info(f"Current state with interface elements: {output}")
        if cv_img is None:
            raise ValueError("Input data is not a valid image")

        for elem in output.elements:
            """
            Model returns dimensions in scale from 0 to 1000 we should convert to real image size.
            """
            abs_y1 = int(elem.box_2d[0] / 1000 * image_size[1])
            abs_x1 = int(elem.box_2d[1] / 1000 * image_size[0])
            abs_y2 = int(elem.box_2d[2] / 1000 * image_size[1])
            abs_x2 = int(elem.box_2d[3] / 1000 * image_size[0])

            if abs_x1 > abs_x2:
                abs_x1, abs_x2 = abs_x2, abs_x1

            if abs_y1 > abs_y2:
                abs_y1, abs_y2 = abs_y2, abs_y1
            elem.box_2d = [abs_y1, abs_x1, abs_y2, abs_x2]
            if debug:
                cv2.rectangle(
                    cv_img, (abs_x1, abs_y1), (abs_x2, abs_y2), (128, 128, 128), 2
                )
        now = datetime.datetime.now()
        if debug:
            cv2.imwrite(
                str(
                    self.settings.technical_screenshots
                    / f"gm_{now.strftime('%Y-%m-%d-%H-%M-%S')}.png"
                ),
                cv_img,
            )
        return output


class GMPageParserAI:
    #     google_meet_meeting_add_participant_page - It should be a screenshot with a google meet call from the host and an incoming participant notification: On the right, a pop-up notification shows that "Someone wants to join this call." (text maybe slightly different) The person's name is maybe different, and the host has the options to Admit or View
    """ """

    system_prompt = """
    
    You will receive google meeting screenshots. You will see google meet in various states. Your goals are to determine the state of the google meet call and detect interface elements. Here is list of possible state and their description:
    google_login_page - page with initial Google login password prompt 
    google_relogin_page - page where you need to confirm yourself and reenter password
    google_chrome_workspace_popup - it should be popup with text 'Your organization will manage this profile' or something similar.
    google_meet_initial_page - google meet initial page with text (maybe not exactly the same) video calls and meetings for everyone, user logged in and there are controls(buttons) for starting new meeting
    google_meet_meeting_connection_page_getting_ready page of connection to google meet meeting with text: Getting ready...
    google_meet_meeting_connection_page - page with interface text: Ready to join? And the ‘Ask to join’ or ‘Join’ button. 
    google_meet_awaiting_approval_page - when you are asked to join google meet you will see the page with awaiting approval.
    google_meet_meeting_page - when you see the google meet call on screenshot
    google_meet_rejoin_page - page with texts You've left the meeting (may be different but with the same sense) and buttons ‘Rejoin’, ‘Return to home screen’ (names of buttons may be also a little bit different. 
    google_meet_loading_call - when you connect to the call and you see black screen with ‘loading…’ or ‘joining…’ text. 
    google_meet_landing_page - if you see google meet landing page. W/o new call creation join to call controls and user isn't logged in 
    google_meet_unknown_page - if you see some other page with google meet or some other google services you should return this state instead. 
    google_meet_allow_microphone - page where google meet asks to allow microphone. Note if use this page it means user already logged in 
    You should return the state under the state key. You should return only state name w/o any descriptions
    Also you should always check if the user logged in or not and return it in the field logged_in as True or False. You may detect if a user is logged in or not by a circle in the right top corner of the web page with the user's icon standard for all google services. 
    Be Careful! Don’t mess up login in google chrome browser (even though you aren’t logged in you may see an icon with user image) and login in google web page. Please always check login on the web page! But please note: IMPORTANT!!! If you see a screenshot with a google meet call it implicitly assumes that a user is already logged in because you can’t enter a google meet call w/o google login.
    If you see google meet /google workspace landing w/o button New meeting with 100% probability user isn't logged in.
    If you see screenshot of an active google meet call (video conference call) and you see only one participant icon and you don’t see any other icons with names you should setup status alone_in_the_call = True 
    Here is a list of controls on pages that you should detect. Please provide coordinates of these controls. Controls may be buttons, elements of drop down or other control elements. Please read carefully description of controls: 
    new_meeting - button with the text: New meeting
    start_an_instant_meeting - Element of drop down with text ‘Start an instant meeting’
    join_meeting - button with text ‘Join meeting’, 'Join now' or other combinations with 'Join'
    mute_video - button (icon) mute video
    mute_audio - A white circular button with a microphone icon. at the bottom of the screen
    leave_call - A prominent red circular button with a phone receiver icon, indicating the action to end the call.
    rise_hand - A button with a hand icon
    chat_send_message_input - if a chat box is in an open state this is an object where a user may write text. 
    use_microphone_and_camera - button that appears on a page where google meet asks to access to camera and microphone
    allow_while_visiting_the_site - button that appears on a page where google meet asks to access to camera and microphone. Text may be 'Allow while visiting the site'
    cancel - button (icon) with text 'cancel' that you may see on some popup elements of interface. This control should be on google_chrome_workspace_popup. If you see google_chrome_workspace_popup please be sure that you find this control. 
    continue_button - button (icon) with text 'continue' that you may see on some popup elements of interface. This control should be on google_chrome_workspace_popup. If you see google_chrome_workspace_popup please be sure that you find this control. 
    admit_button -  ‘Admit’ button is placed in a pop-up notification located at the bottom right corner of the screen. This grey-colored rectangular notification indicates that "Someone wants to join this call" and specifically names the person  with a small circular profile picture next to the name. Below this information, there are two buttons: "Admit" and "View". Also the Admit button may be found in a "People" pop-up window.  At the top of this pop-up there's a title "People" and an "Add people" button. Below that, a search bar labeled "Search for people" is visible. A section titled "WAITING TO JOIN" indicates that  persons that are wanting to be admitted to the meeting. In front of every person you can see Admit button.
    view - ‘View’ button is placed in a pop-up notification located at the bottom right corner of the screen. This notification is a grey-colored rectangular box that states "Someone wants to join this call" and includes a "View" button on its right side. To the left of the text, there is a small circular profile picture.
    admit_all - ‘Admit all’ button is placed in a "People" pop-up window.  At the top of this pop-up there's a title "People" and an "Add people" button. Below that, a search bar labeled "Search for people" is visible. A section titled "WAITING TO JOIN" indicates that  persons that are wanting to be admitted to the meeting. Within this section, there are two prominent buttons: "Deny all" and "Admit all". The "Admit all" button is blue and is located to the right of "Deny all".
    Never return masks or code fencing. Limit to 25 objects.
    
"""

    def __init__(self, settings: Settings, use_pydantic: bool = False):
        """
        For the purpose of creating code that does not depend on a specific LLM
        I wanted to use PydanticAI. But PydanticAI has an odd issue with the BinaryContent class.
        If I feed an image to Gemini via PydanticAI, Gemini detects the interface element
        with very bad precision. But I drew an image from BinaryContent and it looks good…
        I suspect that some transformations inside the PydanticAI are happening
        when the .run function is called and it causes distortion.
        I didn’t have time to analyse and fix this issue and decided to create native version
        of this class that works with Gemini directly.
        But I save options for Pydantic AI and I hope that I can switch to it later.

        :param settings:  - project settings object
        :param use_pydantic: - which type of llm interaction we should use. PydanticAI or native.
        """
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.use_pydantic = use_pydantic

        self.thinkingDisabledConfig = ThinkingConfig(
            include_thoughts=False, thinking_budget=0
        )

        self.agent = Agent(
            settings.pydantic_ai_model,
            system_prompt=self.system_prompt,
            model_settings=ModelSettings(
                temperature=0.4, gemini_thinking_config=self.thinkingDisabledConfig
            ),
        )
        self.screen_shot_maker = ScreenShotMaker()
        self.client = genai.Client()

    async def run(
        self, image: Optional[Image.Image | None] = None, debug=True
    ) -> GMState:
        """

        :param image: screenshot of the current screen
        :param debug: should we draw image with metadata in the debuging folder or not.
        :return: metadata about page and controls.
        """
        if not image:
            if self.use_pydantic:
                image, image_size = await self.screen_shot_maker.get_screen_pydantic()
            else:
                screen_shot_data = await self.screen_shot_maker.get_screen_gemini()
                image = screen_shot_data["image"]
                image_size = screen_shot_data["image_size"]
        else:
            image_size = image.size
            if self.use_pydantic:
                image_io = io.BytesIO()
                if image.mode == "RGBA":
                    image = image.convert("RGB")
                image.save(image_io, format="jpeg")
                image_io.seek(0)
                image_bytes = image_io.read()
                image = BinaryContent(image_bytes, media_type="image/jpeg")

        if self.use_pydantic:
            result = await self.agent.run([image], output_type=GMState)

        else:
            print(f"We call Gemini! {image}")
            result = self.client.models.generate_content(
                model=settings.llm_model,
                contents=[
                    "Please detect all call control element in the google meet screenshot",
                    image,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=GMState,
                    system_instruction=self.system_prompt,
                    temperature=0.5,
                    thinking_config=self.thinkingDisabledConfig,
                ),
            )

        if self.use_pydantic:
            print(f"tokens consummed: {result.usage()}")
            output = result.output
            img_buf = np.frombuffer(image.data, dtype=np.uint8)
            cv_img = cv2.imdecode(img_buf, cv2.IMREAD_COLOR)
        else:
            output = result.parsed
            img_buf = np.array(image)
            cv_img = cv2.cvtColor(img_buf, cv2.COLOR_RGB2BGR)

        logging.info(output)
        if cv_img is None:
            raise ValueError("Input data is not a valid image")

        for elem in output.control_elems:
            """
            Model returns dimensions in scale from 0 to 1000 we should convert to real image size.
            """
            abs_y1 = int(elem.box_2d[0] / 1000 * image_size[1])
            abs_x1 = int(elem.box_2d[1] / 1000 * image_size[0])
            abs_y2 = int(elem.box_2d[2] / 1000 * image_size[1])
            abs_x2 = int(elem.box_2d[3] / 1000 * image_size[0])
            if abs_x1 > abs_x2:
                abs_x1, abs_x2 = abs_x2, abs_x1

            if abs_y1 > abs_y2:
                abs_y1, abs_y2 = abs_y2, abs_y1
            elem.box_2d = [abs_y1, abs_x1, abs_y2, abs_x2]
            if debug:
                cv2.rectangle(
                    cv_img, (abs_x1, abs_y1), (abs_x2, abs_y2), (128, 128, 128), 2
                )
        now = datetime.datetime.now()
        if debug:
            cv2.imwrite(
                f"./technical_screenshots/gm_{now.strftime('%Y-%m-%d-%H-%M-%S')}.png",
                cv_img,
            )
        # TODO maybe we should remove image_width and image_height
        # output.image_width = image_size[0]
        # output.image_height = image_size[1]
        return output
