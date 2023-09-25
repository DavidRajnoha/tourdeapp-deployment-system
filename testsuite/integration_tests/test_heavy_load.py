import pytest
from requests.auth import HTTPBasicAuth
import requests


@pytest.mark.parametrize("num_apps", [
    1
    # 10,
    # 20,
    # 30,
    # 50,
    # 300
])
def test_get_all_applications(initial_cleanup, domain_name, credentials, deploy_multiple_applications, num_apps):
    # Deploy the specified number of apps
    deployed_apps = deploy_multiple_applications(num_apps)

    url = f'https://deploy.{domain_name}/application'
    auth = HTTPBasicAuth(credentials[0], credentials[1])

    response = requests.get(url, auth=auth)

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) == num_apps  # Verify that the correct number of applications are deployed

    for app in data:
        assert 'team_id' in app
        assert 'container_id' in app
        assert 'container_name' in app
        assert 'route' in app
        assert 'subdomain' in app
        assert 'image_name' in app

        # Verify that the application is running
        app_url = f'http://{app["subdomain"]}.{domain_name}/'
        app_response = requests.get(app_url)
        assert 'Hostname' in app_response.text and 'IP' in app_response.text