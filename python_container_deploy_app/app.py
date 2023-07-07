from flask import Flask, request, jsonify
from src.tasks import deploy_application as deploy_application_task
from src.tasks import delete_application as delete_application_task
from src.tasks import delete_all_applications as delete_all_applications_task
from src.tasks import get_application as get_application_task
from src.tasks import get_applications as get_applications_task
from src.tasks import reset_redis as reset_redis_task


from src.async_rq import queue
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)


@app.route('/', methods=['GET'])
def home():
    return "The service is running!\n", 200


@app.route('/reset-redis', methods=['GET'])
def reset_redis():
    message, status = reset_redis_task()
    return jsonify({"message": message}), status


@app.route('/application/<string:team_id>', methods=['GET'])
def get_application(team_id):
    # Get application data from the hash associated with the team_id
    result, status = get_application_task(team_id)
    if status == 200:
        return jsonify(result), status
    else:
        return jsonify({"message": result}), status


@app.route('/application/<string:team_id>', methods=['POST'])
def deploy_application(team_id):
    public_hash = request.args.get('public-hash', team_id)
    docker_registry = request.args.get('docker-registry', None)
    image_name = request.args.get('image-name', get_image_name(team_id))
    redeploy = request.args.get('redeploy', 'true').lower() in ['true', '1', 'yes']
    callback_url = request.args.get('callback-url', None)

    # Enqueue the function call
    job = queue.enqueue_call(func=deploy_application_task,
                             args=(team_id, public_hash, image_name, docker_registry, redeploy))

    # Enqueue the callback
    if callback_url is not None:
        job.callback = 'notify_callback_url'
        job.meta['callback_url'] = callback_url
        job.save_meta()

    return jsonify({"message": "Deployment started", "job_id": job.get_id()}), 202

@app.route('/application', methods=['GET'])
def get_all_applications():
    applications, status = get_applications_task()
    return jsonify(applications), status


@app.route('/application/<string:team_id>', methods=['DELETE'])
def delete_application(team_id):
    # Delete the specified application
    err, status = delete_application_task(team_id)
    if status == 200:
        return jsonify({"team_id": team_id}), status
    else:
        return jsonify({"message": err}), status


@app.route('/application', methods=['DELETE'])
def delete_all_applications():
    delete_all = request.args.get('delete-all-applications', None)
    # If delete_all is true, delete all applications
    if delete_all and delete_all.lower() in ['true', '1', 'yes']:
        deleted, err, status = delete_all_applications_task()
        return jsonify({"deleted_ids": deleted}), 200
    else:
        return jsonify({"message": "Delete all flag not set"}), 400

def get_image_name(team_id):
    return f"traefik/whoami"


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')