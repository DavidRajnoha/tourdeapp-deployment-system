import pytest
import requests


@pytest.fixture
def custom_application(deploy_custom_image, custom_registry_image):
    return deploy_custom_image(custom_registry_image)


def test_run_image_from_custom_registry(domain_name, custom_application):
    _, public_hash, _ = custom_application
    app_url = f'http://{public_hash}.{domain_name}/'

    # Make a GET request to the deployed application
    response = requests.get(app_url)

    # Check if the application is running by examining the response
    assert 'Hostname' in response.text and 'IP' in response.text
