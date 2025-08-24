import asyncio
import json
import logging
import uuid

import docker
import os

import requests
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, List

from connection_manager.agent.meeting_manager import MeetingManager
from connection_manager.agent.tools import launch_google_meet
from connection_manager.docker_manager import DockerManager
from connection_manager.schemas import MeetingProgress, WebSocketResponse, ResponseType, StatusEnum
from connection_manager.settings import settings


# --- Configuration ---
MAX_CONCURRENT_SESSIONS = 5  # Your resource pool limit
WORKER_IMAGE_NAME = "statemachine_worker:latest"  # The name we'll give our worker image
# This URL is how the worker container will reach the main app.
# 'main_app' is the service name we will define in docker-compose.
INTERNAL_CALLBACK_URL = "http://main_app:8000/internal/meeting_ready"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()


# --- Connection and State Management ---

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: WebSocketResponse, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message.model_dump_json())


manager = ConnectionManager()

docker_manager = DockerManager(settings)

def register_exception(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
        # or logger.error(f'{exc}')
        logging.error(request, exc_str)
        content = {'status_code': 10422, 'message': exc_str, 'data': None}
        return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


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

#
@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
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
                result = await agent.mngmnt_agent.run(data, message_history=result.all_messages())
            else:
                result = await agent.mngmnt_agent.run(data)
            response = WebSocketResponse(
                response_type=ResponseType.assistant_response,
                text=result.output
            )
            await asyncio.sleep(5)
            await manager.send_personal_message(
                        response,
                        user_id)

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        docker_manager.stop_session(user_id)

    except Exception as ex:
        print(f"Got exception {ex}")


@app.post("/internal/meeting_progress")
async def meeting_progress_callback(result: MeetingProgress):
    response_type = ResponseType.connection_progress
    if result.status == StatusEnum.error:
        response_type = ResponseType.error
    response = WebSocketResponse(
        response_type=response_type,
        text=f"{result.status.value}: {result.status.description()}",
        gm_link=result.gm_link
    )
    await manager.send_personal_message(response, result.user_id)
    return {"status": "acknowledged"}

