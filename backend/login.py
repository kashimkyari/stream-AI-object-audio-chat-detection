#!/usr/bin/env python3
"""
This script logs in to Chaturbate using provided credentials,
navigates to a specified room page, and then uses Seleniumwire to capture
network traffic to extract any URLs containing ".m3u8".

Requirements:
- selenium
- selenium-wire
- a compatible version of ChromeDriver in your PATH
"""

import logging
import time
import re
import tempfile
import sys
import types
# --- Monkey Patch for blinker._saferef ---
if 'blinker._saferef' not in sys.modules:
    saferef = types.ModuleType('blinker._saferef')
    import weakref
    class SafeRef(weakref.ref):
        def __init__(self, ob, callback=None):
            super().__init__(ob, callback)
            self._hash = hash(ob)
        def __hash__(self):
            return self._hash
        def __eq__(self, other):
            try:
                return self() is other()
            except Exception:
                return False
    saferef.SafeRef = SafeRef
    sys.modules['blinker._saferef'] = saferef
# --- End of Monkey Patch ---

from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- Configuration ---
LOGIN_URL = "https://chaturbate.com/auth/login/"
ROOM_URL = "https://chaturbate.com/cassies1/"  # Update this to the desired room URL

# Provided login credentials (update if needed)
USERNAME = "journalistafraid"
PASSWORD = '4adPwNBq,g\"}+x3'  # note: ensure proper escaping if needed

def init_driver():
    """
    Initialize a headless Seleniumwire Chrome driver with a temporary user data directory.
    Returns:
        driver: Seleniumwire webdriver instance.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--ignore-certificate-errors")
    # Create a temporary directory for user data
    unique_user_data_dir = tempfile.mkdtemp()
    chrome_options.add_argument(f"--user-data-dir={unique_user_data_dir}")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def login_chaturbate(driver, username, password):
    """
    Log in to Chaturbate using Selenium.
    
    Args:
        driver: Selenium webdriver instance.
        username (str): Username for login.
        password (str): Password for login.
    """
    logging.info("Navigating to login page: %s", LOGIN_URL)
    driver.get(LOGIN_URL)
    
    try:
        # Wait until the login form is present
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
    except Exception as e:
        logging.error("Login page did not load properly: %s", e)
        return False

    # Fill in the username and password fields
    username_input = driver.find_element(By.NAME, "username")
    password_input = driver.find_element(By.NAME, "password")
    
    username_input.clear()
    username_input.send_keys(username)
    password_input.clear()
    password_input.send_keys(password)
    
    # Note: The CSRF token is usually automatically set in a hidden input.
    # Locate and click the submit button. Adjust the selector if needed.
    try:
        submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        submit_button.click()
    except Exception as e:
        logging.error("Failed to locate or click the login button: %s", e)
        return False

    # Wait for the login to process. One strategy is to wait for the URL to change.
    try:
        WebDriverWait(driver, 15).until(
            EC.url_changes(LOGIN_URL)
        )
        logging.info("Login successful. Current URL: %s", driver.current_url)
    except Exception as e:
        logging.error("Login may have failed or timed out: %s", e)
        return False

    return True

def fetch_page_content_with_network(driver, url, wait_time=10):
    """
    Navigate the driver to the provided URL, wait for dynamic content,
    and return the page source along with the captured network requests.
    
    Args:
        driver: Seleniumwire webdriver instance.
        url (str): The URL to load.
        wait_time (int): Time in seconds to wait for dynamic content.
        
    Returns:
        tuple: (page_source, network_requests)
    """
    logging.info("Navigating to room URL: %s", url)
    driver.get(url)
    time.sleep(wait_time)  # Wait for page to load dynamic content
    page_source = driver.page_source
    network_requests = driver.requests
    return page_source, network_requests

def extract_m3u8_urls_from_network(requests_list):
    """
    Extract m3u8 URLs from a list of Seleniumwire request objects.
    
    Args:
        requests_list (list): List of Seleniumwire request objects.
        
    Returns:
        list: A list of m3u8 URLs found in the network traffic.
    """
    m3u8_urls = []
    for req in requests_list:
        if req.response and ".m3u8" in req.url:
            m3u8_urls.append(req.url)
    return m3u8_urls

def scrape_chaturbate_m3u8_after_login(driver, room_url):
    """
    After logging in, navigate to a room URL and extract the m3u8 URL from network requests.
    
    Args:
        driver: Seleniumwire webdriver instance.
        room_url (str): The full URL of the Chaturbate room.
        
    Returns:
        str or None: The first m3u8 URL found, or None if not found.
    """
    page_source, network_requests = fetch_page_content_with_network(driver, room_url, wait_time=10)
    m3u8_urls = extract_m3u8_urls_from_network(network_requests)
    if m3u8_urls:
        logging.info("Found m3u8 URLs: %s", m3u8_urls)
        return m3u8_urls[0]
    else:
        logging.error("No m3u8 URL found in network requests.")
        return None

def main():
    driver = init_driver()
    try:
        if not login_chaturbate(driver, USERNAME, PASSWORD):
            logging.error("Login failed. Exiting.")
            return

        # After successful login, scrape the desired room page.
        m3u8_url = scrape_chaturbate_m3u8_after_login(driver, ROOM_URL)
        if m3u8_url:
            print("Found m3u8 URL:", m3u8_url)
        else:
            print("No m3u8 URL found.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
