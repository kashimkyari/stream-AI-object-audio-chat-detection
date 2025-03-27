#!/usr/bin/env python3
import sys
import types
import tempfile
import os
import re
import logging
import uuid
import time
import random


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

# New imports for proxy and anti-detection
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from fake_useragent import UserAgent

# Proxy management class
class ProxyManager:
    def __init__(self, proxy_list_file='proxies.txt'):
        """
        Initialize ProxyManager with a list of proxies from a file.
        
        Proxy file format should be:
        protocol://ip:port
        http://123.45.67.89:8080
        https://98.76.54.32:3128
        """
        self.proxies = self.load_proxies(proxy_list_file)
        self.used_proxies = set()
        self.ua = UserAgent()
    
    def load_proxies(self, proxy_list_file):
        """
        Load proxies from a text file.
        
        Args:
            proxy_list_file (str): Path to the proxy list file
        
        Returns:
            list: List of proxy strings
        """
        try:
            with open(proxy_list_file, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            logging.warning(f"Proxy list file {proxy_list_file} not found. No proxies available.")
            return []
    
    def get_proxy(self):
        """
        Get a fresh proxy from the list, avoiding recently used proxies.
        
        Returns:
            str or None: A proxy URL or None if no proxies are available
        """
        available_proxies = list(set(self.proxies) - self.used_proxies)
        
        if not available_proxies:
            # Reset used proxies if all have been tried
            self.used_proxies.clear()
            available_proxies = self.proxies
        
        if available_proxies:
            proxy = random.choice(available_proxies)
            self.used_proxies.add(proxy)
            return proxy
        return None
    
    def get_headers(self):
        """
        Generate headers with a random user agent to avoid detection.
        
        Returns:
            dict: Headers with a random user agent
        """
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

# Modify existing functions to use proxy rotation

def fetch_page_content(url, proxy_manager=None, timeout=30):
    """
    Fetch the HTML content of the provided URL with proxy rotation and retry logic.
    
    Args:
        url (str): The URL of the webpage to scrape
        proxy_manager (ProxyManager, optional): Proxy manager instance
        timeout (int, optional): Request timeout in seconds
    
    Returns:
        str: The HTML content of the webpage
    
    Raises:
        requests.HTTPError: If the request to the webpage fails
    """
    if not proxy_manager:
        proxy_manager = ProxyManager()
    
    # Retry strategy
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    # Rotate proxies
    proxy = proxy_manager.get_proxy()
    proxies = {"http": proxy, "https": proxy} if proxy else None
    
    try:
        response = session.get(
            url, 
            headers=proxy_manager.get_headers(), 
            proxies=proxies, 
            timeout=timeout
        )
        response.raise_for_status()
        return response.text
    except Exception as e:
        logging.error(f"Error fetching {url} with proxy {proxy}: {e}")
        raise

# Modify Chaturbate and Stripchat scraping functions to use proxy rotation
def scrape_chaturbate_data(url, progress_callback=None, proxy_manager=None):
    """
    Updated Chaturbate scraping with proxy rotation and anti-detection.
    
    Args:
        url (str): The full Chaturbate room URL
        progress_callback (callable, optional): Progress update function
        proxy_manager (ProxyManager, optional): Proxy manager instance
    
    Returns:
        dict or None: Scraped stream data
    """
    if not proxy_manager:
        proxy_manager = ProxyManager()
    
    try:
        if progress_callback:
            progress_callback(10, "Extracting room slug")
        
        room_slug = url.rstrip("/").split("/")[-1]
        
        if progress_callback:
            progress_callback(20, "Fetching m3u8 URL via AJAX endpoint")
        
        ajax_url = "https://chaturbate.com/get_edge_hls_url_ajax/"
        
        # Use session with proxy and retry logic
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "POST", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        # Rotate proxies
        proxy = proxy_manager.get_proxy()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        
        headers = proxy_manager.get_headers()
        headers.update({
            "Referer": f"https://chaturbate.com/{room_slug}/",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://chaturbate.com",
        })
        
        data = {
            "room_slug": room_slug,
            "jpeg": "1",
            "csrfmiddlewaretoken": str(uuid.uuid4())  # Randomize token
        }
        
        try:
            response = session.post(
                ajax_url, 
                data=data, 
                headers=headers, 
                proxies=proxies, 
                timeout=30
            )
            
            if response.status_code != 200:
                logging.error(f"HTTP error: {response.status_code}")
                if progress_callback:
                    progress_callback(100, f"Error: HTTP {response.status_code}")
                return None
            
            result = response.json()
            
            if result.get("success"):
                m3u8_url = result.get("url")
                if not m3u8_url:
                    logging.error("m3u8 URL missing in response")
                    if progress_callback:
                        progress_callback(100, "Error: m3u8 URL missing")
                    return None
                
                if progress_callback:
                    progress_callback(100, "Scraping complete")
                
                return {
                    "streamer_username": room_slug,
                    "chaturbate_m3u8_url": m3u8_url,
                }
            else:
                logging.error(f"Request unsuccessful: {result}")
                if progress_callback:
                    progress_callback(100, "Error: Request unsuccessful")
                return None
        
        except Exception as e:
            logging.error(f"Error during Chaturbate scraping: {e}")
            if progress_callback:
                progress_callback(100, f"Error: {e}")
            return None
    
    except Exception as e:
        logging.error(f"Error scraping Chaturbate URL {url}: {e}")
        if progress_callback:
            progress_callback(100, f"Error: {e}")
        return None

# Update other scraping functions similarly with proxy rotation and anti-detection techniques

# Main scraping function
def run_scrape_job(job_id, url):
    """
    Run a scraping job with proxy rotation.
    
    Args:
        job_id (str): Unique job identifier
        url (str): URL to scrape
    """
    proxy_manager = ProxyManager()
    update_job_progress(job_id, 0, "Starting scrape job")
    
    if "chaturbate.com" in url:
        result = scrape_chaturbate_data(
            url, 
            progress_callback=lambda p, m: update_job_progress(job_id, p, m),
            proxy_manager=proxy_manager
        )
    elif "stripchat.com" in url:
        # Update Stripchat scraping function similarly
        result = scrape_stripchat_data(
            url, 
            progress_callback=lambda p, m: update_job_progress(job_id, p, m),
            proxy_manager=proxy_manager
        )
    else:
        logging.error("Unsupported platform for URL: %s", url)
        result = None
    
    if result:
        scrape_jobs[job_id]["result"] = result
    else:
        scrape_jobs[job_id]["error"] = "Scraping failed"
    
    update_job_progress(job_id, 100, scrape_jobs[job_id].get("error", "Scraping complete"))

# Add method to test and validate proxies
def validate_proxies(proxies, test_url='https://httpbin.org/ip'):
    """
    Validate a list of proxies by testing their connectivity.
    
    Args:
        proxies (list): List of proxy URLs
        test_url (str): URL to test proxy connectivity
    
    Returns:
        list: List of working proxies
    """
    working_proxies = []
    for proxy in proxies:
        try:
            response = requests.get(
                test_url, 
                proxies={'http': proxy, 'https': proxy}, 
                timeout=10
            )
            if response.status_code == 200:
                working_proxies.append(proxy)
        except Exception as e:
            logging.warning(f"Proxy {proxy} failed: {e}")
    
    return working_proxies

# When setting up, create a proxies.txt file with your list of proxies
# Example proxies.txt format:
# http://123.45.67.89:8080
# https://98.76.54.32:3128
# socks4://12.34.56.78:1080

