import redis
import logging
import os

redis_host = os.getenv('REDIS_HOST', 'redis-db')
redis_port = int(os.getenv('REDIS_PORT', 6379))
rq_db_id = int(os.getenv('RQ_DB', 1))

redis_db = redis.Redis(host=redis_host, port=redis_port, db=0, charset="utf-8", decode_responses=True)
redis_queue = redis.Redis(host=redis_host, port=redis_port, db=rq_db_id, charset="utf-8")


def get_application(team_id):
    """
    Retrieves an application's data from Redis using the provided team ID. It checks if the application is listed
    in the set of managed applications before attempting to fetch its data. If the application is not found or if
    the Redis data is inconsistent (the application is listed but no data is found), the function logs an error
    and raises an InternalRedisError.

    :param team_id: str. The unique identifier for the team whose application data is being retrieved.

    :return: dict or None. The application data as a dictionary if found; otherwise, None.

    :raises InternalRedisError: If there's an inconsistency in the Redis data or if the application data cannot be retrieved.

    Note: Assumes a global Redis connection (`redis_db`) is available and that logging is configured for the application.
    """
    # Check if the application already exists
    if redis_db.sismember('managed_applications', team_id):
        application = redis_db.hgetall(team_id)
        if not application:
            err = f'No application data for team {team_id}, the state of the db is inconsistent\n'
            logging.error(err)
            raise InternalRedisError(err)
        return application
    return None


def get_applications():
    """
    Retrieves the data for all applications listed in the set of managed applications in Redis. It iterates over
    all team IDs in the managed applications set, fetching each application's data. If any application data cannot
    be found or if the Redis data is inconsistent, it logs an error and raises an InternalRedisError.

    :return: list. A list of dictionaries, each representing an application's data.

    :raises InternalRedisError: If there's an inconsistency in the Redis data or if any application data cannot be retrieved.

    Note: Leverages the `get_application` function for fetching individual application data and assumes a global Redis
    connection (`redis_db`) and configured logging.
    """
    team_ids = get_all_team_ids()
    applications = []
    for team_id in team_ids:
        application = get_application(team_id)
        if not application:
            err = f'No application data for team {team_id}, the state of the db is inconsistent\n'
            logging.error(err)
            raise InternalRedisError(err)
        applications.append(application)
    return applications


def is_subdomain_used(subdomain):
    """
    Checks if a given subdomain is already used by any managed application by querying the set of used subdomains in Redis.

    :param subdomain: str. The subdomain to check for usage.

    :return: bool. True if the subdomain is already used; False otherwise.

    Note: Assumes a global Redis connection (`redis_db`) is available.
    """
    if redis_db.sismember('used_subdomains', subdomain):
        return True
    return False


def get_all_team_ids():
    """
    Retrieves all team IDs from the set of managed applications in Redis. This function is used to get a list of
    all applications that are currently managed.

    :return: set. A set of team IDs for all managed applications.

    Note: Assumes a global Redis connection (`redis_db`) is available.
    """
    return redis_db.smembers('managed_applications')


def save_to_redis(application):
    """
    Saves the application data to Redis, using the team ID as the key. It adds the team ID to a set of managed
    applications and the application's subdomain to a set of used subdomains. If the application does not contain an
    "error" field, any existing "error" field for the application in Redis is removed.

    :param application: dict. A dictionary containing the application data, including "team_id" and "subdomain" keys.

    :raises InternalRedisError: If any Redis operation fails, encapsulating the original Redis error.

    Note: This function assumes that a Redis connection (`redis_db`) is globally available and that logging is configured
    for the application. It is designed to ensure consistency in application state management within Redis.
    """
    team_id = application["team_id"]
    subdomain = application["subdomain"]

    try:
        redis_db.sadd('managed_applications', team_id)
        redis_db.sadd('used_subdomains', subdomain)

        # Remove the "error" field from Redis if it's not in the application dict
        if "error" not in application:
            logging.info("Removing error field from Redis")
            if redis_db.hexists(team_id, "error"):
                redis_db.hdel(team_id, "error")

        logging.info(f"Saving application data for team {team_id} to Redis")
        redis_db.hset(team_id, mapping=application)
    except redis.exceptions.RedisError as e:
        logging.error('Redis error: {}'.format(str(e)))
        raise InternalRedisError('Redis error: {}'.format(str(e)))


def delete_from_redis(team_id):
    """
    Deletes application data from Redis based on the given team ID. It removes the application's team ID from the
    set of managed applications and its subdomain from the set of used subdomains, then deletes all application data
    associated with the team ID.

    :param team_id: str. The unique identifier for the team whose application data is to be deleted.

    :return: Tuple (bool, str or None). Returns a tuple where the first element indicates success (True) or failure (False),
             and the second element provides an error message in case of failure or None if successful.

    Note: Assumes a global Redis connection (`redis_db`) and that logging is set up. This function also checks for
    consistency and handles cases where data may be partially present.
    """
    application = redis_db.hgetall(team_id)
    if not redis_db.sismember('managed_applications', team_id):
        if application:
            redis_db.hdel(team_id, 'container_id', 'route', 'subdomain', 'image_name', 'team_id')
            return False, f'Application data for team {team_id} exists but is not in the managed_applications set\n'
        return False, f'No application data for team {team_id}\n'

    if not application:
        return False, f'No application data for team {team_id}, the state of the db is inconsistent\n'

    pipeline = redis_db.pipeline()
    pipeline.srem('managed_applications', team_id)
    pipeline.srem('used_subdomains', application['subdomain'])
    pipeline.delete(team_id)
    pipeline.execute()
    logging.info(f'Deleted application data for team {team_id}\n')
    return True, None


def flush_redis():
    """
    Performs a complete flush of all data stored in Redis, effectively resetting the database to its initial empty state.
    This operation is used for clearing all application data and metadata from Redis.

    :raises InternalRedisError: If the flush operation fails due to a Redis error, encapsulating the original Redis error.

    Note: This function assumes that a Redis connection (`redis_db`) is globally available and that logging is configured
    for monitoring purposes. It's intended for use in situations requiring a clean slate or for maintenance tasks.
    """
    try:
        redis_db.flushall()
        logging.info('Flushed redis\n')
    except redis.exceptions.RedisError as e:
        logging.error('Redis error: {}'.format(str(e)))
        raise InternalRedisError('Redis error: {}'.format(str(e)))


class InternalRedisError(Exception):
    pass
