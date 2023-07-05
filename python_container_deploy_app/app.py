from flask import Flask, request
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


@app.route('/test', methods=['GET'])
def test_redis():
    key = request.args.get('key', None)
    value = request.args.get('value', None)

    if key and value:
        redis_db.set(key, value)

    all_values = {key: redis_db.get(key) for key in redis_db.keys()}

    return all_values, 200


@app.route('/deploy', methods=['GET'])
def deploy():
    image_name = request.args.get('image_name', None)
    subdomain = request.args.get('subdomain', 'default')
    registry = request.args.get('registry', None)
    container_name = f"{subdomain}_container"

    if registry:
        image_name = registry + "/" + image_name

    if image_name is None:
        logging.info('Missing image name.')
        return 'Missing image name.\n', 400

    if subdomain in managed_containers:
        logging.info('Subdomain already in use.')
        return 'Subdomain already in use.\n', 400

    try:
        labels = {
            "traefik.enable": "true",
            "traefik.http.routers.{}.rule".format(subdomain): "Host(`{}.{}`)".format(subdomain, traefik_domain),
        }
        logging.info('Attempting to run container from image: {}'.format(image_name))
        container = client.containers.run(image_name,
                                          name=container_name,
                                          detach=True,
                                          labels=labels,
                                          network=traefik_network)
        logging.info('Started container with id: {}'.format(container.short_id))

        managed_containers[subdomain] = container_name
        return f'Started container with id {container.short_id} on subdomain {subdomain}\n', 200

    except docker.errors.ImageNotFound:
        logging.error('Image {} not found.'.format(image_name))
        return f'Image {image_name} not found.\n', 404
    except docker.errors.APIError as e:
        logging.error('API error: {}'.format(str(e)))
        return str(e) + '\n', 500


@app.route('/delete', methods=['GET'])
def delete():
    subdomain = request.args.get('subdomain', None)

    if subdomain is None:
        logging.info('Missing subdomain.')
        return 'Missing subdomain.\n', 400

    if subdomain not in managed_containers:
        logging.info('Subdomain not found.')
        return 'Subdomain not found.\n', 400

    success, message = delete_container(subdomain)
    if success:
        return message, 200
    else:
        return message, 500


@app.route('/delete_all', methods=['GET'])
def delete_all():
    errors = []
    for subdomain in list(managed_containers.keys()):  # Create a copy of the keys list to avoid errors due to modifications during iteration
        success, message = delete_container(subdomain)
        if not success:
            errors.append(message)

    if errors:
        return 'Some containers could not be stopped and removed:\n' + ''.join(errors), 500

    return 'All managed containers have been stopped and removed.\n', 200


def delete_container(subdomain):
    try:
        container = client.containers.get(managed_containers[subdomain])
        container.stop()
        container.remove()
        del managed_containers[subdomain]
        return True, f'Stopped and removed container for subdomain {subdomain}\n'
    except docker.errors.NotFound:
        logging.error(f'Container for subdomain {subdomain} not found.')
        return False, f'Container for subdomain {subdomain} not found.\n'
    except docker.errors.APIError as e:
        logging.error(f'API error for subdomain {subdomain}: {str(e)}')
        return False, f'API error for subdomain {subdomain}: {str(e)}\n'



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')