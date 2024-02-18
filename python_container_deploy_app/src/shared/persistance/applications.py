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
    Query Loki for logs for the given application
    Queries Loki if the logs are older than 60 seconds or the information is missing (first time update)
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
    try:
        applications = get_applications_from_redis()
        map(update_logs, applications)
    except InternalRedisError as e:
        return str(e), 500
    return applications, 200


def reset_redis():
    try:
        flush_redis()
    except InternalRedisError as e:
        return str(e), 500
    return "Redis has been reseted!\n", 200
