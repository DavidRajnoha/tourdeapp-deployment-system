import pytest
import requests
from requests.auth import HTTPBasicAuth


@pytest.fixture
def failing_application(deploy_custom_image, always_fail_image_name):
    return deploy_custom_image(always_fail_image_name)


def test_get_failing_application_data(domain_name, credentials, failing_application):
    """
    Tests the successful retrieval of a deployed application's details.
    The test deploys an application, then sends a GET request to verify the application's details.
    """
    _, _, team_id = failing_application
    url = f'https://deploy.{domain_name}/application/{team_id}'
    auth = HTTPBasicAuth(credentials[0], credentials[1])

    response = requests.get(url, auth=auth)

    assert response.status_code == 200

    data = response.json()

    assert 'team_id' in data
    assert 'status' in data
    assert 'subdomain' in data
    assert 'image_name' in data
    assert 'logs' in data


def test_delete_failing_application_success(domain_name, credentials, failing_application):
    """
    Tests the successful deletion of a deployed application.
    The test deploys an application, deletes it, and then verifies it no longer exists.
    """
    _, subdomain, team_id = failing_application
    url = f'https://deploy.{domain_name}/application/{team_id}'
    auth = HTTPBasicAuth(credentials[0], credentials[1])

    # Delete the application
    delete_response = requests.delete(url, auth=auth)
    assert delete_response.status_code == 200 or delete_response.status_code == 202

    # Verify the application no longer exists by calling the /application endpoint
    get_response = requests.get(url, auth=auth)
    assert get_response.status_code == 404
