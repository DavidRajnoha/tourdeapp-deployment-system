import random

import backoff
import requests
import pytest
import configparser
from requests.auth import HTTPBasicAuth
import socket
import getpass
from concurrent.futures import ThreadPoolExecutor
import concurrent
import docker
import string
import os


@pytest.fixture(scope='session')
def docker_client():
    return docker.from_env()


@pytest.fixture(scope='session')
def config():
    """Loads and returns the configuration."""
    config_parser = configparser.ConfigParser()
    config_parser.read('config.ini')

    # A helper function to get the configuration value
    # with an environment variable override
    def get_config(section, option, env_var=None, default=None):
        # If an environment variable is specified and exists, return its value
        if env_var and env_var in os.environ:
            return os.environ[env_var]
        # Otherwise, return the value from config.ini or the default
        return config_parser.get(section, option, fallback=default)

        # Use a dictionary to structure the config for easy access
    config_map = {
        'cleanup': {
            'cleanup': get_config('cleanup', 'cleanup', env_var='CLEANUP', default='false').lower() in ['true', '1',
                                                                                                        't', 'y',                                                                             'yes'],
        },
        'url': {
            'base_domain': get_config('url', 'base_domain', env_var='BASE_DOMAIN'),
        },
        'images': {
            'whoami': get_config('images', 'whoami', env_var='IMAGE_WHOAMI'),
            'always_fail': get_config('images', 'always_fail', env_var='IMAGE_ALWAYS_FAIL'),
            'platform': get_config('images', 'platform', env_var='PLATFORM'),
            'custom_registry': get_config('images', 'custom_registry', env_var='REGISTRY'),
            'custom_registry_user': get_config('images', 'custom_registry_user', env_var='REGISTRY_USER'),
            'custom_registry_password': get_config('images', 'custom_registry_password',
                                                   env_var='REGISTRY_PASSWORD'),
        },
        'auth': {
            'username': get_config('auth', 'username', env_var='AUTH_USERNAME'),
            'password': get_config('auth', 'password', env_var='AUTH_PASSWORD'),
        }
    }
    return config_map


@pytest.fixture
def cleanup(config):
    return config['cleanup']


@pytest.fixture
def domain_name(config):
    """Returns the domain name for the application deployment."""
    return config['url']['base_domain']


@pytest.fixture
def image_name(config):
    """Returns the image name to be used for the application deployment."""
    return config['images']['whoami']


@pytest.fixture
def always_fail_image_name(config):
    """Returns an image that fails on deployment."""
    return config['images']['always_fail']


@pytest.fixture
def platform(config):
    """Returns the platform to be used for the application deployment."""
    return config['images']['platform']


@pytest.fixture
def registry_credentials(config):
    """Returns the credentials for the custom Docker registry."""
    return f"{config['images']['custom_registry_user']}:{config['images']['custom_registry_password']}"


@pytest.fixture
def custom_registry_image(image_name, platform, config, docker_client):
    """
    Returns the image name to be used for the application deployment after performing several operations:

    1. Reads the custom Docker registry information from a configuration file ('config.ini').
    2. Logs into the custom Docker registry using the provided credentials.
    3. Pulls the specified Docker image from Docker Hub.
    4. Generates a random tag and retags the pulled image with this tag and the custom registry.
    5. Pushes the retagged image to the custom Docker registry.

    After the test execution, the fixture also removes the retagged image from the local machine.
    """
    custom_registry = config['images']['custom_registry']
    custom_registry_user = config['images']['custom_registry_user']
    custom_registry_password = config['images']['custom_registry_password']

    # Initialize Docker client
    client = docker_client
    client.login(username=custom_registry_user, password=custom_registry_password, registry=custom_registry)

    # Generate a random tag
    random_tag = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

    # Pull the image from Docker Hub
    image = client.images.pull(image_name, platform=platform)

    # Retag the image with the custom registry and random tag
    custom_registry_retagged_image = f"{custom_registry}/{image_name}:{random_tag}"
    image.tag(custom_registry_retagged_image)

    # Push the retagged image to the custom registry
    client.images.push(custom_registry_retagged_image)

    yield custom_registry_retagged_image

    # Delete the image from the custom registry
    client.images.remove(custom_registry_retagged_image)


