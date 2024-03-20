import logging
import os

from tasks.callback import store_data_for_callback
from shared.docker_wrapper.docker_run import run_container, \
    InternalDockerError, InvalidParameterError, DockerContainerStartError, UnauthorizedError
from shared.docker_wrapper.docker_delete import delete_container

from shared.persistance.redis_persistance import save_to_redis, \
    is_subdomain_used, InternalRedisError
from shared.persistance.redis_persistance import get_application as get_application_from_redis


traefik_domain = os.environ.get('BASE_DOMAIN', 'localhost')
traefik_network = os.environ.get('TRAEFIK_NETWORK', 'traefik_default')
deploy_timeout = int(os.environ.get('DEPLOY_TIMEOUT', 60))


class InternalError(Exception):
    pass


def deploy_application(team_id, subdomain, image_name, registry_credentials, redeploy=True):
    """
    Deploys an application by running a Docker container with specified parameters, and handling deployment conditions
    such as redeployment and subdomain availability. Updates application data in Redis upon successful deployment or
    records the failure reason.

    :param team_id: str. Unique identifier for the team deploying the application.
    :param subdomain: str. Desired subdomain for the application's access URL.
    :param image_name: str. Docker image to use for the application container.
    :param registry_credentials: str. Credentials for accessing the Docker registry in 'username:password' format.
    :param redeploy: bool, optional. Flag indicating whether to redeploy the application if it already exists (default is True).

    :return: Tuple (dict, str or None, int). Returns a tuple containing the application data as a dictionary,
             an error message (or None if successful), and an HTTP status code indicating the outcome.

    :raises InternalRedisError: If saving the application data to Redis fails.

    Note: The deployment logic includes checking deployment conditions, handling Docker and Redis errors,
    and updating Redis with the deployment result. It leverages environment variables for default values like
    Traefik domain and network, and deploy timeout.
    """
    application = {
        "team_id": team_id,
        "subdomain": subdomain,
        "image_name": image_name
    }

    container_name = f"team-{team_id}"
    err, status_code = "Failed to assign error cause for this case", 500
    try:
        check_deploy_conditions(team_id, subdomain, container_name, redeploy)

        logging.debug(f"Deploying application for team {team_id} with subdomain {subdomain} and image {image_name}")
        logging.debug(f"Registry credentials: {registry_credentials}")

        container_info = run_container(image_name, subdomain, container_name=f"team-{team_id}",
                                       registry_credentials=registry_credentials, network=traefik_network,
                                       traefik_domain=traefik_domain, timeout=deploy_timeout)
        application["status"] = container_info[0]
        application["container_id"] = container_info[1]
        application["container_name"] = container_info[2]
        application["route"] = container_info[3]
        application["logs"] = container_info[4]
        application["started_at"] = container_info[5]

    except InvalidParameterError as e:
        application["status"] = "invalid_parameter"
        application["error"] = str(e)
        err = str(e)
        status_code = 400
    except DockerContainerStartError as e:
        application["container_id"] = e.container_id
        application["status"] = e.container_status
        application["error"] = str(e)
        application["logs"] = e.container_logs
        err = str(e)
        status_code = 400
    except InternalDockerError:
        application["status"] = "internal_error"
        status_code = 500
        err = None
    except UnauthorizedError:
        application["status"] = "invalid_registry_credentials"
        status_code = 401
        err = None
    finally:
        status = 'success' if status_code == 200 else err
        store_data_for_callback(application, status, status_code)

    try:
        save_to_redis(application)
    except InternalRedisError as e:
        return None, str(e), 500

    return application, err, status_code


def check_deploy_conditions(team_id, subdomain, container_name, redeploy=True):
    """
    Checks conditions for deploying an application, such as verifying if the application or subdomain already exists,
    and handles necessary cleanup like deleting existing containers in case of redeployment.

    :param team_id: str. Unique identifier for the team associated with the application.
    :param subdomain: str. Desired subdomain for the application's access URL.
    :param container_name: str. Name assigned to the Docker container for the application.
    :param redeploy: bool, optional. Flag indicating whether to redeploy (and thus delete existing container)
                     if the application already exists (default is True).

    :raises InvalidParameterError: If the application already exists and redeployment is not allowed,
                                   or if the subdomain is already in use.
    :raises InternalError: For any unhandled situations or Docker-related errors during cleanup.

    Note: Utilizes application data from Redis to determine existence and uses Docker operations to manage containers.
          It is intended to be called within the `deploy_application` function to ensure pre-deployment conditions are met.
    """
    application = get_application_from_redis(team_id)
    subdomain_used = is_subdomain_used(subdomain)

    if not application and not subdomain_used:
        logging.info(f"No application found for team {team_id}. Deploying...")
        try:
            found_by_name = delete_container(container_name)
            if not found_by_name:
                # Everything ok, no container found
                return
            logging.info(f"Successfully deleted container {container_name} for team {team_id}. "
                         f"System was repaired from an inconsistent state")
        except InternalDockerError as e:
            logging.error(f"Failed to delete container {container_name} for team {team_id}\n"
                          f"There is no record for such application in the database, "
                          f"but the container exists. Please investigate")
        return

    if application and redeploy:
        logging.info(f"Application already exists for team {team_id}. Redeploying...")
        container_id = application.get('container_id')
        found_by_id = False
        found_by_name = False
        try:
            if container_id is not None:
                found_by_id = delete_container(container_id)
            if not found_by_id:
                found_by_name = delete_container(container_name)
            if not found_by_name and not found_by_id:
                logging.info("No container exits, proceeding with deployment")
                return

            logging.info(f"Successfully deleted container {container_id} for team {team_id},"
                         f" proceeding with deployment")
            return
        except InternalDockerError as e:
            err = f"Failed to delete container {container_id} for team {team_id}\n"
            logging.error(err)
            raise InternalError(err)

    if application and not redeploy:
        err = f'Application already exists for team {team_id}\n'
        logging.info(err)
        raise InvalidParameterError(err)

    if subdomain_used:
        err = f'Subdomain {subdomain} is already in use\n'
        logging.error(err)
        raise InvalidParameterError(err)

    err = "Unhandled situation while checking for application existence\n"
    logging.error(err)
    raise InternalError(err)
