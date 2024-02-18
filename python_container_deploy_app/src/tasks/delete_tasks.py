import logging

from shared.docker_wrapper.docker_delete import delete_container, InternalDockerError
from shared.persistance.redis_persistance import delete_from_redis, get_all_team_ids, InternalRedisError
from shared.persistance.redis_persistance import get_application as get_application_from_redis


def delete_application(team_id, force=False):
    """
    Deletes an application for a given team ID by removing its associated container and Redis records. If the container
    is running, it attempts to delete the container. If the container cannot be deleted and the `force` flag is not set,
    the deletion process stops. If `force` is true, it proceeds to remove the application's Redis records regardless of
    container deletion success.

    :param team_id: str. The unique identifier for the team whose application is to be deleted.
    :param force: bool, optional. A flag to force deletion of the application records even if the container cannot be
                  deleted (default is False).

    :return: Tuple (str or None, int). Returns a tuple containing an error message (or None if successful) and an HTTP
             status code (200 for success, 404 if the application does not exist, 500 for internal errors).

    :raises InternalRedisError: If an error occurs while accessing Redis data.

    Note: The function leverages custom error handling for Redis and Docker-related operations, ensuring application data
    consistency across the system. It requires the `get_application_from_redis` and `delete_from_redis` functions for Redis
    operations and `delete_container` for Docker container management.
    """
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
    """
    Iteratively deletes all applications listed in the 'managed_applications' set in Redis. It attempts to delete each
    application's associated container and Redis records. The function can optionally force the deletion of Redis records
    regardless of container deletion success based on the `force` parameter.

    :param force: bool, optional. A flag to force deletion of the application records even if the container cannot be
                  deleted (default is False).

    :return: Tuple (list, str or None, int). Returns a tuple containing a list of team IDs for which applications were
             attempted to be deleted, an aggregated error message (or None if all deletions were successful), and an HTTP
             status code (200 for success, 500 if any deletions fail).

    :raises InternalRedisError: If an error occurs while accessing or modifying Redis data.

    Note: This function uses `get_all_team_ids` to retrieve all application team IDs and `delete_application` to handle
    individual application deletions. It accumulates errors, if any, and returns them along with the status of the operation.
    """
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
