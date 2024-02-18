import docker
import logging

from shared.docker_wrapper.docker_utils import InternalDockerError


client = docker.from_env()


def delete_container(container_id):
    """
    Stop and remove a Docker container.

    :param container_id: The ID of the container to stop and remove
    :return: True if the container was stopped and removed, False if the container did not exist
    :raises InternalDockerError: If an error occurred while stopping or removing the container
    """
    try:
        container = client.containers.get(container_id)
        container.stop()
        container.remove()
        msg = f'Stopped and removed container {container_id}\n'
        logging.info(msg)
        return True
    except docker.errors.NotFound:
        msg = f'Container {container_id} already does not exist'
        logging.info(msg)
        return False
    except docker.errors.APIError as e:
        err = f'API error for container {container_id}: {str(e)}'
        logging.error(err)
        raise InternalDockerError(err)
    except docker.errors.NullResource as e:
        err = f'Null resource for container {container_id}: {str(e)}'
        logging.error(err)
        raise InternalDockerError(err)
