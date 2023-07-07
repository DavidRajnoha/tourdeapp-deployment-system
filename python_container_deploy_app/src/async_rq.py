import requests
import logging
from rq import Queue
import rq
from src.persistance import redis_queue

queue = Queue('default', connection=redis_queue)

def notify_callback_url(job, *args, **kwargs):
    callback_url = job.meta.get('callback_url')
    application = job.meta.get('application', {})

    if callback_url:
        try:
            requests.post(callback_url, json={
                'job_id': job.get_id(),
                'status': job.get_status(),
                'application': application,
            })
        except requests.exceptions.RequestException as e:
            logging.error("Failed to send callback to URL: %s", callback_url)

def store_data_for_callback(application, status, status_code):
    # Get current job
    job = rq.get_current_job()
    if job:
        # Store results in job meta data
        job.meta['application'] = application
        job.meta['status'] = status
        job.meta['status_code'] = status_code
        job.save_meta()