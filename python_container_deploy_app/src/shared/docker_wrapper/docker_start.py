import time
from typing import Optional

import docker
import logging

from shared.docker_wrapper.docker_utils import InternalDockerError, InvalidParameterError


client = docker.from_env()


def start_container(container_id: str) -> (Optional[int], str) or (None, str):
    """
    Attempts to start a Docker container based on the given container ID. It checks if the container ID is not None,
    verifies whether the container is already running, and starts the container if it is not running.
    Logs are generated for each significant event, and specific errors are raised for exceptional conditions.

    :param container_id: str. The unique identifier for the Docker container to be started.

    :return: Tuple (int, str) or (None, str). Returns a tuple containing the UNIX timestamp at which the container
             was started and a message indicating the action taken ('Started container {container_id}' or
             'Container {container_id} is already running'). Returns (None, 'Container ID cannot be None')
             if the container_id is None.

    :raises InvalidParameterError: If the `container_id` is None or if the specified container cannot be found.
    :raises InternalDockerError: If there is an API error while attempting to start the container.

    Note: This function requires the 'docker' Python module for interacting with Docker and assumes that a Docker
    client (`client`) has been instantiated and is globally accessible. It also presupposes custom exception classes
    (`InvalidParameterError`, `InternalDockerError`) for handling specific error conditions.
    """
    try:
        if container_id is None:
            logging.error('Container ID cannot be None')
            raise InvalidParameterError('Container ID cannot be None')
        container = client.containers.get(container_id)
        if container.status == 'running':
            logging.info(f'Container {container_id} is already running')
            return None, f'Container {container_id} is already running'
        container.start()
        logging.info(f'Started container {container_id}')
        return int(time.time()), f'Started container {container_id}'
    except docker.errors.NotFound:
        err = f'Container {container_id} not found'
        logging.error(err)
        raise InvalidParameterError(err)
    except docker.errors.APIError as e:
        err = f'API error for container {container_id}: {str(e)}'
        logging.error(err)
        raise InternalDockerError(err)
