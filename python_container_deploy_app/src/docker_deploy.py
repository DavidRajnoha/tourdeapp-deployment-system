import time

import docker
import logging

client = docker.from_env()


class DockerContainerStartError(Exception):
    def __init__(self, message, container_logs, container_status, container_id):
        super().__init__(message)
        self.container_id = container_id
        self.container_status = container_status
        self.container_logs = container_logs


class InternalDockerError(Exception):
    pass


class InvalidParameterError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


def extract_registry_from_image_name(image_name):
    """
    Extract the Docker registry URL from a given Docker image name.

    Parameters:
        image_name (str): The full name of the Docker image.

    Returns:
        str: The extracted Docker registry URL, or None if not found.
    """
    parts = image_name.split('/')

    # If there's only one part, it means the image is from Docker Hub
    if len(parts) == 1:
        return None  # Default to Docker Hub

    # Check if the first part contains a '.' or a ':', indicating it's likely a registry URL
    if '.' in parts[0] or ':' in parts[0]:
        return parts[0]

    return None  # Default to Docker Hub


def deploy_container(image_name, subdomain, container_name, registry_credentials=None,
                     network=None, traefik_domain=None, timeout=60):
    try:
        logging.info(f'Attempting to pull image: {image_name}')
        if registry_credentials:
            registry = extract_registry_from_image_name(image_name)
            if not registry:
                raise InvalidParameterError(f'Could not extract registry from image name {image_name}')
            username, password = registry_credentials.split(':')
            try:
                login_result = client.login(username=username, password=password, registry=registry)
            except docker.errors.APIError as e:
                logging.error(f'API error: {str(e)}')
                raise UnauthorizedError("Invalid registry credentials")
            logging.info(f'Tried to log in to registry {registry} with username {username} with result {login_result}')

        routed_domain = f"{subdomain}.app.{traefik_domain}"

        labels = {
            "traefik.enable": "true",
            f"traefik.http.routers.{subdomain}.rule": f"Host(`{routed_domain}`)",
            f"traefik.http.routers.{subdomain}.entrypoints": "web",
        }

        # pulling container image to run the latest version
        logging.info(f'Attempting to pull image: {image_name}')
        client.images.pull(image_name)

        logging.info(f'Attempting to run container from image: {image_name}')
        container = client.containers.run(image_name,
                                          name=container_name,
                                          detach=True,
                                          labels=labels,
                                          network=network)

        wait_for_container(container, timeout)
        logging.info('Started container with id: {}'.format(container.short_id))

        return (container.status, container.id, container.name,
                routed_domain, container.logs().decode('utf-8'), int(time.time()))

    except docker.errors.ImageNotFound:
        logging.error('Image {} not found.'.format(image_name))
        raise InvalidParameterError('Image {} not found.'.format(image_name))
    except docker.errors.APIError as e:
        logging.error('API error: {}'.format(str(e)))
        raise InternalDockerError('API error: {}'.format(str(e)))


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


def wait_for_container(container, timeout):
    start_time = time.time()
    running = False

    while not (container.status == 'running' and running):
        if container.status == 'running':
            running = True
            logging.info(f'Container {container.id} is running, waiting if it will stay running.')
        time.sleep(10)
        container.reload()
        logging.info(f'Waiting for container {container.id} to start. Status: {container.status}')
        if time.time() - start_time > timeout or container.status == 'exited':
            err = f'Container {container.id} failed to start in {time.time() - start_time}' \
                  f' seconds. The status is {container.status}'
            logging.error(err)

            container_logs = container.logs().decode('utf-8')
            container_status = container.status
            container_id = container.id
            logging.info(container_logs)
            container.stop()
            container.remove()
            logging.info(f'Stopped and removed container {container.id}')

            raise DockerContainerStartError(err, container_logs, container_status, container_id)


def delete_container(container_id):
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
