from typing import List, Tuple, Set
import os
import redis

redis_host = os.getenv('REDIS_HOST', 'redis-db')
redis_port = int(os.getenv('REDIS_PORT', 6379))

redis_db = redis.Redis(host=redis_host, port=redis_port, db=0, charset="utf-8", decode_responses=True)


def get_team_data_from_db() -> List[Tuple[str, str, str, str]]:
    # get the team data from database
    team_data = []
    for team_id in redis_db.keys():
        url = redis_db.hget(team_id, 'url')
        hash_value = redis_db.hget(team_id, 'hash')
        team_name = redis_db.hget(team_id, 'team_name')
        team_data.append((url, team_id, hash_value, team_name))
    return team_data


def persist_team_data(team_data: List[Tuple[str, str, str, str]]):
    # save the team data to database
    for url, team_id, hash_value, team_name in team_data:
        redis_db.hset(team_id, mapping={'url': url, 'hash': hash_value, 'team_name': team_name})


def delete_all_data_from_db():
    """
    Delete all keys and their associated values from the Redis database.
    """
    try:
        # Fetch all keys from the Redis database
        all_keys = redis_db.keys()

        # Delete each key
        for key in all_keys:
            redis_db.delete(key)

        print("All data deleted successfully.")

    except Exception as e:
        # Handle any exceptions
        print(f"An error occurred: {e}")
