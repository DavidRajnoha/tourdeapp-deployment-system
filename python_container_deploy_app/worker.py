import redis
import os
from rq import Worker

redis_host = os.getenv('REDIS_HOST', 'redis-db')
redis_port = int(os.getenv('REDIS_PORT', 6379))
rq_db_id = int(os.getenv('RQ_DB', 1))

redis_queue = redis.Redis(host='redis-db', port=redis_port, db=rq_db_id, charset="utf-8")
w = Worker('default', connection=redis_queue)
w.work()