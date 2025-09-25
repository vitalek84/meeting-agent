import logging
from typing import Optional

import requests

from connection_manager.docker_manager import DockerManager
from connection_manager.schemas import LiveAgentRoles, MeetingProgress, StatusEnum
from connection_manager.settings import settings


def launch_google_meet(
    user_id: str, gm_link: Optional[str] = None, agent_role: Optional[str] = None
) -> str:
    """
    Launch google meet container.

    :param user_id: - unique user id
    :param gm_link: - is optional parameter
    :param agent_role - which prompt we will use
    :return:
    """
    try:
        agent_role_verified = LiveAgentRoles(agent_role)
    except ValueError:
        logging.warning(
            f"Can't find role {agent_role} in LiveAgentRoles "
            f"{LiveAgentRoles.software_development_manager} will be used as "
            f"a default role"
        )
        agent_role_verified = LiveAgentRoles.software_development_manager

    docker_manager = DockerManager(settings)
    logging.info("Start container")
    result = docker_manager.launch_container(user_id, gm_link, agent_role_verified)
    if result == "OK":
        meet_progress = MeetingProgress(
            status=StatusEnum.container_starting, user_id=user_id
        )
        requests.post(
            str(settings.callback_url), json=meet_progress.model_dump(), timeout=120.0
        )
    return result
