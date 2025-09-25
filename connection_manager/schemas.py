from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class LiveAgentRoles(Enum):
    """Enum for defining the roles of live agents."""

    software_development_manager = "software_development_manager"
    psychologist = "psychologist"
    heart_of_gold_computer = "heart_of_gold_computer"
    business_coach = "business_coach"


class ResponseType(Enum):
    """Enum for different types of responses sent over WebSockets."""

    connection_progress = "connection_progress"
    assistant_response = "assistant_response"
    error = "error"


class StatusEnum(str, Enum):
    """Enum representing the status of the meeting creation process."""

    container_starting = "container_starting"
    new_meeting_starting = "new_meeting_starting"
    life_agent_loading = "life_agent_loading"
    error = "error"
    meeting_ready = "meeting_ready"
    waiting_for_approve = "waiting_for_approve"
    connecting_to_the_meeting = "connecting_to_the_meeting"
    ready = "ready"

    def description(self) -> str:
        """Returns a human-readable description for each status."""
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


class ContainerSettings(BaseModel):
    """Settings for configuring a containerized environment."""

    browser_profile_dir: Path = Field(
        ..., description="Path to the browser profiles directory."
    )
    google_email: str = Field(..., description="Google Account Email")
    google_password: str = Field(..., description="Google Account Password")
    is_launched: bool = Field(
        ..., description="True if a container has already launched with these settings."
    )


class MeetingProgress(BaseModel):
    """Represents the progress or status of a meeting creation process."""

    user_id: str = Field(..., description="User ID in UUID string format.")
    gm_link: Optional[str] = Field(
        default=None, description="Link for connection to a meeting."
    )
    error: Optional[str] = Field(
        default=None, description="Description of an error if it occurs."
    )
    status: StatusEnum = Field(
        ..., description="Status of the meeting creation process."
    )


class WebSocketResponse(BaseModel):
    """Structure for responses sent over WebSockets."""

    role: str = Field(
        default="assistant",
        description="Role of the response. Currently always 'assistant'.",
    )
    response_type: ResponseType = Field(
        ..., description="Type of response to guide frontend behavior."
    )
    text: str = Field(
        ..., description="Response text from the assistant or a callback URL."
    )
    gm_link: Optional[str] = Field(
        default=None, description="Google Meet link, if one should be shared."
    )


class ConnectionManagerAgentResponse(BaseModel):
    """Represents the response from the Connection Manager agent."""

    text: str = Field(..., description="Answer for the user's question or request.")
