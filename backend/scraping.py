#!/usr/bin/env python3
import sys
import types
import tempfile  # For generating unique user-data directories
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

from concurrent.futures import ThreadPoolExecutor
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from flask import jsonify

# Import models and database session for stream creation.
from models import ChaturbateStream, StripchatStream, Assignment, TelegramRecipient
from extensions import db
from config import app  # Use the Flask app for application context
from notifications import send_text_message

# New imports for proxy and anti-detection
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from fake_useragent import UserAgent

# Global dictionaries to hold job statuses.
scrape_jobs = {}
stream_creation_jobs = {}
executor = ThreadPoolExecutor(max_workers=5)  # Thread pool for parallel scraping

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraping.log'),
        logging.StreamHandler()
    ]
)

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

def update_job_progress(job_id, percent, message):
    """Update the progress of a scraping job with interactive data."""
    now = time.time()
    if job_id not in scrape_jobs or 'start_time' not in scrape_jobs[job_id]:
        scrape_jobs[job_id] = {'start_time': now}
    elapsed = now - scrape_jobs[job_id]['start_time']
    estimated = None
    if percent > 0:
        estimated = (100 - percent) / percent * elapsed
    scrape_jobs[job_id].update({
        "progress": percent,
        "message": message,
        "elapsed": round(elapsed, 1),
        "estimated_time": round(estimated, 1) if estimated is not None else None,
    })
    logging.info("Job %s progress: %s%% - %s (Elapsed: %ss, Est: %ss)",
                 job_id, percent, message,
                 scrape_jobs[job_id]['elapsed'],
                 scrape_jobs[job_id]['estimated_time'])

def update_stream_job_progress(job_id, percent, message):
    """Update the progress of a stream creation job with interactive data."""
    now = time.time()
    if job_id not in stream_creation_jobs or 'start_time' not in stream_creation_jobs[job_id]:
        stream_creation_jobs[job_id] = {'start_time': now}
    elapsed = now - stream_creation_jobs[job_id]['start_time']
    estimated = None
    if percent > 0:
        estimated = (100 - percent) / percent * elapsed
    stream_creation_jobs[job_id].update({
        "progress": percent,
        "message": message,
        "elapsed": round(elapsed, 1),
        "estimated_time": round(estimated, 1) if estimated is not None else None,
    })
    logging.info("Stream Job %s progress: %s%% - %s (Elapsed: %ss, Est: %ss)",
                 job_id, percent, message,
                 stream_creation_jobs[job_id]['elapsed'],
                 stream_creation_jobs[job_id]['estimated_time'])

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

def extract_m3u8_urls(html_content):
    """
    Extract m3u8 URLs from the given HTML content using a regular expression.
    
    Args:
        html_content (str): The HTML content to search within.
    
    Returns:
        list: A list of found m3u8 URLs.
    """
    pattern = r'https?://[^\s"\']+\.m3u8'
    urls = re.findall(pattern, html_content)
    return urls

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

