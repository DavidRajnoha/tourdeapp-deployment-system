import redis
import logging
import os

redis_host = os.getenv('REDIS_HOST', 'redis-db')
redis_port = int(os.getenv('REDIS_PORT', 6379))
rq_db_id = int(os.getenv('RQ_DB', 1))

redis_db = redis.Redis(host=redis_host, port=redis_port, db=0, charset="utf-8", decode_responses=True)
redis_queue = redis.Redis(host=redis_host, port=redis_port, db=rq_db_id, charset="utf-8")

def get_application(team_id):
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
    if redis_db.sismember('used_subdomains', subdomain):
        return True
    return False


def get_all_team_ids():
    return redis_db.smembers('managed_applications')


def save_to_redis(application):
    team_id = application["team_id"]
    subdomain = application["subdomain"]

    try:
        redis_db.sadd('managed_applications', team_id)
        redis_db.sadd('used_subdomains', subdomain)
        redis_db.hset(team_id, mapping=application)
    except redis.exceptions.RedisError as e:
        logging.error('Redis error: {}'.format(str(e)))
        raise InternalRedisError('Redis error: {}'.format(str(e)))


def delete_from_redis(team_id):
    application = redis_db.hgetall(team_id)
    if not redis_db.sismember('managed_applications', team_id):
        if application:
            redis_db.hdel(team_id, 'container_id', 'route', 'public_hash', 'subdomain', 'image_name', 'team_id')
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
    try:
        redis_db.flushall()
        logging.info('Flushed redis\n')
    except redis.exceptions.RedisError as e:
        logging.error('Redis error: {}'.format(str(e)))
        raise InternalRedisError('Redis error: {}'.format(str(e)))


class InternalRedisError(Exception):
    pass
