import requests
from requests.auth import HTTPBasicAuth


def test_application_running(deploy_random_application, domain_name):
    """
    Verifies that a randomly deployed application is running.
    The test checks the response from the application's URL for specific text to confirm it's operational.
    """
    # Test to verify that the deployed application is running
    _, public_hash, _ = deploy_random_application

    # Construct the URL for the deployed application
    app_url = f'http://{public_hash}.{domain_name}/'

    # Make a GET request to the deployed application
    response = requests.get(app_url)

    # Check if the application is running by examining the response
    assert 'Hostname' in response.text and 'IP' in response.text


def test_get_application_success(domain_name, credentials, deploy_random_application):
    """
    Tests the successful retrieval of a deployed application's details.
    The test deploys an application, then sends a GET request to verify the application's details.
    """
    _, _, team_id = deploy_random_application
    url = f'https://deploy.{domain_name}/application/{team_id}'
    auth = HTTPBasicAuth(credentials[0], credentials[1])

    response = requests.get(url, auth=auth)

    assert response.status_code == 200

    data = response.json()

    assert 'team_id' in data
    assert 'container_id' in data
    assert 'container_name' in data
    assert 'route' in data
    assert 'subdomain' in data
    assert 'image_name' in data


def test_get_application_not_found(domain_name, credentials):
    """
    Tests the scenario where an application is not found.
    The test sends a GET request for a non-existent team_id and expects a 404 status code.
    """
    team_id = "nonexistent_team_id"
    url = f'https://deploy.{domain_name}/application/{team_id}'
    auth = HTTPBasicAuth(credentials[0], credentials[1])

    response = requests.get(url, auth=auth)

    assert response.status_code == 404


def test_delete_application_success(domain_name, credentials, deploy_random_application):
    """
    Tests the successful deletion of a deployed application.
    The test deploys an application, deletes it, and then verifies it no longer exists.
    """
    _, public_hash, team_id = deploy_random_application
    url = f'https://deploy.{domain_name}/application/{team_id}'
    auth = HTTPBasicAuth(credentials[0], credentials[1])

    # Delete the application
    delete_response = requests.delete(url, auth=auth)
    assert delete_response.status_code == 200 or delete_response.status_code == 202

    # Verify the application no longer exists by calling the /application endpoint
    get_response = requests.get(url, auth=auth)
    assert get_response.status_code == 404

    # Verify the application is not accessible from the public domain
    app_url = f'http://deploy.{public_hash}.{domain_name}/'
    get_app_response = requests.get(app_url)
    assert get_app_response.status_code == 404


def test_delete_application_not_found(domain_name, credentials):
    """
    Tests the scenario where an attempt is made to delete a non-existent application.
    The test sends a DELETE request for a non-existent team_id and expects a 404 status code.
    """
    team_id = "nonexistent_team_id"
    url = f'https://deploy.{domain_name}/application/{team_id}'
    auth = HTTPBasicAuth(credentials[0], credentials[1])

    # Attempt to delete a non-existent application
    delete_response = requests.delete(url, auth=auth)
    assert delete_response.status_code == 404


def test_get_all_applications(initial_cleanup, domain_name, credentials, deploy_four_applications):
    """
    Tests the retrieval of all deployed applications.
    The test deploys four applications and then sends a GET request to verify that all are listed.
    """
    url = f'https://deploy.{domain_name}/application'
    auth = HTTPBasicAuth(credentials[0], credentials[1])

    response = requests.get(url, auth=auth)

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 4  # Verify that 4 applications are deployed

    for app in data:
        assert 'team_id' in app
        assert 'container_id' in app
        assert 'container_name' in app
        assert 'route' in app
        assert 'subdomain' in app
        assert 'image_name' in app
