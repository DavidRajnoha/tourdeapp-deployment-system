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


@pytest.fixture
def domain_name():
    """Returns the domain name for the application deployment."""
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config['url']['base_domain']


@pytest.fixture
def image_name():
    """Returns the image name to be used for the application deployment."""
    return "traefik/whoami"


@pytest.fixture
def credentials():
    """Reads and returns the username and password from a configuration file."""
    config = configparser.ConfigParser()
    config.read('config.ini')

    username = config['auth']['username']
    password = config['auth']['password']
    return username, password


@pytest.fixture
def cleanup_function(domain_name, credentials):
    """Returns a function that cleans up a deployed application.
    The function sends a DELETE request to remove the application from the deployment environment.
    """
    def _cleanup(url, team_id):
        def __cleanup():
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
    def _wait_for_application_to_initialize(public_hash, team_id, max_tries, interval):
        @backoff.on_predicate(
            backoff.constant,
            lambda x: x is False,
            interval=interval,
            max_tries=max_tries,
            on_backoff=lambda details: print(f"Backing off {details['wait']} seconds..."),
        )
        def wait():
            app_url = f'http://{public_hash}.{domain_name}/'
            response = requests.get(app_url)

            url = f'http://deploy.{domain_name}/application/{team_id}'
            auth = HTTPBasicAuth(credentials[0], credentials[1])
            response_api = requests.get(url, auth=auth)

            if response.status_code == 200 and response_api.status_code == 200:
                return True
            else:
                print(f'Application is not running. Response: {response.text}')
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
    def _deploy_application(team_id, cleanup=True, backoff_max_tries=5, backoff_interval=10):
        url = f'http://deploy.{domain_name}/application/{team_id}'
        headers = {'Content-Type': 'application/json'}
        auth = HTTPBasicAuth(credentials[0], credentials[1])
        public_hash = f'public-hash-{team_id}'
        params = {
            'public-hash': public_hash,
            'image-name': image_name,
        }
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
        backoff_function(public_hash, team_id, backoff_max_tries, backoff_interval)

        return response, public_hash, team_id

    return _deploy_application


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
            response, public_hash, team_id = deploy_application_function(team_id, backoff_max_tries=backoff_max_tries,
                                                                         backoff_interval=backoff_interval)
            return {'response': response, 'public_hash': public_hash, 'team_id': team_id}

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
    url = f'http://deploy.{domain_name}/application'
    auth = HTTPBasicAuth(credentials[0], credentials[1])
    params = {'delete-all-applications': True}

    response = requests.delete(url, auth=auth, params=params)

    if response.status_code not in [200]:  # 200 OK
        pytest.fail(f"Initial cleanup failed with status code {response.status_code}")

    yield

