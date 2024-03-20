import requests
import logging
import rq


def notify_callback_url(job, *args, **kwargs):
    """
    Sends a notification to a specified callback URL with details about a job's execution status and associated application data.
    It constructs a payload containing the job ID, job status, and application information, then makes a POST request to the callback URL.

    :param job: The RQ job instance from which metadata is retrieved, including the callback URL and application data.
    :param args: Additional arguments (unused in this function, but included for flexibility and future extensions).
    :param kwargs: Additional keyword arguments (unused in this function, but included for flexibility and future extensions).

    Note: The function logs an error if the POST request to the callback URL fails due to any request-related exception.
    This ensures that the system is aware of failures in notifying external services or endpoints about the job status.
    """
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
    """
    Stores application data, status, and status code in the metadata of the current RQ job for later use,
    such as notifying a callback URL. This function is intended to be called within the context of an RQ job
    to capture the outcome of job execution along with any relevant application details.

    :param application: dict. The application data associated with the job.
    :param status: str. The execution status of the job (e.g., 'success', 'failed').
    :param status_code: int. An HTTP-like status code indicating the result of the job execution (e.g., 200, 400, 500).

    Note: This function assumes it is called within the context of an RQ worker job. It retrieves the current job using
    `rq.get_current_job` and updates its metadata with the provided application data, status, and status code. The metadata
    is then saved, making it accessible for further processing or for callbacks.
    """
    # Get current job
    job = rq.get_current_job()
    if job:
        # Store results in job meta data
        job.meta['application'] = application
        job.meta['status'] = status
        job.meta['status_code'] = status_code
        job.save_meta()
