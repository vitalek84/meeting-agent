from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

class LiveAgentRoles(Enum):
    software_development_manager = 'software_development_manager'
    psychologist = 'psychologist'
    heart_of_gold_computer = 'heart_of_gold_computer'
    business_coach = 'business_coach'

class ResponseType(Enum):
    connection_progress = 'connection_progress'
    assistant_response = 'assistant_response'
    error = 'error'

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



class ContainerSettings(BaseModel):

    browser_profile_dir: Path = Field( ...,
        description="Path to the browser profiles directory."
    )
    # agent_memory_dir: Path = Field( ...,
    #     description="Path to the browser profiles directory."
    # )
    google_email: str = Field(..., description="Google Account Email")
    google_password: str = Field(..., description="Google Account Password")
    is_launched: bool = Field(...,
                              description="True if we have container that already launched with this settings")

class MeetingProgress(BaseModel):
    user_id: str = Field(..., description="User id in uuid as string format")
    gm_link: Optional[str] = Field(default=None, description="Link for connection to a meeting")
    error: Optional[str] = Field(default=None, description="Description of an error if it occurs")
    status: StatusEnum = Field(..., description="Status of meeting creation process")


class WebSocketResponse(BaseModel):
    role: str = Field(default="assistant", description="Role of the response. Always assistant for now")
    response_type: ResponseType = Field(default=None,
                                        description="Type of response that helps a frontend to determinate behaviour")
    text: str = Field(..., description="Response text from assistant or from call back url")
    gm_link: Optional[str] = Field(default=None, description="Google meet link if we should share it")

class ConnectionManagerAgentResponse(BaseModel):
    text: str =  Field(..., description="Answer for user question/request")