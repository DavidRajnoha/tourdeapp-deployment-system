import logging

from shared.docker_wrapper.docker_delete import delete_container, InternalDockerError
from shared.persistance.redis_persistance import delete_from_redis, get_all_team_ids, InternalRedisError
from shared.persistance.redis_persistance import get_application as get_application_from_redis


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