def fetch_m3u8_from_page(url, timeout=90):
    """Fetch the M3U8 URL from the given page using Selenium."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--ignore-certificate-errors")
    unique_user_data_dir = tempfile.mkdtemp()
    chrome_options.add_argument(f"--user-data-dir={unique_user_data_dir}")

    driver = webdriver.Chrome(options=chrome_options)
    driver.scopes = ['.*\\.m3u8']

    try:
        logging.info(f"Opening URL: {url}")
        driver.get(url)
        time.sleep(5)
        found_url = None
        elapsed = 0
        while elapsed < timeout:
            for request in driver.requests:
                if request.response and ".m3u8" in request.url:
                    found_url = request.url
                    logging.info(f"Found M3U8 URL: {found_url}")
                    break
            if found_url:
                break
            time.sleep(1)
            elapsed += 1
        return found_url if found_url else None
    except Exception as e:
        logging.error(f"Error fetching M3U8 URL: {e}")
        return None
    finally:
        driver.quit()

def scrape_stripchat_data(url, progress_callback=None, proxy_manager=None):
    """Scrape Stripchat data and update progress."""
    try:
        if progress_callback:
            progress_callback(10, "Fetching Stripchat page")
        stripchat_m3u8_url = fetch_m3u8_from_page(url)
        if not stripchat_m3u8_url:
            logging.error("Failed to fetch m3u8 URL for Stripchat stream.")
            if progress_callback:
                progress_callback(100, "Error: Failed to fetch m3u8 URL")
            return None
        if "playlistType=lowLatency" in stripchat_m3u8_url:
            stripchat_m3u8_url = stripchat_m3u8_url.split('?')[0]
        streamer_username = url.rstrip("/").split("/")[-1]
        result = {
            "streamer_username": streamer_username,
            "stripchat_m3u8_url": stripchat_m3u8_url,
        }
        logging.info("Scraped details: %s", result)
        if progress_callback:
            progress_callback(100, "Scraping complete")
        return result
    except Exception as e:
        logging.error("Error scraping Stripchat URL %s: %s", url, e)
        if progress_callback:
            progress_callback(100, f"Error: {e}")
        return None

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

def run_stream_creation_job(job_id, room_url, platform, agent_id=None):
    with app.app_context():
        try:
            update_stream_job_progress(job_id, 5, "Initializing scraping...")
            proxy_manager = ProxyManager()
            
            if platform == "chaturbate":
                scraped_data = scrape_chaturbate_data(
                    room_url, 
                    progress_callback=lambda p, m: update_stream_job_progress(job_id, 5 + p * 0.45, m),
                    proxy_manager=proxy_manager
                )
            else:
                scraped_data = scrape_stripchat_data(
                    room_url, 
                    progress_callback=lambda p, m: update_stream_job_progress(job_id, 5 + p * 0.45, m),
                    proxy_manager=proxy_manager
                )
            
            if not scraped_data:
                update_stream_job_progress(job_id, 100, "Scraping failed")
                return
            
            update_stream_job_progress(job_id, 50, "Creating stream...")
            streamer_username = room_url.rstrip("/").split("/")[-1]
            
            if platform == "chaturbate":
                stream = ChaturbateStream(
                    room_url=room_url,
                    streamer_username=streamer_username,
                    chaturbate_m3u8_url=scraped_data["chaturbate_m3u8_url"]
                )
            else:
                stream = StripchatStream(
                    room_url=room_url,
                    streamer_username=streamer_username,
                    stripchat_m3u8_url=scraped_data["stripchat_m3u8_url"]
                )
            
            db.session.add(stream)
            db.session.commit()

            # Assign agent if agent_id is provided
            if agent_id:
                assignment = Assignment(agent_id=agent_id, stream_id=stream.id)
                db.session.add(assignment)
                db.session.commit()

            db.session.refresh(stream)

            for prog in range(51, 101, 10):
                time.sleep(0.5)
                update_stream_job_progress(job_id, prog, "Finalizing stream...")

            update_stream_job_progress(job_id, 100, "Stream created")

            # Notify Telegram users when the stream is successfully created
            recipients = TelegramRecipient.query.all()
            message = (
                f"🚀 **New Stream Created!**\n"
                f"🎥 **Platform:** {platform.capitalize()}\n"
                f"📡 **Streamer:** {streamer_username}\n"
                f"🔗 **Stream URL:** {room_url}"
            )
            for recipient in recipients:
                executor.submit(send_text_message, message, recipient.chat_id, None)

            stream_creation_jobs[job_id]["stream"] = stream.serialize()

        except Exception as e:
            update_stream_job_progress(job_id, 100, f"Error: {str(e)}")

def refresh_chaturbate_stream(room_slug):
    """
    Refresh the m3u8 URL for a Chaturbate stream based on the given room slug.
    This function sends a POST request to the Chaturbate AJAX endpoint to fetch the latest HLS m3u8 URL,
    and if a corresponding ChaturbateStream exists in the database, it updates its URL.
    
    Args:
        room_slug (str): The room slug (streamer username).
    
    Returns:
        str or None: The new m3u8 URL if successful, or None if an error occurred.
    """
    proxy_manager = ProxyManager()
    ajax_url = "https://chaturbate.com/get_edge_hls_url_ajax/"
    
    headers = proxy_manager.get_headers()
    headers.update({
        "Referer": f"https://chaturbate.com/{room_slug}/",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://chaturbate.com",
    })
    
    # Rotate proxies
    proxy = proxy_manager.get_proxy()
    proxies = {"http": proxy, "https": proxy} if proxy else None
    
    session_req = requests.Session()
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "POST", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session_req.mount("https://", adapter)
    session_req.mount("http://", adapter)
    
    data = {
        "room_slug": room_slug,
        "jpeg": "1",
        "csrfmiddlewaretoken": str(uuid.uuid4())  # Randomize token
    }
    
    try:
        response = session_req.post(
            ajax_url, 
            data=data, 
            headers=headers, 
            proxies=proxies, 
            timeout=10
        )
        logging.info("POST response status: %s", response.status_code)
    except Exception as e:
        logging.error("Error during the POST request: %s", e)
        return None
    
    if response.status_code != 200:
        logging.error("HTTP error: %s", response.status_code)
        logging.error("Response text: %s", response.text)
        return None
    
    try:
        result = response.json()
        logging.info("Response JSON: %s", result)
    except ValueError:
        logging.error("Failed to decode JSON response: %s", response.text)
        return None
    
    if result.get("success"):
        new_url = result.get("url")
        if not new_url:
            logging.error("m3u8 URL missing in response")
            return None
    else:
        logging.error("Request was not successful: %s", result)
        return None
    
    # Update the corresponding ChaturbateStream in the database.
    stream = ChaturbateStream.query.filter_by(streamer_username=room_slug).first()
    if stream:
        stream.chaturbate_m3u8_url = new_url  # Replace the old URL with the new one.
        try:
            db.session.commit()
            logging.info("Updated stream '%s' with new m3u8 URL: %s", room_slug, new_url)
        except Exception as db_e:
            db.session.rollback()
            logging.error("Database commit failed: %s", db_e)
            return None
        return new_url
    else:
        logging.error("No Chaturbate stream found for room slug: %s", room_slug)
        return None

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

if __name__ == '__main__':
    # You can add any initialization or testing code here
    logging.info("Scraping script initialized.")