@pytest.fixture
def credentials(config):
    """Reads and returns the username and password from the configuration."""
    username = config['auth']['username']
    password = config['auth']['password']
    return username, password


@pytest.fixture
def cleanup_function(domain_name, credentials, cleanup):
    """Returns a function that cleans up a deployed application.
    The function sends a DELETE request to remove the application from the deployment environment.
    """
    def _cleanup(url, team_id):
        def __cleanup():
            if not cleanup:
                print('Skipping cleanup')
                return

            headers = {'Content-Type': 'application/json'}
            auth = HTTPBasicAuth(credentials[0], credentials[1])
            delete_response = requests.delete(url, headers=headers, auth=auth)

            if delete_response.status_code == 200 or delete_response.status_code == 202:
                print('Successfully deleted the application')
            elif delete_response.status_code == 404:
                response_data = delete_response.json()
                if response_data.get('message') == f"No application found for team {team_id}\n":
                    print(f'Application with team_id {team_id} has already been deleted.')
                else:
                    print(f'Unexpected 404 error: {delete_response.text}')
            else:
                print(f'Failed to delete the application, status code: {delete_response.status_code}')
                print('Response:', delete_response.text)
        return __cleanup
    return _cleanup


@pytest.fixture
def backoff_function(domain_name, credentials):
    """Returns a function that waits for an application to initialize.
    The function uses exponential backoff to periodically check if the application is running.
    """
    def _wait_for_application_to_initialize(subdomain, team_id, max_tries, interval):
        @backoff.on_predicate(
            backoff.constant,
            lambda x: x is False,
            interval=interval,
            max_tries=max_tries,
            on_backoff=lambda details: print(f"Backing off {details['wait']} seconds..."),
        )
        def wait():
            app_url = f'http://{subdomain}.app.{domain_name}/'
            response = requests.get(app_url)

            url = f'https://deploy.{domain_name}/application/{team_id}'
            auth = HTTPBasicAuth(credentials[0], credentials[1])
            response_api = requests.get(url, auth=auth)

            if response.status_code != 200:
                print(f'Application is not running.\n Response: {response.text}')
                return False
            if response_api.status_code != 200:
                print(f'Response API: {response_api.text}\n')
                return False

            status = response_api.json()['status']
            if status != 'running':
                print(f'Application is not running.\n Response: {response_api.text}')
                return False

        wait()
    return _wait_for_application_to_initialize


# Your existing deploy_application fixture
@pytest.fixture
def deploy_application_function(domain_name, image_name, credentials, cleanup_function,
                                backoff_function, request):
    """
    Returns a function that deploys an application.
    The function sends a POST request to deploy an application and waits for it to initialize.
    It also registers a cleanup function to remove the application after the test.
    """
    def _deploy_application(team_id, custom_image_name=image_name, cleanup=True, backoff_max_tries=10, backoff_interval=10,
                            registry_credentials=None):
        url = f'https://deploy.{domain_name}/application/{team_id}'
        headers = {'Content-Type': 'application/json'}
        auth = HTTPBasicAuth(credentials[0], credentials[1])
        subdomain = f'public-hash-{team_id}'
        params = {
            'subdomain': subdomain,
            'image-name': custom_image_name,
        }
        if registry_credentials:
            params['registry-credentials'] = registry_credentials

        response = requests.post(url, headers=headers, auth=auth, params=params)

        if response.status_code == 200 or response.status_code == 202:
            print('Successfully made the POST request')
            print('Response:', response.json())
        else:
            print(f'Failed to make the POST request, status code: {response.status_code}')
            print('Response:', response.text)

        # Register the cleanup function to be called when the fixture goes out of scope
        if cleanup:
            request.addfinalizer(cleanup_function(url, team_id))

        # Wait for the application to initialize
        backoff_function(subdomain, team_id, backoff_max_tries, backoff_interval)

        return response, subdomain, team_id

    return _deploy_application


