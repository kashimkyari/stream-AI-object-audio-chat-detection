#!/usr/bin/env python3
"""
This script uses Seleniumwire to load a given URL in a headless Chrome browser,
capture network traffic, and extract any URLs that contain ".m3u8".
It prints the first found m3u8 URL (if any) from the intercepted network requests.
"""

import sys
import types
import tempfile  # For generating unique user-data directories
import os
import re
import logging
import uuid
import time
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
import re
import tempfile
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def fetch_page_content_with_network(url, wait_time=10):
    """
    Fetch the HTML content of the provided URL using Seleniumwire to capture network requests.
    
    Args:
        url (str): The URL of the webpage to load.
        wait_time (int): Time in seconds to wait for dynamic content to load.
        
    Returns:
        tuple: (page_source, network_requests)
            page_source (str): The HTML source of the loaded page.
            network_requests (list): List of intercepted request objects.
    """
    # Set up Chrome options for headless browsing
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--ignore-certificate-errors")
    
    # Create a temporary user data directory to avoid profile conflicts
    unique_user_data_dir = tempfile.mkdtemp()
    chrome_options.add_argument(f"--user-data-dir={unique_user_data_dir}")
    
    # Initialize the Seleniumwire Chrome driver
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        logging.info("Opening URL: %s", url)
        driver.get(url)
        # Wait for dynamic content to load (adjust wait_time if needed)
        time.sleep(wait_time)
        page_source = driver.page_source
        network_requests = driver.requests
        return page_source, network_requests
    finally:
        driver.quit()

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
        # Check if a response exists and the URL contains ".m3u8"
        if req.response and ".m3u8" in req.url:
            m3u8_urls.append(req.url)
    return m3u8_urls

def scrape_chaturbate_m3u8(url):
    """
    Scrape a Chaturbate room page and extract the m3u8 URL from network requests.
    
    Args:
        url (str): The full URL of the Chaturbate room.
        
    Returns:
        str or None: The first m3u8 URL found, or None if no URL was found.
    """
    logging.info("Scraping m3u8 URL from: %s", url)
    # Load the page and capture network requests
    page_source, network_requests = fetch_page_content_with_network(url, wait_time=10)
    
    # Try extracting m3u8 URLs from the intercepted network requests
    m3u8_urls = extract_m3u8_urls_from_network(network_requests)
    
    if m3u8_urls:
        logging.info("Found m3u8 URLs: %s", m3u8_urls)
        return m3u8_urls[0]  # Return the first found m3u8 URL
    else:
        logging.error("No m3u8 URL found in network requests.")
        return None

if __name__ == "__main__":
    # Example usage: update this URL as needed
    test_url = "https://chaturbate.com/cassies1/"
    m3u8_url = scrape_chaturbate_m3u8(test_url)
    if m3u8_url:
        print("Found m3u8 URL:", m3u8_url)
    else:
        print("No m3u8 URL found.")
