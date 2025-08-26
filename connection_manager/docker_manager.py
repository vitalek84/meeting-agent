import datetime
import logging
import os
import threading
from datetime import tzinfo
from time import sleep
from typing import Dict, List, Optional, Set

import docker
import requests
from docker.errors import NotFound
from docker.models.containers import Container

# Assuming these are defined in your project
from connection_manager.schemas import ContainerSettings, LiveAgentRoles
from connection_manager.settings import Settings


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
        self.occupied_ports: Set[int] = set()
        self.occupied_ports_lock = threading.Lock()
        self.port_range = range(5900, 6001)
        # New logic
        self.log_streaming_threads: Dict[str, threading.Thread] = {}
        self.log_threads_lock = threading.Lock()
        # End new logic
        self.settings = settings
        self.monitoring_active = True
        self.monitoring_thread = None
        print(settings.google_accounts)
        for account in settings.google_accounts:
            self.containers_settings.append(
                ContainerSettings(
                    google_email=account.email,
                    google_password=account.password,
                    browser_profile_dir=settings.browser_profile_root / account.email.replace("@", "-").replace(".",
                                                                                                                "-"),
                    is_launched=False
                )
            )
        self.start_monitoring()

    def _find_available_port(self) -> Optional[int]:
        """Finds an available port within the specified range."""
        with self.occupied_ports_lock:
            for port in self.port_range:
                if port not in self.occupied_ports:
                    self.occupied_ports.add(port)
                    return port
        return None

    def _release_port(self, port: int):
        """Releases a port, making it available for reuse."""
        with self.occupied_ports_lock:
            if port in self.occupied_ports:
                self.occupied_ports.remove(port)

    # New logic
    def _stream_container_logs_to_file(self, container: Container, log_file_path: str):
        """
        Streams logs from a container and writes them to a file.
        This method is intended to be run in a separate thread.
        """
        self.logger.info(f"Starting to stream logs for container {container.short_id} to {log_file_path}")
        try:
            with open(log_file_path, 'ab') as log_file: # Open in append binary mode
                # The stream=True makes this a blocking call that yields new lines as they come in
                for line in container.logs(stream=True, follow=True, stdout=True, stderr=True):
                    log_file.write(line)
                    log_file.flush()
        except Exception as e:
            self.logger.error(f"Log streaming for container {container.short_id} failed: {e}")
        finally:
            self.logger.info(f"Stopping log stream for container {container.short_id}.")
    # End new logic

    def find_container_settings_by_email(self, email: str) -> Optional[ContainerSettings]:
        """Finds container settings by Google email."""
        return next((cs for cs in self.containers_settings if cs.google_email == email), None)

    def monitor_containers(self):
        """Monitors all active docker containers and cleans up if they are not running."""
        while self.monitoring_active:
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
                        f"Container for user {user_id} not found. Cleaning up settings.")
                    self.cleanup_container_resources(None, user_id) # Pass None for container
            sleep(5)

    def cleanup_container_resources(self, container: Optional[Container], user_id: str):
        """Clears internal storage, resets flags, and stops associated threads."""
        try:
            # New logic
            # The log streaming thread will stop automatically when the container stops.
            # We just need to remove our reference to it.
            with self.log_threads_lock:
                if user_id in self.log_streaming_threads:
                    del self.log_streaming_threads[user_id]
                    self.logger.info(f"Removed log streaming thread reference for user {user_id}.")
            # End new logic

            if container:
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
                    container.reload()
                    if container.ports:
                        for container_port, host_ports in container.ports.items():
                            if host_ports:
                                for host_port in host_ports:
                                    self._release_port(int(host_port['HostPort']))
                except Exception as e:
                    self.logger.error(f"Error releasing port for user {user_id}: {e}")

                try:
                    container.remove(force=True)
                except NotFound:
                    pass  # Already removed

        except Exception as e:
            self.logger.error(f"Error during cleanup for user {user_id}: {e}")
        finally:
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
            container_settings: ContainerSettings,
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
            self, user_id: str,
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

        host_port = self._find_available_port()
        if host_port is None:
            self.logger.warning("No available ports in the specified range.")
            return "No available ports"

        environment = self.create_environment(container_settings, user_id, agent_role, gm_link)

        # New logic
        # Instead of mounting a log volume, we will now stream STDOUT/STDERR directly.
        # Define the log file path on the host.
        now = datetime.datetime.now(tz=datetime.UTC)
        user_logs_path_on_host = self.settings.logs_root / f"{now.strftime('%Y-%m-%dT%H:%M:%S')}-{user_id}.log"
        os.makedirs(os.path.dirname(user_logs_path_on_host), exist_ok=True)
        # End new logic

        volumes_to_mount = {
            str(self.settings.browser_profile_volume): {
                "bind": str(self.settings.browser_profile_root),
                "mode": "rw"
            },
            str(self.settings.technical_screenshots): {
                "bind": str(self.settings.technical_screenshots),
                "mode": "rw"
            }
        }
        self.logger.info(f"Volumes for mounting: {volumes_to_mount}")

        ports_mapping = {'5900/tcp': host_port}

        try:
            container = self.docker_client.containers.run(
                self.settings.docker_image,
                detach=True,
                environment=environment,
                network="meeting-bot_default",
                shm_size='2g',
                volumes=volumes_to_mount,
                ports=ports_mapping
            )
        except Exception as e:
            self.logger.error(f"Failed to launch container for user {user_id}: {e}")
            self._release_port(host_port) # Release the port if container fails to start
            return "Failed to start container"

        self.logger.info(f"Launched container: {container.short_id} for user {user_id}")

        # New logic
        # Create and start a daemon thread to stream logs for the new container.
        log_thread = threading.Thread(
            target=self._stream_container_logs_to_file,
            args=(container, str(user_logs_path_on_host)),
            daemon=True
        )
        log_thread.start()
        with self.log_threads_lock:
            self.log_streaming_threads[user_id] = log_thread
        # End new logic

        with self.containers_settings_lock:
            container_settings.is_launched = True
        with self.active_containers_lock:
            self.active_containers[user_id] = container
        return "OK"

    def stop_session(self, user_id: str):
        if user_id in self.active_containers:
            self.logger.info(f"Stopping container for user: {user_id}")
            container = self.active_containers[user_id]
            container.stop()
            # The monitor_containers loop will eventually find the stopped container
            # and call cleanup_container_resources, or you can call it directly
            # for a more immediate cleanup.
            self.cleanup_container_resources(container, user_id)
            self.logger.info(f"Stopping container for user: {user_id} Done!")