import logging
import os
import threading
from time import sleep
from typing import Dict, List, Optional

import docker
import requests
from docker.errors import NotFound
from docker.models.containers import Container

from connection_manager.schemas import ContainerSettings, MeetingProgress, StatusEnum, LiveAgentRoles
from connection_manager.settings import Settings, BASE_DIR


class DockerManager:
    _singleton_instance = None

    def __new__(cls, *args, **kwargs):
        if cls._singleton_instance is None:
            cls._singleton_instance = super(DockerManager, cls).__new__(cls)
        return cls._singleton_instance

    def __init__(self, settings: Settings):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self.logger = logging.getLogger(self.__class__.__name__)
        self.docker_client = docker.from_env()
        self.active_containers: Dict[str, Container] = {}
        self.active_containers_lock = threading.Lock()
        self.containers_settings: List[ContainerSettings] = []
        self.containers_settings_lock = threading.Lock()
        self.settings = settings
        self.monitoring_active = True
        self.monitoring_thread = None
        print(settings.google_accounts)
        for account in settings.google_accounts:
           self.containers_settings.append(
               ContainerSettings(
                   google_email=account.email,
                   google_password=account.password,
                   browser_profile_dir=settings.browser_profile_root / account.email.replace("@", "-").replace(".", "-"),
                   is_launched=False
               )
           )
        self.start_monitoring()

    def find_container_settings_by_email(self, email: str) -> Optional[ContainerSettings]:
        """Finds container settings by Google email."""
        return next((cs for cs in self.containers_settings if cs.google_email == email), None)

    def monitor_containers(self):
        """Monitors all active docker containers and cleans up if they are not running."""
        while self.monitoring_active:
            # TODO Implement Timer!
            # Create a copy of user_ids to avoid issues with modifying the dict while iterating
            user_ids = list(self.active_containers.keys())
            for user_id in user_ids:
                container = self.active_containers.get(user_id)
                if not container:
                    continue

                try:
                    container.reload()
                    if container.status != 'running':

                        self.logger.warning(
                            f"Container for user {user_id} is not running (status: {container.status}). Cleaning up.")
                        self.cleanup_container_resources(container, user_id)
                except NotFound:
                    self.logger.warning(
                        f"Container for user {user_id} not found. It might have been removed manually. Cleaning up settings.")
                    # If the container is not found, we still need to clean up the settings
                    # We need a way to get the email to find the container settings
                    # This part of the logic might need adjustment based on how you can retrieve the email
                    # For now, we assume we can't find the settings if the container is gone, so we just remove it from active_containers
                    with self.active_containers_lock:
                        del self.active_containers[user_id]

            sleep(5)  # Check every 10 seconds

    def cleanup_container_resources(self, container: Container, user_id: str):
        """Clears internal storage and resets the is_launched flag."""
        try:
            # Extract email from container's environment to find the correct settings
            env_vars = container.attrs['Config']['Env']
            email_var = next((var for var in env_vars if var.startswith("MEET_GOOGLE_EMAIL=")), None)
            if email_var:
                email = email_var.split("=")[1]
                container_settings = self.find_container_settings_by_email(email)

                if container_settings:
                    with self.containers_settings_lock:
                        container_settings.is_launched = False
                    self.logger.info(f"Reset is_launched=False for {email}")

            try:
                container.remove(force=True)
            except NotFound:
                pass # Already removed

        except Exception as e:
            self.logger.error(f"Error during cleanup for user {user_id}: {e}")
        finally:
            # Remove from active containers list
            if user_id in self.active_containers:
                with self.active_containers_lock:
                    del self.active_containers[user_id]

    def start_monitoring(self):
        """Starts the background monitoring thread."""
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(target=self.monitor_containers, daemon=True)
            self.monitoring_thread.start()
            self.logger.info("Docker container monitoring started.")

    def stop_monitoring(self):
        """Stops the background monitoring thread."""
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join()
        self.logger.info("Docker container monitoring stopped.")

    def find_unlaunched_container_settings(self) -> Optional[ContainerSettings]:
        return next((container for container in self.containers_settings if not container.is_launched), None)

    def create_environment(
            self,
            container_settings:ContainerSettings,
            user_id: str,
            agent_role,
            gm_link: str = None) -> Dict[str, str]:

        return {
            "MEET_USER_ID": user_id,
            "GEMINI_API_KEY": self.settings.gemini_api_key,
            "MEET_GM_LINK": gm_link,
            "MEET_GOOGLE_EMAIL": container_settings.google_email,
            "MEET_GOOGLE_PASSWORD": container_settings.google_password,
            "MEET_BROWSER_PROFILE_PATH": container_settings.browser_profile_dir,
            "MEET_AGENT_ROLE": agent_role.value,
            "MEET_TECHNICAL_SCREENSHOTS": self.settings.technical_screenshots,
            "MEET_MANAGER_HOST_NAME": self.settings.manager_host_name
        }

    def launch_container(
            self,user_id: str,
            gm_link: Optional[str] = None,
            agent_role: Optional[LiveAgentRoles] = None
    ) -> str:
        if agent_role is None:
            agent_role = LiveAgentRoles.software_development_manager
        container_settings = self.find_unlaunched_container_settings()
        if container_settings is None:
            logging.warning("No available slots for new containers")
            return "No available slots"
        if user_id in self.active_containers:
            return "You already have live call. Please finish it and then create new"
        environment = self.create_environment(container_settings, user_id, agent_role, gm_link)
        # os.makedirs(container_settings.browser_profile_dir, exist_ok=True)
        # TODO SHOULD BE ADDED
        # os.makedirs(user_logs_path_on_host, exist_ok=True)

        # 3. Build the volume mapping dictionary
        volumes_to_mount = {
            # --- Mapping #1: Profiles ---
            str(self.settings.browser_profile_volume): {  # The "Outside" Path
                # TODO Check maybe we should use full path here.
                "bind": str(self.settings.browser_profile_root),  # The "Inside" Path
                "mode": "rw"
            },
            # str(self.settings.wireplumber_cache_src): {
            #     "bind": str(self.settings.wireplumber_cache_dst),
            #     "mode": "ro"
            # },
            # TODO SHOULD BE ADDED
            # # --- Mapping #2: Logs ---
            # user_logs_path_on_host: {  # The "Outside" Path
            #     'bind': CONTAINER_LOG_PATH,  # The "Inside" Path
            #     'mode': 'rw'
            # }
            str(self.settings.technical_screenshots): {
                "bind": str(self.settings.technical_screenshots),
                "mode": "rw"
            }

        }
        self.logger.info(f"Volumes for mounting: {volumes_to_mount}")
        container = self.docker_client.containers.run(
            self.settings.docker_image,
            detach=True,
            environment=environment,
            network="meeting-bot_default",  # TODO Fix this
            shm_size='2g',  # Recommended for browser automation
            volumes=volumes_to_mount
        )
        self.logger.info(f"Launched container: {container}")
        # api_client = docker.APIClient()
        # container_details = api_client.inspect_container(container.id)
        # print(container_details)
        # sleep(20)
        with self.containers_settings_lock:
            container_settings.is_launched = True
        with self.active_containers_lock:
            self.active_containers[user_id] = container
        return "OK"

    def stop_session(self, user_id:str):
        if user_id in self.active_containers:
            self.logger.info(f"Stopping container for user: {user_id}")
            self.active_containers[user_id].stop()
            # TODO Deal with logs and than enable removing
            # self.active_containers[user_id].remove()
            self.logger.info(f"Stopping container for user: {user_id} Done!")

