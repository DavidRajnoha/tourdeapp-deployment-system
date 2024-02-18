import os
from flask import Flask, request, jsonify
from tasks.run_tasks import deploy_application as deploy_application_task
from tasks.delete_tasks import delete_application as delete_application_task
from tasks.delete_tasks import delete_all_applications as delete_all_applications_task
from tasks.start_tasks import resume_stopped_containers as resume_stopped_containers_task
from shared.persistance.applications import get_application
from shared.persistance.applications import get_applications
from shared.persistance.applications import reset_redis
from shared.persistance.redis_persistance import redis_queue
from shared.utils import get_log_level, get_image_name
from rq import Queue

import logging

app = Flask(__name__)
queue = Queue('default', connection=redis_queue)
logging.basicConfig(level=get_log_level())


@app.route('/', methods=['GET'])
def home():
    """
    A simple endpoint to check the service status.

    :return: A plain text message indicating the service is running and an HTTP 200 status code.
    """
    return "The service is running!\n", 200


@app.route('/reset-redis', methods=['GET'])
def reset_redis_endpoint():
    """
    Endpoint to reset all data in Redis. This action is irreversible and clears all stored application and container data.

    :return: JSON response with a message indicating the result of the Redis reset operation and the corresponding HTTP status code.
    """
    message, status = reset_redis()
    return jsonify({"message": message}), status


@app.route('/application/<string:team_id>', methods=['GET'])
def get_application_endpoint(team_id):
    """
    Retrieves the application data associated with a given team ID from Redis.

    :param team_id: The unique identifier for the team whose application data is being requested.
    :return: JSON response containing the application data if found, with an HTTP 200 status,
             or an error message with the corresponding HTTP status code.
    """
    result, status = get_application(team_id)
    if status == 200:
        return jsonify(result), status
    else:
        return jsonify({"message": result}), status


@app.route('/application/<string:team_id>', methods=['POST'])
def deploy_application_endpoint(team_id):
    """
    Initiates the deployment of an application based on the provided parameters. This includes setting up a Docker
    container for the application and configuring routing with Traefik.

    :param team_id: Path parameter specifying the team ID for which the application is deployed.
    :return: JSON response with a message indicating that deployment has started and the job ID, along with an HTTP 202 status code.
    """
    subdomain = request.args.get('subdomain', team_id)
    registry_credentials = request.args.get('registry-credentials', None)
    image_name = request.args.get('image-name', get_image_name(team_id))
    redeploy = request.args.get('redeploy', 'true').lower() in ['true', '1', 'yes']
    callback_url = request.args.get('callback-url', None)

    # Enqueue the function call
    job = queue.enqueue_call(func=deploy_application_task,
                             args=(team_id, subdomain, image_name, registry_credentials, redeploy))

    # Enqueue the callback
    if callback_url is not None:
        job.callback = 'notify_callback_url'
        job.meta['callback_url'] = callback_url
        job.save_meta()

    return jsonify({"message": "Deployment started", "job_id": job.get_id()}), 202


@app.route('/application', methods=['PUT'])
def restart_all_applications_endpoint():
    """
    Endpoint to restart all stopped applications. It queues a job to resume all stopped Docker containers
    associated with applications stored in Redis.

    :return: JSON response with a message indicating that the restart process has started and the job ID,
             along with an HTTP 202 status code.
    """
    callback_url = request.args.get('callback-url', None)

    # Enqueue the function call
    job = queue.enqueue_call(func=resume_stopped_containers_task)

    # Enqueue the callback
    if callback_url is not None:
        job.callback = 'notify_callback_url'
        job.meta['callback_url'] = callback_url
        job.save_meta()

    return jsonify({"message": "Restart of all aplications started", "job_id": job.get_id()}), 202


@app.route('/application', methods=['GET'])
def get_all_applications_endpoint():
    """
    Retrieves data for all applications stored in Redis.

    :return: JSON response containing an array of application data and the corresponding HTTP status code.
    """
    applications, status = get_applications()
    return jsonify(applications), status


@app.route('/application/<string:team_id>', methods=['DELETE'])
def delete_application_endpoint(team_id):
    """
    Deletes the application associated with the provided team ID. Supports a forced deletion mode via query parameters.

    :param team_id: Path parameter specifying the team ID for which the application is to be deleted.
    :return: JSON response with the team ID on successful deletion or an error message, along with the corresponding HTTP status code.
    """
    force = request.args.get('force', 'false').lower() in ['true', '1', 'yes']

    # Delete the specified application
    err, status = delete_application_task(team_id, force=force)
    if status == 200:
        return jsonify({"team_id": team_id}), status
    else:
        return jsonify({"message": err}), status


@app.route('/application', methods=['DELETE'])
def delete_all_applications_endpoint():
    """
    Deletes all applications if the appropriate flag is set. Supports a forced deletion mode via query parameters.

    :return: JSON response with a list of deleted team IDs or an error message, along with the corresponding HTTP status code.
    """
    force = request.args.get('force', 'false').lower() in ['true', '1', 'yes']
    delete_all = request.args.get('delete-all-applications', None)

    # If delete_all is true, delete all applications
    if delete_all and delete_all.lower() in ['true', '1', 'yes']:
        deleted, err, status = delete_all_applications_task(force=force)
        return jsonify({"deleted_ids": deleted}), 200
    else:
        return jsonify({"message": "Delete all flag not set"}), 400


if __name__ == '__main__':
    debug_mode = os.environ.get('DEBUG_MODE', 'False').lower() == 'true'
    if debug_mode:
        logging.warning("Application is running in debug mode")
        app.run(debug=debug_mode, host='0.0.0.0')
