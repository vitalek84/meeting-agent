import logging

import requests

from connection_manager.docker_manager import DockerManager
from connection_manager.schemas import StatusEnum, MeetingProgress, LiveAgentRoles
from connection_manager.settings import settings


def launch_google_meet(user_id: str, gm_link: str = None, agent_role:str = None) -> str:
    """
    :param user_id: - unique user id
    :param gm_link: - is optional parameter
    :param agent_role - which prompt we will use
    :return:
    """
    try:
        agent_role_verified = LiveAgentRoles(agent_role)
    except ValueError:
        logging.warning(f"Can't find role {agent_role} in LiveAgentRoles "
                        f"{LiveAgentRoles.software_development_manager} will be used as a default role")
        agent_role_verified = LiveAgentRoles.software_development_manager

    docker_manager = DockerManager(settings)
    logging.info("Start container")
    result = docker_manager.launch_container(user_id, gm_link, agent_role_verified)
    if result == "OK":
        meet_progress = MeetingProgress(status=StatusEnum.container_starting, user_id=user_id)
        requests.post(str(settings.callback_url), json=meet_progress.model_dump())
    return result