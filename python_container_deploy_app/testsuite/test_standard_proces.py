import random
import time

import backoff
import requests
import pytest
import configparser
from requests.auth import HTTPBasicAuth


@pytest.fixture
def domain_name():
    return "tda.rajnoha.eu"


@pytest.fixture
def image_name():
    return "traefik/whoami"


@pytest.fixture
def credentials():
    config = configparser.ConfigParser()
    config.read('config.ini')

    username = config['auth']['username']
    password = config['auth']['password']
    return username, password


@pytest.fixture
def deploy_container(domain_name, image_name, credentials):
    i_value = random.randint(100, 200)

    url = f'http://deploy.{domain_name}/application/{i_value}'
    headers = {'Content-Type': 'application/json'}
    auth = HTTPBasicAuth(credentials[0], credentials[1])
    public_hash = f'public-hash-{i_value}'

    # Query parameters
    params = {
        'public-hash': public_hash,
        'image-name': image_name,
    }

    # Making the POST request
    response = requests.post(url, headers=headers, auth=auth, params=params)

    # Check the response
    if response.status_code == 200 or response.status_code == 202:
        print('Successfully made the POST request')
        print('Response:', response.json())
    else:
        print(f'Failed to make the POST request, status code: {response.status_code}')
        print('Response:', response.text)

    yield response, public_hash

    time.sleep(5)

    # Initialize backoff time
    backoff_time = 1

    while backoff_time < 32:
        # Making the DELETE request to remove the application
        delete_response = requests.delete(url, headers=headers, auth=auth)

        # Check the DELETE response
        if delete_response.status_code == 200 or delete_response.status_code == 202:
            print('Successfully deleted the application')
            break
        else:
            print(f'Failed to delete the application, status code: {delete_response.status_code}')
            print('Response:', delete_response.text)
            print(f'Retrying in {backoff_time} seconds...')

            # Wait for backoff time before retrying
            time.sleep(backoff_time)

            # Double the backoff time for the next iteration
            backoff_time *= 2


def test_deploy_container(deploy_container):
    response, _ = deploy_container
    assert response.status_code == 202


@backoff.on_predicate(
    backoff.constant,  # Constant backoff strategy
    lambda x: x is False,  # Predicate to continue
    interval=5,  # Constant backoff time in seconds
    max_tries=5,  # Maximum number of tries
    on_backoff=lambda details: print(f"Backing off {details['wait']} seconds..."),
    on_giveup=lambda _: pytest.fail('Failed to deploy the application correctly'),
)
def test_container_running(deploy_container):
    # Test to verify that the deployed application is running
    _, public_hash = deploy_container

    # Construct the URL for the deployed application
    app_url = f'http://{public_hash}.tda.rajnoha.eu/'

    # Make a GET request to the deployed application
    response = requests.get(app_url)

    # Check if the application is running by examining the response
    if 'Hostname' in response.text and 'IP' in response.text:
        return True  # Stop backoff
    else:
        print(f'Application is not running. Response: {response.text}')
        return False  # Continue backoff
