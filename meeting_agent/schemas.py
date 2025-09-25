from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class StatusEnum(str, Enum):
    container_starting = "container_starting"
    new_meeting_starting = "new_meeting_starting"
    life_agent_loading = "life_agent_loading"
    error = "error"
    meeting_ready = "meeting_ready"
    waiting_for_approve = "waiting_for_approve"
    connecting_to_the_meeting = "connecting_to_the_meeting"
    ready = "ready"

    def description(self) -> str:
        return {
            StatusEnum.container_starting: "The container is starting up",
            StatusEnum.new_meeting_starting: "A new meeting is being initialized",
            StatusEnum.life_agent_loading: "The live agent is currently loading",
            StatusEnum.error: "An error has occurred",
            StatusEnum.meeting_ready: "The meeting is ready to join",
            StatusEnum.waiting_for_approve: "Waiting for approval to proceed",
            StatusEnum.connecting_to_the_meeting: "Connecting to the meeting",
            StatusEnum.ready: "System is fully ready",
        }[self]


class GoogleMeetState(Enum):
    google_login_page = "google_login_page"
    google_relogin_page = "google_relogin_page"
    google_chrome_workspace_popup = "google_chrome_workspace_popup"
    google_sign_in_to_chrome = "google_sign_in_to_chrome"
    google_meet_initial_page = "google_meet_initial_page"
    google_meet_meeting_connection_page = "google_meet_meeting_connection_page"
    google_meet_meeting_connection_page_getting_ready = (
        "google_meet_meeting_connection_page_getting_ready"
    )
    google_meet_awaiting_approval_page = "google_meet_awaiting_approval_page"
    google_meet_meeting_page = "google_meet_meeting_page"
    # google_meet_meeting_add_participant_page = "google_meet_meeting_add_participant_page"
    google_meet_call_finishing_page = "google_meet_call_finishing_page"
    google_meet_rejoin_page = "google_meet_rejoin_page"
    google_meet_loading_call = "google_meet_loading_call"
    google_meet_unknown_page = "google_meet_unknown_page"
    google_meet_landing_page = "google_meet_landing_page"
    google_meet_cant_join_this_call = "google_meet_cant_join_this_call"
    google_meet_allow_microphone = "google_meet_allow_microphone"  # TODO LLM Always use previous state it is ok. But maybe an issue in the future.


class PageControls(Enum):
    new_meeting_button = "new_meeting_button"
    start_an_instant_meeting = "start_an_instant_meeting"
    join_meeting = "join_meeting"
    mute_video = "mute_video"
    mute_audio = "mute_audio"
    live_call = "live_call"
    rise_hand = "rise_hand"
    chat_send_message_input = "chat_send_message_input"
    use_microphone_and_camera = "use_microphone_and_camera"
    allow_while_visiting_the_site = "allow_while_visiting_the_site"
    cancel = "cancel"
    continue_button = "continue"
    admit_button = "admit_button"
    admit_all_button = "admit_all_button"
    view_button = "view_button"
    # smiling_face_reaction_button = "smiling_face_reaction_button"


class ControlElem(BaseModel):
    """
    Represents a bounding box with its 2D coordinates and associated label.
    """

    label: str = Field(..., description="Name of the control element")
    box_2d: List[int] = Field(
        ..., description="Bounding Box: [y_min, x_min, y_max, x_max]."
    )


# class ControlElem(BaseModel):
#     """
#        Represents a bounding box with its 2D coordinates and associated label.
#     """
#     label: str
#     box_2d: List[int]


class ControlElemList(BaseModel):
    elements: List[ControlElem]


class GMState(BaseModel):
    state: GoogleMeetState
    logged_in: bool = Field(
        ...,
        description="True if a user is logged into the Google web page/service, False otherwise.",
    )
    alone_in_the_call: Optional[bool] = Field(
        False,
        description="True if only one participant is visible in the call. Only applicable for 'google_meet_meeting_page'.",
    )


class GMStateWithControlElems(GMState):
    """
    we use separate class here because Gemini can't combine state detection and BB detection in one prompt
    (it doesn't perform well)
    """

    elements: List[ControlElem]


class GMStateTest(BaseModel):
    name: str = Field(..., description="What the element is or does.")
    category: str = Field(
        ...,
        description="Category: (e.g., 'Browser Tab', 'Application Button', 'Notification Popup', 'System Tray Icon').",
    )
    bounding_box: list[int] = Field(
        ...,
        description="Bounding Box: The pixel coordinates [x_min, y_min, x_max, y_max] "
        " of its bounding box.",
    )


class GMStateTestList(BaseModel):
    elements: List[GMStateTest]


class MeetingProgress(BaseModel):
    user_id: str = Field(..., description="User id in uuid as string format")
    gm_link: Optional[str] = Field(
        default=None, description="Link for connection to a meeting"
    )
    error: Optional[str] = Field(
        default=None, description="Description of an error if it occurs"
    )
    status: StatusEnum = Field(..., description="Status of meeting creation process")
