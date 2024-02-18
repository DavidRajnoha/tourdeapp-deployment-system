import time
import docker
import logging

from shared.docker_wrapper.docker_utils import extract_registry_from_image_name, DockerContainerStartError, InternalDockerError, \
    InvalidParameterError, UnauthorizedError


client = docker.from_env()


def run_container(image_name, subdomain, container_name, registry_credentials=None,
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
