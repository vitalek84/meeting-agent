import asyncio
import logging
import uuid
from typing import Dict

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from starlette import status
from starlette.responses import JSONResponse

from connection_manager.agent.meeting_manager import MeetingManager
from connection_manager.agent.tools import launch_google_meet
from connection_manager.docker_manager import DockerManager
from connection_manager.schemas import (
    MeetingProgress,
    ResponseType,
    StatusEnum,
    WebSocketResponse,
)
from connection_manager.settings import settings

# --- Configuration ---
WORKER_IMAGE_NAME = "statemachine_worker:latest"  # The name we'll give our worker image
# This URL is how the worker container will reach the main app.
# 'main_app' is the service name we will define in docker-compose.
INTERNAL_CALLBACK_URL = "http://main_app:8000/internal/meeting_ready"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

app = FastAPI()


# --- Connection and State Management ---


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        """Initialize the ConnectionManager with an empty dictionary."""
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Accept a WebSocket connection and store it with the given user ID.

        Args:
            websocket: The WebSocket to connect.
            user_id: The unique identifier for the user.
        """
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str) -> None:
        """Remove a disconnected user's WebSocket connection.

        Args:
            user_id: The unique identifier for the user to disconnect.
        """
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(
        self, message: WebSocketResponse, user_id: str
    ) -> None:
        """Send a personal message to a specific user via their WebSocket.

        Args:
            message: The WebSocketResponse message to send.
            user_id: The unique identifier for the user to send the message to.
        """
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message.model_dump_json())


manager = ConnectionManager()

docker_manager = DockerManager(settings)


def register_exception(app: FastAPI) -> None:
    """Register exception handlers for the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle RequestValidationErrors by logging them and returning a JSON response.

        Args:
            request: The incoming request.
            exc: The RequestValidationError exception.

        Returns:
            A JSONResponse indicating the validation error.
        """
        exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
        logging.error(f"Validation error for {request.url}: {exc_str}")
        content = {"status_code": 10422, "message": exc_str, "data": None}
        return JSONResponse(
            content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


# --- API Endpoints ---
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


@app.get("/")
async def get() -> HTMLResponse:
    """Render a simple HTML page for WebSocket connection testing.

    :return: HTMLResponse
    """
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Handle WebSocket connections for real-time communication.

    This endpoint manages user connections, receives messages, interacts with
    the MeetingManager agent, and sends responses back to the client.

    Args:
        websocket: The WebSocket connection object.
    """
    user_id = str(uuid.uuid4())
    await manager.connect(websocket, user_id)
    logging.info(f"User {user_id} connected.")
    agent = MeetingManager(settings, tools=[launch_google_meet])
    result = None
    try:
        while True:
            data = await websocket.receive_text()
            data += f"user_id: {user_id}"
            if result is not None:
                result = await agent.mngmnt_agent.run(
                    data, message_history=result.all_messages()
                )
            else:
                result = await agent.mngmnt_agent.run(data)
            response = WebSocketResponse(
                response_type=ResponseType.assistant_response, text=result.output
            )
            await asyncio.sleep(5)
            await manager.send_personal_message(response, user_id)

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        docker_manager.stop_session(user_id)
        logging.info(f"User {user_id} disconnected.")

    except Exception as ex:
        logging.error(
            f"During websocket connection for user {user_id}, an error occurred: {ex}"
        )
        # Optionally, send an error message back to the client
        error_response = WebSocketResponse(
            response_type=ResponseType.error,
            text="An unexpected error occurred.",
        )
        await manager.send_personal_message(error_response, user_id)
        manager.disconnect(user_id)


@app.post("/internal/meeting_progress")
async def meeting_progress_callback(result: MeetingProgress) -> Dict:
    """Notify about call creation/connection progress and errors.

    This is a callback function invoked by workers managing Google meetings.
    It's used to inform users about the progress of call creation/connection
    and any occurring errors.

    :param result: MeetingProgress object containing status, description, and link.
    :return: A dictionary acknowledging the received status.
    """
    response_type = ResponseType.connection_progress
    if result.status == StatusEnum.error:
        response_type = ResponseType.error

    response = WebSocketResponse(
        response_type=response_type,
        text=f"{result.status.value}: {result.status.description()}",
        gm_link=result.gm_link,
    )
    await manager.send_personal_message(response, result.user_id)
    return {"status": "acknowledged"}