@pytest.fixture
def reset_redis(domain_name, credentials):
    """
    Returns a function that resets the Redis database.
    The function sends a GET request to reset the Redis database.
    """
    def _reset_redis():
        url = f'https://deploy.{domain_name}/reset-redis'
        auth = HTTPBasicAuth(credentials[0], credentials[1])

        response = requests.get(url, auth=auth)

        if response.status_code == 200:
            print('Successfully reset the Redis database')
        else:
            print(f'Failed to reset the Redis database, status code: {response.status_code}')
            print('Response:', response.text)

    return _reset_redis




@pytest.fixture
def blame():
    """
    Returns a string containing information about the entity running the test.
    The string is a combination of the username and hostname, intended to 'blame' or identify who initiated the test.
    """
    def _get_blame_info():
        # Get the username of the person running the test
        username = getpass.getuser()

        # Get the hostname of the machine where the test is being run
        hostname = socket.gethostname()

        # Create a "blame" string that includes the username and hostname
        blame_string = f"{username[:2]}{hostname[:2]}{random.randint(100, 999)}"

        return blame_string
    return _get_blame_info


@pytest.fixture
def deploy_random_application(blame, deploy_application_function):
    """
    Deploys an application with a random team ID and returns its details.
    The team ID is generated randomly and includes a 'blame' string to identify the test initiator.
    """
    # Get the "blame" string
    blame_string = blame()

    # Generate a random team_id and incorporate the "blame" string
    team_id = f"{random.randint(100, 200)}-{blame_string}"

    return deploy_application_function(team_id)


@pytest.fixture
def deploy_custom_image(blame, deploy_application_function, registry_credentials):
    def _deploy_custom_image(image_name, custom_registry_credentials=None, fixed_id=None):
        if custom_registry_credentials is None:
            custom_registry_credentials = registry_credentials

        blame_string = blame()

        # Generate a random team_id and incorporate the "blame" string
        team_id = fixed_id or f"{random.randint(100, 200)}-{blame_string}"

        return deploy_application_function(team_id, custom_image_name=image_name,
                                           registry_credentials=custom_registry_credentials)
    return _deploy_custom_image


@pytest.fixture
def deploy_multiple_applications(deploy_application_function, blame):
    """
    Returns a function that deploys multiple applications asynchronously.
    The function uses ThreadPoolExecutor to deploy multiple instances of the application in parallel.
    """
    def _deploy_apps(num_apps):
        deployed_apps = []

        backoff_max_tries = 5 * num_apps
        backoff_interval = 30

        def deploy_app(i):
            team_id = blame() + str(i)
            response, subdomain, team_id = deploy_application_function(team_id, backoff_max_tries=backoff_max_tries,
                                                                         backoff_interval=backoff_interval)
            return {'response': response, 'subdomain': subdomain, 'team_id': team_id}

        # Use ThreadPoolExecutor to run deploy_app function asynchronously
        with ThreadPoolExecutor() as executor:
            future_to_app = {executor.submit(deploy_app, i): i for i in range(num_apps)}
            for future in concurrent.futures.as_completed(future_to_app):
                i = future_to_app[future]
                try:
                    deployed_apps.append(future.result())
                except Exception as exc:
                    print(f"App {i} generated an exception: {exc}")

        return deployed_apps

    return _deploy_apps


@pytest.fixture
def deploy_four_applications(deploy_multiple_applications):
    """
    Deploys four applications and returns their details.
    """
    return deploy_multiple_applications(4)


@pytest.fixture(scope="function")
def initial_cleanup(domain_name, credentials):
    """
    Performs an initial cleanup by deleting all existing applications.
    This fixture is intended to run before any tests to ensure a clean state.
    """
    url = f'https://deploy.{domain_name}/application'
    auth = HTTPBasicAuth(credentials[0], credentials[1])
    params = {'delete-all-applications': True}

    response = requests.delete(url, auth=auth, params=params)

    if response.status_code not in [200]:  # 200 OK
        pytest.fail(f"Initial cleanup failed with status code {response.status_code}")

    yield

