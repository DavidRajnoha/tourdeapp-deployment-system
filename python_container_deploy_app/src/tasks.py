import logging
import os

from src.docker_deploy import deploy_container, delete_container,\
    InternalDockerError, InvalidParameterError, DockerContainerStartError

from src.persistance import save_to_redis, delete_from_redis, \
    is_subdomain_used, get_all_team_ids, InternalRedisError, flush_redis
from src.persistance import get_applications as get_applications_from_redis
from src.persistance import get_application as get_application_from_redis
from src.async_rq import store_data_for_callback, notify_callback_url

traefik_domain = os.environ.get('BASE_DOMAIN', 'localhost')
traefik_network = os.environ.get('TRAEFIK_NETWORK', 'traefik_default')
deploy_timeout = int(os.environ.get('DEPLOY_TIMEOUT', 60))

logging.basicConfig(level=logging.INFO)

class InternalError(Exception):
    pass


def deploy_application(team_id, subdomain, image_name, registry_credentials, redeploy=True):
    application = {
        "team_id": team_id,
        "subdomain": subdomain,
        "image_name": image_name
    }

    err, status_code = "Failed to assign error cause for this case", 500
    try:
        check_deploy_conditions(team_id, subdomain, redeploy)

        logging.debug(f"Deploying application for team {team_id} with subdomain {subdomain} and image {image_name}")
        logging.debug(f"Registry credentials: {registry_credentials}")

        container_info = deploy_container(image_name, subdomain, container_name=f"team-{team_id}",
                                            registry_credentials=registry_credentials, network=traefik_network,
                                            traefik_domain=traefik_domain, timeout=deploy_timeout)
        application["status"] = container_info[0]
        application["container_id"] = container_info[1]
        application["container_name"] = container_info[2]
        application["route"] = container_info[3]
        application["logs"] = container_info[4]

    except InvalidParameterError as e:
        application["status"] = "invalid_parameter"
        application["error"] = str(e)
        err = str(e)
        status_code = 400
    except DockerContainerStartError as e:
        application["status"] = e.container_status
        application["error"] = str(e)
        application["logs"] = e.container_logs
        err = str(e)
        status_code = 400
    except InternalDockerError as e:
        return None, str(e), 500
    finally:
        status = 'success' if status_code == 200 else err
        store_data_for_callback(application, status, status_code)

    try:
        save_to_redis(application)
    except InternalRedisError as e:
        return None, str(e), 500

    return application, err, status_code


def check_deploy_conditions(team_id, subdomain, redeploy=True):
    application = get_application_from_redis(team_id)
    subdomain_used = is_subdomain_used(subdomain)

    if application and not redeploy:
        err = f'Application already exists for team {team_id}\n'
        logging.info(err)
        raise InvalidParameterError(err)
    elif application and redeploy:
        logging.info(f"Application already exists for team {team_id}. Redeploying...")
        container_id = application.get('container_id')
        try:
            delete_container(container_id)
        except InternalDockerError as e:
            err = f"Failed to delete container {container_id} for team {team_id}\n"
            logging.error(err)
            raise InternalError(err)
    elif subdomain_used:
        err = f'Subdomain {subdomain} is already in use\n'
        logging.error(err)
        raise InvalidParameterError(err)
    elif not application and not subdomain_used:
        logging.info(f"No application found for team {team_id}. Deploying...")
    else:
        err = "Unhandled situation while checking for application existence\n"
        logging.error(err)
        raise InternalError(err)


def delete_application(team_id, force=False):
    try:
        application = get_application_from_redis(team_id)
        if not application:
            err = f'No application found for team {team_id}\n'
            logging.info(err)
            return err, 404

        status = application.get('status')
        container_id = application.get('container_id')

        if not container_id and status == 'running':
            err = f'No container information stored for team {team_id}\n'
            logging.error(err)
            return err, 500
    except InternalRedisError as e:
        return str(e), 500

    try:
        if status == 'running':
            delete_container(application.get('container_id'))
    except InternalDockerError as e:
        err = f"Failed to delete container {container_id} for team {team_id}\n" \
              f"Error: {str(e)}\n"
        logging.error(err)
        if not force:
            return err, 500
        else:
            logging.info(f"Force deleting application records for team {team_id}")

    try:
        delete_from_redis(team_id)
        logging.info(f"Successfully deleted application for team {team_id}")
    except InternalRedisError as e:
        return str(e), 500

    return None, 200


def delete_all_applications(force=False):
    # Get all team_ids from the 'managed_applications' set
    team_ids = get_all_team_ids()
    deleted = []
    errors = []

    # For each team_id, try to delete its associated container
    for team_id in team_ids:
        err, status = delete_application(team_id, force=force)
        if err:
            errors.append(err)
        deleted.append(team_id)

    if len(errors) > 0:
        err = f"Failed to delete {len(errors)} applications " \
              f"out of {len(team_ids)}\n"
        logging.error(err)
        return deleted, '\n'.join(errors), 500

    logging.info(f"Successfully deleted {len(deleted)} applications")
    return deleted, None, 200


def get_application(team_id):
    try:
        application = get_application_from_redis(team_id)
        if not application:
            err = f'No application found for team {team_id}\n'
            logging.info(err)
            return err, 404
        return application, 200
    except InternalRedisError as e:
        return str(e), 500


def get_applications():
    try:
        applications = get_applications_from_redis()
    except InternalRedisError as e:
        return str(e), 500
    return applications, 200


def reset_redis():
    try:
        flush_redis()
    except InternalRedisError as e:
        return str(e), 500
    return "Redis has been reseted!\n", 200
