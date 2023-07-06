from flask import Flask, request, jsonify
from tasks import deploy_application_logic, delete_container, delete_all_containers
from tasks import queue, redis_db
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)


@app.route('/', methods=['GET'])
def home():
    return "The service is running!\n", 200


@app.route('/reset-redis', methods=['GET'])
def reset_redis():
    redis_db.flushdb()
    return "Redis has been reseted!\n", 200


@app.route('/application/<string:team_id>', methods=['GET'])
def get_application(team_id):
    # Get application data from the hash associated with the team_id
    application = redis_db.hgetall(team_id)
    # If application_data is not None, convert it to a dict and return it
    if application:
        return jsonify(application), 200
    else:
        return jsonify({"message": "Application not found for team " + team_id}), 404


@app.route('/application/<string:team_id>', methods=['POST'])
def deploy_application(team_id):
    public_hash = request.args.get('public-hash', team_id)
    docker_registry = request.args.get('docker-registry', None)
    image_name = request.args.get('image-name', get_image_name(team_id))
    redeploy = request.args.get('redeploy', 'true').lower() in ['true', '1', 'yes']
    callback_url = request.args.get('callback-url', None)

    # Log the types and values
    logging.info(f"Type and value of team_id: {type(team_id)}, {team_id}")
    logging.info(f"Type and value of public_hash: {type(public_hash)}, {public_hash}")
    logging.info(f"Type and value of docker_registry: {type(docker_registry)}, {docker_registry}")
    logging.info(f"Type and value of image_name: {type(image_name)}, {image_name}")
    logging.info(f"Type and value of redeploy: {type(redeploy)}, {redeploy}")

    # Enqueue the function call
    job = queue.enqueue_call(func=deploy_application_logic,
                         args=(team_id, public_hash, image_name, docker_registry, redeploy))

    # Enqueue the callback
    if callback_url is not None:
        job.callback = 'notify_callback_url'
        job.meta['callback_url'] = callback_url
        job.save_meta()

    return jsonify({"message": "Deployment started", "job_id": job.get_id()}), 202

@app.route('/application', methods=['GET'])
def get_all_applications():
    applications = []
    # Iterate over all team_ids in the managed_applications set
    for team_id in redis_db.smembers('managed_applications'):
        # Get application data from the hash associated with the team_id
        applications.append(redis_db.hgetall(team_id))
        # If application_data is not None, convert it to a dict and append to applications list
    return jsonify(applications), 200


@app.route('/application/<string:team_id>', methods=['DELETE'])
def delete_application(team_id):
    # Delete the specified application
    success, message = delete_container(team_id)
    if success:
        return jsonify({"message": "Application deleted for team " + team_id}), 200
    else:
        return message, 500


@app.route('/application', methods=['DELETE'])
def delete_all_applications():
    delete_all = request.args.get('delete-all-applications', None)
    # If delete_all is true, delete all applications
    if delete_all and delete_all.lower() in ['true', '1', 'yes']:
        num_deleted = delete_all_containers()
        return jsonify({"message": f"All {num_deleted} applications deleted"}), 200
    else:
        return jsonify({"message": "Delete all flag not set"}), 400

def get_image_name(team_id):
    return f"traefik/whoami"


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')