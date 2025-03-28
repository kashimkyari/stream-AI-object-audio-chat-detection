#!/usr/bin/env python3
"""
This script logs into the website using the provided credentials.
It sends a POST request with the necessary login data (including CSRF token, username, password, and rememberme)
and prints the response status and headers.
"""

import requests

def login():
    # Set the login URL.
    # Update this URL if the login endpoint differs.
    login_url = "https://chaturbate.com/auth/login/"  # Example endpoint

    # Initialize a session to maintain cookies across requests.
    session = requests.Session()

    # Define headers to mimic a real browser.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:112.0) "
            "Gecko/20100101 Firefox/112.0"
        ),
        "Referer": login_url,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive"
    }

    # Define the login payload with the provided credentials.
    login_data = {
        "csrfmiddlewaretoken": "zJbw6qtGyDznqoJtVKrQKBzrYUT2hnRKzeAeyzMz9KWGpco75zFlPflRw866H1sJ",
        "username": "journalistafraid",
        "password": '4adPwNBq,g\"}+x3',  # Note: the double quote is escaped
        "rememberme": "on"
    }

    # It's often necessary to perform an initial GET to retrieve cookies (e.g., for the CSRF token)
    initial_response = session.get(login_url, headers=headers)
    if initial_response.status_code != 200:
        print("Failed to load login page:", initial_response.status_code)
        return

    # Send the POST request to login.
    response = session.post(login_url, data=login_data, headers=headers)
    
    # Print the response details.
    print("Status Code:", response.status_code)
    print("Response Headers:")
    for key, value in response.headers.items():
        print(f"{key}: {value}")
    print("\nResponse Text:")
    print(response.text)

if __name__ == "__main__":
    login()
