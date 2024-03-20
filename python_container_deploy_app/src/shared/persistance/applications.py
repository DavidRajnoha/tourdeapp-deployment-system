import json
import logging
import os
import time
from typing import Optional

import requests

from shared.persistance.redis_persistance import save_to_redis, InternalRedisError, flush_redis
from shared.persistance.redis_persistance import get_applications as get_applications_from_redis
from shared.persistance.redis_persistance import get_application as get_application_from_redis

traefik_domain = os.environ.get('BASE_DOMAIN', 'localhost')
traefik_network = os.environ.get('TRAEFIK_NETWORK', 'traefik_default')
deploy_timeout = int(os.environ.get('DEPLOY_TIMEOUT', 60))
loki_url = os.environ.get('LOKI_URL', 'http://loki:3100/')

logging.basicConfig(level=logging.INFO)


class InternalError(Exception):
    pass


def get_application(team_id):
    """
    Retrieves an application's details for a specified team ID from Redis and updates its logs by querying Loki.
    If the application is found in Redis, it attempts to update the logs before returning the application object.
    The function returns a tuple containing the application data (or an error message) and an HTTP status code.
    The status code indicates whether the operation was successful (200), not found (404), or resulted in an internal
    error (500).

    :param team_id: str. The unique identifier of the team whose application details are being retrieved.

    :return: Tuple (dict or str, int). The function returns a tuple where the first element is either the application
             object (as a dictionary) with updated logs or an error message (as a string) if the application cannot be
             found or an internal error occurs. The second element is an HTTP status code indicating the outcome of the
             operation (200, 404, or 500).

    Note: This function relies on the presence of a custom exception `InternalRedisError` to handle Redis-related errors
    and assumes the existence of globally accessible functions `get_application_from_redis` for fetching the application
    from Redis and `update_logs` for updating the application's logs from Loki. It also assumes a configured logger is
    available for logging information and errors.
    """
    try:
        application = get_application_from_redis(team_id)

        if not application:
            err = f'No application found for team {team_id}\n'
            logging.info(err)
            return err, 404

        application = update_logs(application)
        return application, 200
    except InternalRedisError as e:
        return str(e), 500


def update_logs(application):
    """
    Updates the application's log entries by querying Loki for the latest logs associated with the application's container.
    It performs this update if the logs are older than 60 seconds or if it's the initial update (logs are missing).
    The function checks for the presence of 'container_id' in the application object and queries Loki using this identifier.
    If successful, it updates the application object with the latest logs and the timestamp of the update. If the logs
    cannot be retrieved or if there's an issue with saving the updated logs to Redis, the function logs the appropriate
    error but still returns the application object, potentially unmodified.

    :param application: dict. A dictionary representing the application, containing at least 'logs_updated_at',
                        'container_id', and 'team_id' keys.
    :return: dict. The updated application object, which may include new log entries and an updated 'logs_updated_at' timestamp.

    Note: This function assumes global access to a configured logger, the URL of the Loki instance (`loki_url`),
    and a function `save_to_redis` for persisting the application object. It handles exceptions raised by the requests
    library for HTTP requests and a custom `InternalRedisError` for Redis operations.
    """
    logs_updated_at: Optional[str] = application.get('logs_updated_at')

    if logs_updated_at and time.time() - float(logs_updated_at) < 60:
        logging.debug(f"Logs for team {application.get('team_id')} are up to date")
        return application

    container_id = application.get('container_id')
    if not container_id:
        err = f'No container information stored for team {application.get("team_id")}\n'
        logging.info(err)
        return application

    query = "{container_id=\"" + container_id + "\"}"
    url = f'{loki_url}/loki/api/v1/query_range?query={query}'

    try:
        response = requests.get(url)
        response.raise_for_status()
        logs = response.json()
        application['logs_updated_at'] = time.time()

        if not logs['data']['result']:
            logging.debug(f"No logs found for container {container_id}")
            return application

        application['logs'] = json.dumps(logs['data']['result'][0]['values'])

        try:
            save_to_redis(application)
        except InternalRedisError as e:
            logging.error(f"Failed to save application {application} to redis")

        return application

    except requests.exceptions.RequestException as e:
        err = f'Failed to get logs for container {container_id}: {str(e)}\n'
        logging.error(err)
        return application


def get_applications():
    """
    Retrieves a list of all applications stored in Redis and updates their logs by querying Loki for each application.
    This operation is atomic - either all applications are successfully updated, or an error is returned without partial updates.
    If an error occurs while accessing Redis, the function returns an error message and a 500 status code.

    :return: Tuple (list or str, int). Returns a tuple where the first element is a list of application objects
             (each as a dictionary) with updated logs, or an error message (as a string) if an internal error occurs
             during the Redis operation. The second element is an HTTP status code indicating the outcome of the operation
             (200 for success, 500 for internal errors).

    Note: Assumes global access to `get_applications_from_redis` for fetching applications and `update_logs`
    for updating logs for each application. Relies on handling a custom `InternalRedisError` exception for Redis-related
    errors. Applications are expected to be dictionaries with necessary information for `update_logs`.
    """
    try:
        applications = get_applications_from_redis()
        map(update_logs, applications)
    except InternalRedisError as e:
        return str(e), 500
    return applications, 200


def reset_redis():
    """
    Resets the Redis database by flushing all stored data. This action clears all applications and their associated data
    from Redis. If an error occurs during the flushing operation, the function returns an error message and a 500 status
    code.

    :return: Tuple (str, int). Returns a tuple where the first element is a success message indicating that Redis has been
             reset, or an error message (as a string) if an internal error occurs during the flush operation. The second
             element is an HTTP status code (200 for success, 500 for internal errors).

    Note: This function assumes the presence of a `flush_redis` function for performing the reset operation and
    handles `InternalRedisError` for any Redis-related errors that occur. It is intended for administrative or
    maintenance purposes and should be used with caution.
    """
    try:
        flush_redis()
    except InternalRedisError as e:
        return str(e), 500
    return "Redis has been reseted!\n", 200
