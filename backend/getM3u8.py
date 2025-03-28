#!/usr/bin/env python3
"""
chaturbate_scraper.py

Usage:
    python chaturbate_scraper.py https://chaturbate.com/roomslug/

This script retrieves the HLS URL for a given Chaturbate room.
It first fetches the room page to establish a session, obtain a dynamic CSRF token,
and then uses that token in a POST request to the endpoint.

Note: If running on environments with known IP restrictions (e.g., AWS EC2),
you may need to use a proxy or adjust headers to mimic a real browser.
"""

import sys
import logging
import requests
from requests.exceptions import RequestException
from urllib.parse import urlparse
from bs4 import BeautifulSoup  # Requires: pip install beautifulsoup4

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def extract_room_slug(url: str) -> str:
    """
    Extract the room slug from the provided Chaturbate URL.
    
    Args:
        url (str): URL of the room.
    
    Returns:
        str: The extracted room slug.
    
    Raises:
        ValueError: If the room slug could not be extracted.
    """
    parsed_url = urlparse(url)
    path_parts = [part for part in parsed_url.path.split('/') if part]
    if not path_parts:
        raise ValueError("No room slug found in the URL.")
    return path_parts[0]


def fetch_room_page(session: requests.Session, room_url: str) -> requests.Response:
    """
    Attempts to GET the room page using primary headers. If it fails with 403,
    it retries using a fallback header set to mimic a different browser.
    
    Args:
        session (requests.Session): The session object.
        room_url (str): The URL of the room.
        
    Returns:
        requests.Response: The response object.
    
    Raises:
        Exception: If both attempts fail.
    """
    try:
        logging.info(f"Fetching room page with primary headers: {room_url}")
        response = session.get(room_url)
        response.raise_for_status()
        return response
    except RequestException as e:
        logging.warning(f"Primary GET failed: {e}. Trying fallback headers.")
        # Fallback headers to mimic a different browser environment
        fallback_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/112.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        try:
            response = session.get(room_url, headers=fallback_headers)
            response.raise_for_status()
            return response
        except RequestException as e2:
            logging.error(f"Fallback GET request failed: {e2}")
            raise Exception("Failed to fetch room page with both primary and fallback headers.")


def get_csrf_token(session: requests.Session, room_url: str) -> str:
    """
    Fetches the room page to allow the session to capture cookies and extract the CSRF token.
    
    Args:
        session (requests.Session): The session object.
        room_url (str): The URL of the room.
    
    Returns:
        str: The CSRF token.
    
    Raises:
        Exception: If the token cannot be found.
    """
    response = fetch_room_page(session, room_url)
    
    # Try to obtain CSRF token from cookies first
    csrf_token = session.cookies.get('csrftoken')
    if csrf_token:
        logging.info("CSRF token found in cookies.")
        return csrf_token

    # Parse HTML for CSRF token (commonly in a hidden input field)
    soup = BeautifulSoup(response.text, 'html.parser')
    token_input = soup.find('input', attrs={'name': 'csrfmiddlewaretoken'})
    if token_input and token_input.has_attr('value'):
        csrf_token = token_input['value']
        logging.info("CSRF token extracted from HTML input.")
        return csrf_token

    # Fallback: search for a meta tag
    meta_token = soup.find('meta', attrs={'name': 'csrf-token'})
    if meta_token and meta_token.has_attr('content'):
        csrf_token = meta_token['content']
        logging.info("CSRF token extracted from meta tag.")
        return csrf_token

    logging.error("CSRF token not found in cookies or HTML.")
    raise Exception("CSRF token not found.")


def get_hls_url(session: requests.Session, room_slug: str, csrf_token: str) -> dict:
    """
    Sends a POST request to Chaturbate's endpoint to fetch the HLS URL for the given room.
    
    Args:
        session (requests.Session): The session with proper cookies.
        room_slug (str): The room slug.
        csrf_token (str): The dynamic CSRF token obtained from the room page.
    
    Returns:
        dict: JSON response from the endpoint if successful.
        None: If an error occurs.
    """
    post_url = 'https://chaturbate.com/get_edge_hls_url_ajax/'

    # Dynamic headers; cookies are managed by the session.
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Referer': f'https://chaturbate.com/{room_slug}/',
        'X-NewRelic-ID': 'VQIGWV9aDxACUFNVDgMEUw==',
        'newrelic': 'eyJ2IjpbMCwxXSwiZCI6eyJ0eSI6IkJyb3dzZXIiLCJhYyI6IjE0MTg5OTciLCJhcCI6IjI0NTA2NzUwIiwiaWQiOiI3ZWJkMTk3MDQxMTUwOGY5IiwidHIiOiJiYzU3ZDE4Y2RiN2U0ZjVjMjgzMmUxYTdmZTA1ODcyYSJ9fQ==',
        'traceparent': '00-bc57d18cdb7e4f5c2832e1a7fe05872a-7ebd1970411508f9-01',
        'tracestate': '1418997@nr=0-1-1418997-24506750-7ebd1970411508f9----1743187465002',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'multipart/form-data; boundary=----geckoformboundary6a610b256c356f4fb7599aaf07b1de15',
        'Origin': 'https://chaturbate.com',
        'Connection': 'keep-alive'
    }

    boundary = "----geckoformboundary6a610b256c356f4fb7599aaf07b1de15"
    
    payload = (
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="room_slug"\r\n\r\n'
        f'{room_slug}\r\n'
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="bandwidth"\r\n\r\n'
        'high\r\n'
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="current_edge"\r\n\r\n'
        'edge10-mad.live.mmcdn.com\r\n'
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="exclude_edge"\r\n\r\n'
        '\r\n'
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="csrfmiddlewaretoken"\r\n\r\n'
        f'{csrf_token}\r\n'
        f'--{boundary}--\r\n'
    )

    try:
        logging.info("Sending POST request to fetch HLS URL.")
        response = session.post(post_url, headers=headers, data=payload.encode('utf-8'))
        response.raise_for_status()
        logging.info("POST request successful.")
        return response.json()
    except RequestException as e:
        logging.error(f"POST request failed: {e}")
        return None
    except ValueError as e:
        logging.error(f"Failed to decode JSON response: {e}")
        return None


def main():
    """
    Main entry point for the script. Expects a URL as a command-line argument.
    """
    if len(sys.argv) != 2:
        print("Usage: python chaturbate_scraper.py https://chaturbate.com/roomslug/")
        sys.exit(1)

    input_url = sys.argv[1]

    try:
        room_slug = extract_room_slug(input_url)
        room_url = f"https://chaturbate.com/{room_slug}/"
        logging.info(f"Extracted room slug: {room_slug}")
    except ValueError as e:
        logging.error(f"Error extracting room slug: {e}")
        sys.exit(1)

    # Use a session to maintain cookies and headers.
    session = requests.Session()

    try:
        csrf_token = get_csrf_token(session, room_url)
        logging.info(f"Obtained CSRF token: {csrf_token}")
    except Exception as e:
        logging.error(f"Could not obtain CSRF token: {e}")
        sys.exit(1)

    result = get_hls_url(session, room_slug, csrf_token)
    if result:
        print("HLS URL Response:")
        print(result)
    else:
        print("Failed to fetch HLS URL.")


if __name__ == '__main__':
    main()
