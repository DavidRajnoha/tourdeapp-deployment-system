from flask import Flask, request, jsonify
import docker
import logging
import os
import redis


app = Flask(__name__)
client = docker.from_env()
managed_containers = {}
traefik_domain = os.environ.get('BASE_DOMAIN', 'localhost')
traefik_network = os.environ.get('TRAEFIK_NETWORK', 'traefik_default')

logging.basicConfig(level=logging.INFO)

# Create a connection to the Redis server
redis_db = redis.Redis(host='redis-db', port=6379, db=0, charset="utf-8", decode_responses=True)

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
    public_hash = request.args.get('public-hash', None)
    docker_registry = request.args.get('docker-registry', None)
    image_name = request.args.get('image-name', get_image_name(team_id))
    redeploy = request.args.get('redeploy', 'true').lower() in ['true', '1', 'yes']

    application, error_message, status_code = deploy_application_logic(team_id, public_hash, image_name, docker_registry, redeploy)

    if application is not None:
        return jsonify(application), status_code
    else:
        return jsonify({"error": error_message}), status_code


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


def deploy_application_logic(team_id, public_hash, image_name, docker_registry=None, redeploy=True):
    subdomain = public_hash

    # Check if the application already exists
    if redis_db.sismember('managed_applications', team_id):
        if not redeploy:
            return None, 'Application with the given team_id already exists.\n', 409
        else:
            # Stop and remove the existing application before redeploying
            delete_container(team_id)

    # Check if the subdomain is already in use
    if redis_db.sismember('used_subdomains', subdomain):
        return None, f'Subdomain {subdomain} is already in use.\n', 409

    # Deploy the application
    try:
        container, route = deploy_container(image_name, subdomain, container_name=f"team-{team_id}", registry=docker_registry)
    except docker.errors.ImageNotFound:
        logging.error('Image {} not found.'.format(image_name))
        return None, f'Image {image_name} not found.\n', 404
    except docker.errors.APIError as e:
        logging.error('API error: {}'.format(str(e)))
        return None, str(e) + '\n', 500

    application = {
        "team_id": team_id,
        "container_id": container.id,
        "container_name": container.name,
        "route": route,
        "public_hash": public_hash,
        "subdomain": subdomain,
        "image_name": image_name
    }

    # Add the team_id to the set of managed applications
    redis_db.sadd('managed_applications', team_id)
    # Add the subdomain to the set of used subdomains
    redis_db.sadd('used_subdomains', subdomain)

    # Store the application details in a hash map
    redis_db.hset(team_id, mapping=application)

    return application, None, 200


def deploy_container(image_name, subdomain, container_name, registry=None):
    if registry:
        image_name = registry + "/" + image_name

    routed_domain = f"{subdomain}.{traefik_domain}"

    labels = {
        "traefik.enable": "true",
        f"traefik.http.routers.{subdomain}.rule": f"Host(`{routed_domain}`)"
    }
    logging.info(f'Attempting to run container from image: {image_name}')
    container = client.containers.run(image_name,
                                      name=container_name,
                                      detach=True,
                                      labels=labels,
                                      network=traefik_network)
    logging.info('Started container with id: {}'.format(container.short_id))
    return container, routed_domain


def delete_container(team_id):
    # Get application data from Redis set
    application = redis_db.hgetall(team_id)
    if not redis_db.sismember('managed_applications', team_id):
        if application:
            redis_db.hdel(team_id, 'container_id', 'route', 'public_hash', 'subdomain', 'image_name', 'team_id')
            return False, f'Application data for team {team_id} exists but is not in the managed_applications set\n'
        return False, f'No application data for team {team_id}\n'

    if not application:
        return False, f'No application data for team {team_id}, the state of the db is inconsistent\n'

    container_id = application['container_id']
    try:
        container = client.containers.get(container_id)
        container.stop()
        container.remove()

        pipeline = redis_db.pipeline()
        pipeline.srem('managed_applications', team_id)
        pipeline.srem('used_subdomains', application['subdomain'])
        pipeline.delete(team_id)
        pipeline.execute()


        return True, f'Stopped and removed container for team {team_id}\n'
    except docker.errors.NotFound:
        logging.error(f'Container for team {team_id} not found.')
        return False, f'Container for team {team_id} not found.\n'
    except docker.errors.APIError as e:
        logging.error(f'API error for team {team_id}: {str(e)}')
        return False, f'API error for team {team_id}: {str(e)}\n'

def delete_all_containers():
    # Get all team_ids from the 'managed_applications' set
    team_ids = redis_db.smembers('managed_applications')

    # For each team_id, try to delete its associated container
    for team_id in team_ids:
        success, _ = delete_container(team_id)

    return len(team_ids)


def get_image_name(team_id):
    return f"traefik/whoami"



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')