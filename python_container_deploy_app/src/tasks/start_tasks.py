import logging

from shared.docker_wrapper.docker_start import InternalDockerError, InvalidParameterError, start_container
from shared.persistance.redis_persistance import save_to_redis, InternalRedisError
from shared.persistance.redis_persistance import get_applications as get_applications_from_redis


def resume_stopped_containers():
    try:
        applications = get_applications_from_redis()
        logging.info(f"Found {len(applications)} applications")
    except InternalRedisError as e:
        return str(e), 500
    for application in applications:
        logging.info(f"Resuming application {application}")
        team_id = application.get('team_id')
        container_id = application.get('container_id')
        status = application.get('status')
        if not container_id and status == 'running':
            logging.info(f"Container for team {team_id} was not running, skipping...")
            continue
        elif not container_id:
            logging.info(f"Container for team {team_id} was not running, but status was {status}, skipping")
            continue

        try:
            started_at, _ = start_container(container_id)
            logging.info(f"Successfully started container {container_id} for team {team_id}")
            application["status"] = "running"
            if started_at:
                application["started_at"] = started_at
        except InvalidParameterError as e:
            err = f"Failed to start container {container_id} for team {team_id}\n" \
                  f"Error: {str(e)}\n"
            logging.error(err)
            application["status"] = "internal_error"
        except InternalDockerError as e:
            err = f"Failed to start container {container_id} for team {team_id}\n" \
                  f"Error: {str(e)}\n"
            logging.error(err)
            application["status"] = "internal_error"

        try:
            save_to_redis(application)
        except InternalRedisError as e:
            logging.error(f"Failed to save application {application} to redis")
            return None, str(e), 500
