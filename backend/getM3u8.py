#!/usr/bin/env python3
"""
chaturbate_scraper_selenium.py

Usage:
    python chaturbate_scraper_selenium.py https://chaturbate.com/roomslug/

This script uses undetected-chromedriver (Selenium) to bypass Cloudflare's JS challenge.
It loads the room page, waits until the challenge is solved, extracts necessary cookies and the CSRF token,
and then uses a requests session to send the POST request to obtain the HLS URL.
"""

import sys
import time
import logging
import requests
from requests.exceptions import RequestException
from urllib.parse import urlparse
from bs4 import BeautifulSoup  # pip install beautifulsoup4

# Import undetected_chromedriver (pip install undetected-chromedriver)
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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


def get_page_with_selenium(room_url: str) -> (str, dict):
    """
    Uses undetected-chromedriver to load the page and bypass Cloudflare's challenge.
    Waits until the page title no longer contains "Just a moment" and the document is fully loaded.
    
    Args:
        room_url (str): The URL of the room.
    
    Returns:
        tuple: (page HTML, cookies as a dict)
    
    Raises:
        Exception: If the page cannot be loaded.
    """
    logging.info(f"Launching headless browser for {room_url}")
    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = uc.Chrome(options=options)
    
    try:
        driver.get(room_url)
        # Wait up to 30 seconds for the challenge to be solved and the actual page to load.
        wait = WebDriverWait(driver, 30)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        wait.until(lambda d: "Just a moment" not in d.title)
        # Optionally, wait for a known element from the real room page.
        # For instance, if the room page always has a specific element:
        # wait.until(EC.presence_of_element_located((By.ID, "room_video_container")))
        
        # Extra wait to ensure all dynamic content loads.
        time.sleep(5)
        
        html = driver.page_source
        # Get cookies from Selenium and convert them into a dict for requests.
        selenium_cookies = driver.get_cookies()
        cookies = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
        logging.info("Page loaded and cookies obtained.")
        return html, cookies
    finally:
        driver.quit()


def get_csrf_token_from_html(html: str) -> str:
    """
    Extract CSRF token from the HTML content.
    
    Args:
        html (str): HTML content of the page.
    
    Returns:
        str: CSRF token.
    
    Raises:
        Exception: If token is not found.
    """
    soup = BeautifulSoup(html, 'html.parser')
    token_input = soup.find('input', attrs={'name': 'csrfmiddlewaretoken'})
    if token_input and token_input.has_attr('value'):
        csrf_token = token_input['value']
        logging.info("CSRF token extracted from HTML input.")
        return csrf_token

    # Fallback: check meta tag
    meta_token = soup.find('meta', attrs={'name': 'csrf-token'})
    if meta_token and meta_token.has_attr('content'):
        csrf_token = meta_token['content']
        logging.info("CSRF token extracted from meta tag.")
        return csrf_token

    logging.error("CSRF token not found in page HTML.")
    raise Exception("CSRF token not found in page HTML.")


def get_hls_url(session: requests.Session, room_slug: str, csrf_token: str) -> dict:
    """
    Sends a POST request to Chaturbate's endpoint to fetch the HLS URL for the given room.
    
    Args:
        session (requests.Session): Session with proper cookies.
        room_slug (str): The room slug.
        csrf_token (str): The dynamic CSRF token.
    
    Returns:
        dict: JSON response from the endpoint if successful.
        None: If an error occurs.
    """
    post_url = 'https://chaturbate.com/get_edge_hls_url_ajax/'

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
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
        response = session.post(post_url, headers=headers, data=payload.encode('utf-8'), timeout=10)
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
        print("Usage: python chaturbate_scraper_selenium.py https://chaturbate.com/roomslug/")
        sys.exit(1)

    input_url = sys.argv[1]

    try:
        room_slug = extract_room_slug(input_url)
        room_url = f"https://chaturbate.com/{room_slug}/"
        logging.info(f"Extracted room slug: {room_slug}")
    except ValueError as e:
        logging.error(f"Error extracting room slug: {e}")
        sys.exit(1)

    try:
        # Use Selenium to bypass Cloudflare challenge and get page HTML and cookies.
        html, selenium_cookies = get_page_with_selenium(room_url)
        csrf_token = get_csrf_token_from_html(html)
    except Exception as e:
        logging.error(f"Error obtaining CSRF token and page content: {e}")
        sys.exit(1)

    # Create a requests session and update its cookies from Selenium.
    session = requests.Session()
    session.cookies.update(selenium_cookies)

    result = get_hls_url(session, room_slug, csrf_token)
    if result:
        print("HLS URL Response:")
        print(result)
    else:
        print("Failed to fetch HLS URL.")


if __name__ == '__main__':
    main()
