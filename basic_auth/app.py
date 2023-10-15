from flask import Flask, request, jsonify
import logging
import os

import requests

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

GHOST_API_URL = f'http://{os.environ.get("GHOST_CONTAINER", None)}:5000'
REGISTRY = os.environ.get('REGISTRY', None)
TDA_ROUND = os.environ.get('TDA_ROUND', None)


@app.route('/', methods=['GET'])
def home():
    return "The service is running!\n", 200


@app.route('/staging-auth', methods=['POST'])
def staging_auth():
    payload = request.json

    # Access the 'team_secret' field
    team_secret = payload.get('team_secret', None)

    if team_secret is None:
        return jsonify({"message": "team_secret is required"}), 400

    team_data_response = requests.get(f"{GHOST_API_URL}/teams")
    if team_data_response.status_code != 200:
        return jsonify({"message": "Failed to get team data"}), 500

    team_data = team_data_response.json()

    # This code was copied, consider merging the basic_auth and ghost api
    # but it is necessary to figure traefik middleware auth
    if not all(isinstance(item, list) and len(item) == 3 and
               all(isinstance(sub_item, str) for sub_item in item)
               for item in team_data):
        return jsonify({"message": "Received data in invalid format"}), 500

    team_secrets = [team[2] for team in team_data]

    if team_secret not in team_secrets:
        return jsonify({"message": "team_secret is invalid"}), 400

    registry_password = os.environ.get('REGISTRY_PASSWORD', None)

    if registry_password is None:
        logging.error("Registry password is not set")
        return jsonify({"message": "Registry password is not set"}), 500

    team_id = team_data[team_secrets.index(team_secret)][1]

    return jsonify({"key": registry_password,
                    "name": f'{REGISTRY}/{TDA_ROUND}-team-{team_id}'}), 200


if __name__ == '__main__':
    debug_mode = os.environ.get('DEBUG_MODE', 'False').lower() == 'true'
    if debug_mode:
        logging.warning("Application is running in debug mode")
        app.run(debug=debug_mode, host='0.0.0.0')
