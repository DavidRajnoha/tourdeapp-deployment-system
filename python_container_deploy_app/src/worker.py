import redis
import os
from rq import Worker
import logging
import sys

import tasks.start_tasks

logging.basicConfig(level=logging.DEBUG)

logging.debug(f"Current Working Directory: {os.getcwd()}")

pythonpath = os.environ.get('PYTHONPATH', 'PYTHONPATH not set')
logging.debug(f"PYTHONPATH: {pythonpath}")

logging.debug(f"sys.path: {sys.path}")

def log_directory_structure(startpath):
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        logging.debug(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            logging.debug(f"{subindent}{f}")

# Example usage
log_directory_structure(os.getcwd())

redis_host = os.getenv('REDIS_HOST', 'redis-db')
redis_port = int(os.getenv('REDIS_PORT', 6379))
rq_db_id = int(os.getenv('RQ_DB', 1))

redis_queue = redis.Redis(host='redis-db', port=redis_port, db=rq_db_id, charset="utf-8")
w = Worker('default', connection=redis_queue)
w.work()
