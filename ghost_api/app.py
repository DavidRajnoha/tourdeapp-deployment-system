from flask import Flask, jsonify, request, make_response, Response
import logging
import os
import json
from typing import List, Tuple

from persistance import get_team_data_from_db, persist_team_data, delete_all_data_from_db

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)


@app.route('/', methods=['GET'])
def home():
    return "The service is running!\n", 200

# @app.route('/update-data', methods=['POST'])
# def update_data():
#     payload = request.json
#
#     email = payload.get('email', None)
#     password = payload.get('password', None)
#     if not email or not password:
#         return jsonify({"message": "Missing email or password"}), 400
#
#     updated = len(scrape_new_teams_data(email, password))
#     return jsonify({"message": f"Updated {updated} new teams"}), 200


@app.route('/teams', methods=['GET'])
def get_teams():
    team_data: List[Tuple[str, str, str, str]] = get_team_data_from_db()
    team_data_json = json.dumps(team_data, ensure_ascii=False),
    response = Response(
        response=team_data_json,
        status=200,
        mimetype='application/json; charset=utf-8'
    )
    return response


@app.route('/teams', methods=['POST'])
def upload_teams():
    payload = request.json
    if not payload:
        return jsonify({"message": "Missing payload"}), 400
    if not isinstance(payload, list):
        return jsonify({"message": "Invalid format"}), 400

    team_data = payload

    # Validate the team_data
    if not all(isinstance(item, list) and len(item) == 4 and
               all(isinstance(sub_item, str) for sub_item in item)
               for item in team_data):
        return jsonify({"message": "Invalid format"}), 400

    persist_team_data(team_data)

    return jsonify({"message": "Teams uploaded"}), 200


@app.route('/teams', methods=['DELETE'])
def delete_teams():
    try:
        delete_all_data_from_db()
        return jsonify({"message": "All team data deleted"}), 200
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "Failed to delete data"}), 500


if __name__ == '__main__':
    debug_mode = os.environ.get('DEBUG_MODE', 'False').lower() == 'true'
    if debug_mode:
        logging.warning("Application is running in debug mode")
        app.run(debug=debug_mode, host='0.0.0.0')
