import time
import docker
import logging

from shared.docker_wrapper.docker_utils import InternalDockerError, InvalidParameterError


client = docker.from_env()


def start_container(container_id):
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
