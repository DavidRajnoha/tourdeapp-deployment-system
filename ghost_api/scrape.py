import argparse
import logging
import os
import time
import requests

from typing import Tuple, List, Set

from requests.auth import HTTPBasicAuth
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from getpass import getpass


container_driver = os.environ.get('SELENIUM_CONTAINER_NAME', None)
project_id = os.environ.get('PROJECT_ID', None)
credentials_from_env = (os.environ.get('GHOST_API_USER', None), os.environ.get('GHOST_API_PASSWORD', None))

if container_driver is not None:
    options = Options()
    print(options)
    driver = webdriver.Remote(f'http://{container_driver}:4444/wd/hub',
                              options=options)
else:
    driver = webdriver.Chrome()


def scrape_new_teams_data(email, password, base_url, credentials=credentials_from_env):
    login(email, password)

    existing_team_data: List[Tuple[str, str, str]] = get_teams_from_server(base_url)

    saved_links = links_from_team_data(existing_team_data)
    links = set(team_ids())

    # make set difference between all_ids and saved_ids
    new_links = links - saved_links
    new_team_data = get_team_data(new_links)

    upload_teams_to_server(base_url, new_team_data, credentials)

    return new_team_data


def login(email, password):
    driver.get("https://ghost.scg.cz/login")

    # if is_logged_in():
    #     return

    # From ghost login to google
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "google-login-button")))
    driver.find_element(By.CLASS_NAME, "google-login-button").click()
    logging.info("Clicked on google login button")

    # Insert email
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "identifier")))
    driver.find_element(By.NAME, "identifier").send_keys(email)
    driver.find_element(By.ID, 'identifierNext').click()
    logging.info("Inserted email")

    # Insert password
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "Passwd")))
    time.sleep(1)
    driver.find_element(By.NAME, "Passwd").send_keys(password)
    driver.find_element(By.XPATH, "//button[contains(., 'Next')]").click()
    logging.info("Inserted password, waiting for 2FA")

    # Wait for 2FA
    time.sleep(30)
    logging.info("2FA done")


def is_logged_in():
    # Check if the user is logged in
    return driver.get_cookie('scg_session') is not None


def team_ids():
    id_links = []
    page = 1

    while True:
        url = (f"https://ghost.scg.cz/tournaments/teams?filterData[project_id][0]=project-{project_id}&"
               f"page={page}&sortingBy=id&sortingDirection=desc")
        driver.get(url)

        # Wait for the table to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//table[@class='table']")))
        # Find all rows in the table, skipping the header row
        rows = driver.find_elements(By.XPATH, ".//table[@class='table']//tr")[1:]
        logging.info(f"Found {len(rows)} rows on page {page}")

        if not rows:
            print("No more rows found. Exiting.")
            break

        # Loop through each row to get the link in the "ID" column
        for row in rows:
            try:
                # Find the link in the first cell of the row
                link_element = row.find_element(By.XPATH, ".//td[1]//a")

                # Get the href attribute of the link
                link = link_element.get_attribute("href")

                # Append the link to the list
                id_links.append(link)

            except Exception as e:
                print(f"An exception occurred: {e}")

        # Check if the "Next" button is disabled
        next_button_disabled = driver.find_elements(By.XPATH, "//li[@aria-label='další »'][@aria-disabled='true']")

        if next_button_disabled:
            print("Reached the last page. Exiting.")
            break

        page += 1

    logging.info(f"Found {len(id_links)} teams")
    return id_links


def get_team_data(id_links):
    team_data = []
    for link in id_links:
        driver.get(link)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//table[@class='table']")))

        table = driver.find_elements(By.XPATH, "//table[@class='table']")[0]
        table_text = table.text

        # Extract the ID and Hash from the text
        team_id, team_hash = extract_id_and_hash(table_text)
        team_data.append((link, team_id, team_hash))

    return team_data


def extract_id_and_hash(text):
    lines = text.split('\n')
    id_value = None
    hash_value = None

    for line in lines:
        if line.startswith('ID:'):
            id_value = line.split('ID:')[1].strip()
        elif line.startswith('Hash:'):
            hash_value = line.split('Hash:')[1].strip()

    return id_value, hash_value


def links_from_team_data(team_data) -> Set[str]:
    # get ids from a list of team data
    return {link for link, _, _ in team_data}


def get_teams_from_server(base_url: str) -> List[Tuple[str, str, str]]:
    response = requests.get(f"{base_url}/teams")
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get teams. Status code: {response.status_code}")
        return []


def upload_teams_to_server(base_url: str, team_data: List[Tuple[str, str, str]], credentials) -> bool:
    auth = HTTPBasicAuth(credentials[0], credentials[1])
    print(f"logging in with {credentials[0]} and {credentials[1]} as {auth}")
    response = requests.post(f"{base_url}/teams", json=team_data, auth=auth)
    if response.status_code == 200:
        print("Successfully uploaded teams.")
        return True
    else:
        print(f"Failed to upload teams. Status code: {response.status_code}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape new team data.")
    parser.add_argument("--email", required=True, help="Email for login.")
    parser.add_argument("--base_url", required=True, help="Base URL of the server.")
    parser.add_argument("--project", required=True, help="ID of the project.")
    parser.add_argument("--ghost_user", required=True, help="Username for the ghost api service")
    parser.add_argument("--ghost_password", required=True, help="Password for the ghost api service")

    args = parser.parse_args()

    project_id = args.project
    password = getpass("Enter your password: ")

    new_team_data = scrape_new_teams_data(args.email, password, args.base_url,
                                          credentials=(args.ghost_user, args.ghost_password))
    print(f"Newly scraped team data: {new_team_data}")
