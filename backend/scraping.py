#!/usr/bin/env python3
"""
chaturbate_scraper_updated.py

This module provides scraping functions for Chaturbate (and Stripchat) streams.
The updated Chaturbate scraper uses a POST request to retrieve the HLS URL 
via free proxies. SSL verification is disabled due to known proxy issues.
"""
import sys
import types
import tempfile  # For generating unique user-data directories
import os
import re
import logging
import uuid
import time
import random
import requests
import urllib3
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
from requests.exceptions import RequestException, SSLError
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from flask import jsonify

# Disable insecure request warnings due to disabled SSL certificate verification.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import models and database session for stream creation.
from models import Stream, ChaturbateStream, StripchatStream, Assignment, TelegramRecipient, User
from extensions import db
from config import app  # Use the Flask app for application context
from notifications import send_text_message

# Global dictionaries to hold job statuses.
scrape_jobs = {}
stream_creation_jobs = {}
executor = ThreadPoolExecutor(max_workers=5)  # Thread pool for parallel scraping

# --- Helper Functions for Job Progress ---
def update_job_progress(job_id, percent, message):
    """Update the progress of a scraping job"""
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
    """Update the progress of a stream creation job"""
    now = time.time()
    
    # Initialize job with default values if not exists
    job = stream_creation_jobs.setdefault(job_id, {
        'start_time': now,
        'progress': 0,
        'message': '',
        'estimated_time': 0,
        'last_updated': now,
        'error': None,
        'stream': None
    })
    
    # Calculate time estimates
    elapsed = now - job['start_time']
    if percent > 0 and percent < 100:
        estimated_total = elapsed / (percent / 100)
        estimated_remaining = max(0, int(estimated_total - elapsed))
    else:
        estimated_remaining = 0

    # Update only if significant change
    if (abs(percent - job['progress']) > 1 or
        message != job['message'] or
        percent == 100):
        
        job.update({
            'progress': min(100, max(0, percent)),
            'message': message,
            'estimated_time': estimated_remaining,
            'last_updated': now
        })
        
        logging.info("Stream Job %s: %s%% - %s (Est: %ss)",
                    job_id, percent, message, estimated_remaining)


# --- New Helper Functions for Chaturbate Scraping ---
def extract_room_slug(url: str) -> str:
    """Extract the room slug from a Chaturbate URL"""
    parsed_url = urlparse(url)
    path_parts = [part for part in parsed_url.path.split('/') if part]
    if not path_parts:
        raise ValueError("No room slug found in URL")
    return path_parts[0]



# --- Updated Proxy List from free-proxy-list.net (Updated at 2025-03-28 21:42:02 UTC) ---
PROXY_LIST = [
    "43.130.47.130:18088",  
"204.236.137.68:80",  
"13.55.210.141:3128",  
"51.16.179.113:1080",  
"51.20.50.149:3128",  
"99.80.11.54:3128",  
"52.63.129.110:3128",  
"51.16.199.206:3128",  
"43.200.77.128:3128",  
"103.129.200.2:8124",  
"13.36.113.81:3128",  
"15.235.10.31:28003",  
"18.230.71.1:20202",  
"51.84.68.153:20202",  
"13.239.31.125:20202",  
"3.68.91.163:20201",  
"34.233.124.56:20202",  
"51.84.57.200:20202",  
"98.81.33.66:20002",  
"18.183.24.164:20202",  
"56.155.28.22:20202",  
"18.182.43.188:20201",  
"15.157.63.239:20202",  
"3.22.116.89:20202",  
"3.27.112.170:20201",  
"18.138.124.192:20202",  
"13.214.122.121:20202",  
"16.171.52.52:20202",  
"3.79.206.9:20202",  
"18.140.231.34:20201",  
"3.99.172.72:20201",  
"18.207.97.58:20201",  
"43.201.58.184:20202",  
"51.20.137.15:20202",  
"18.197.127.166:20201",  
"15.237.27.182:20201",  
"54.173.153.36:20202",  
"51.16.53.5:20202",  
"3.27.16.79:20201",  
"3.128.90.134:20201",  
"13.53.126.216:20201",  
"13.40.100.60:20202",  
"35.183.236.38:20202",  
"13.247.223.169:20202",  
"18.231.121.68:20201",  
"13.51.6.203:20202",  
"47.129.126.231:20005",  
"3.35.133.153:20201",  
"176.34.199.110:20202",  
"3.26.147.255:20202",  
"51.16.113.105:3128",  
"51.44.173.80:20202",  
"13.203.209.37:20202",  
"54.180.131.34:20202",  
"51.17.5.160:20201",  
"51.17.21.181:20202",  
"3.106.120.30:20201",  
"13.247.88.206:20202",  
"15.236.92.30:20201",  
"51.44.185.55:20202",  
"13.231.150.2:20202",  
"51.17.42.250:20202",  
"3.36.99.188:20201",  
"13.124.128.42:20202",  
"51.17.241.16:20202",  
"56.155.27.142:20201",  
"52.26.248.158:3128",  
"51.84.67.35:45554",  
"18.141.156.100:20202",  
"54.215.228.245:20202",  
"3.115.5.216:20202",  
"43.204.227.94:20201",  
"54.209.104.96:20202",  
"3.249.124.251:20202",  
"18.181.208.20:20201",  
"13.250.172.255:20202",  
"18.144.72.79:20201",  
"13.115.194.123:20202",  
"13.214.35.84:20201",  
"54.151.71.253:20201",  
"54.210.2.20:20201",  
"56.155.29.90:20201",  
"13.245.229.158:20201",  
"13.208.183.144:20201",  
"3.27.111.170:20202",  
"54.174.37.207:20005",  
"54.252.193.7:20201",  
"99.79.64.51:20201",  
"18.134.160.73:20201",  
"13.247.58.145:20201",  
"13.49.75.100:20202",  
"15.236.210.236:20201",  
"51.16.53.20:20202",  
"13.208.56.180:80",  
"71.14.218.2:8080",  
"15.152.50.120:20202",  
"18.215.151.253:20201",  
"34.226.195.206:20202",  
"13.125.35.27:20202",  
"13.245.229.200:20201"  

]


def get_random_proxy() -> dict:
    """
    Select a random proxy from the proxy list.
    
    Returns:
        dict: A dictionary with HTTP and HTTPS proxies formatted for requests.
    """
    proxy = random.choice(PROXY_LIST)
    return {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}"
    }




def get_hls_url(room_slug: str, max_attempts: int = 15) -> dict:
    """
    Send a POST request to Chaturbate's endpoint to fetch the HLS URL for a given room.
    Tries multiple proxies from the free proxy list if necessary.
    
    Enhanced logging is added to capture raw responses and diagnose errors.
    If the response does not contain 'hls_url' but does contain 'url', it is used as the HLS URL.
    
    Args:
        room_slug (str): The room slug to query.
        max_attempts (int): Maximum number of attempts with different proxies.
    
    Returns:
        dict: JSON response from the endpoint if successful.
              Expected to contain the HLS URL under 'hls_url' or 'url'.
        None: If all attempts fail.
    """
    url = 'https://chaturbate.com/get_edge_hls_url_ajax/'
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0',
        # ... (headers remain unchanged)
    }

    # Define the boundary string (without prefixed dashes)
    boundary = "----geckoformboundary6a610b256c356f4fb7599aaf07b1de15"

    # Construct the multipart/form-data payload.
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
        'QBEfLYOhYb02QMAA8FsDhvimMi2rbhTh\r\n'
        f'--{boundary}--\r\n'
    )

    attempts = 0
    while attempts < max_attempts:
        proxy_dict = get_random_proxy()
        try:
            logging.info("Attempt %s: Using proxy %s", attempts + 1, proxy_dict['http'])
            response = requests.post(
                url,
                headers=headers,
                data=payload.encode('utf-8'),
                proxies=proxy_dict,
                timeout=10,
                verify=False  # Disable SSL verification due to proxy issues
            )
            response.raise_for_status()  # Raise error for non-200 HTTP status codes
            logging.info("Request successful using proxy %s", proxy_dict['http'])
            try:
                result = response.json()
            except ValueError as json_err:
                # Log the raw response to help diagnose the issue
                logging.error("JSON decoding failed with proxy %s: %s", proxy_dict['http'], json_err)
                logging.error("Raw response content: %s", response.text)
                attempts += 1
                time.sleep(1)
                continue

            # Check for offline status first
            if result.get('room_status') == 'offline':
                logging.error("Room is offline, stopping attempts")
                return {'error': 'room_offline', 'message': 'Stream is offline'}

            if result:
                # Use 'hls_url' if available; otherwise, check for 'url'
                hls_url = result.get("hls_url") or result.get("url")
                if hls_url:
                    logging.info("HLS URL found: %s", hls_url)
                    # Ensure the result dict contains 'hls_url'
                    result["hls_url"] = hls_url
                    return result
                else:
                    error_msg = "HLS URL not found in response"
                    logging.error(error_msg)
                    logging.error("Response content: %s", result)
                    attempts += 1
                    time.sleep(1)
                    continue
            else:
                logging.error("Empty JSON response received.")
                attempts += 1
                time.sleep(1)
                continue
        except (RequestException, SSLError) as e:
            logging.error("Request failed with proxy %s: %s", proxy_dict['http'], e)
            attempts += 1
            time.sleep(1)
        except Exception as e:
            logging.error("Unexpected error with proxy %s: %s", proxy_dict['http'], e)
            attempts += 1
            time.sleep(1)

    logging.error("Exceeded maximum proxy attempts.")
    return None




# --- Updated Chaturbate Scraping Function (Using AJAX) ---
def scrape_chaturbate_data(url, progress_callback=None):
    """
    Scrape Chaturbate data using a POST request to retrieve the HLS URL.
    Uses free proxies to mask the source IP. Progress is reported via the callback.
    
    Args:
        url (str): Full Chaturbate room URL (e.g., "https://chaturbate.com/roomslug/").
        progress_callback (callable, optional): Function to update progress (percent, message).
    
    Returns:
        dict or None: Contains 'streamer_username' and 'chaturbate_m3u8_url' if successful,
                      otherwise None.
    """
    try:
        if progress_callback:
            progress_callback(10, "Extracting room slug")
        room_slug = extract_room_slug(url)
        
        if progress_callback:
            progress_callback(20, "Fetching HLS URL using proxies")
        result = get_hls_url(room_slug)
        
        if result:
            if 'error' in result:
                if result['error'] == 'room_offline':
                    if progress_callback:
                        progress_callback(100, "Stream is offline")
                    return {'status': 'offline', 'message': result['message']}
                else:
                    if progress_callback:
                        progress_callback(100, f"Error: {result.get('message')}")
                    return None
            
            hls_url = result.get("hls_url")
            if hls_url:
                if progress_callback:
                    progress_callback(100, "Scraping complete")
                return {
                    "status": "online",
                    "streamer_username": room_slug,
                    "chaturbate_m3u8_url": hls_url,
                }
            else:
                error_msg = "HLS URL not found in response"
                logging.error(error_msg)
                if progress_callback:
                    progress_callback(100, f"Error: {error_msg}")
                return None
        else:
            if progress_callback:
                progress_callback(100, "Failed to retrieve HLS URL")
            return None

    except Exception as e:
        logging.error("Error scraping Chaturbate URL %s: %s", url, e)
        if progress_callback:
            progress_callback(100, f"Error: {e}")
        return None



# --- Existing Functions Remain Unchanged ---
def fetch_page_content(url, use_selenium=False):
    """
    Fetch the HTML content of the provided URL.
    Uses a robust set of headers to mimic a real browser.
    
    Args:
        url (str): The URL of the webpage to scrape.
        use_selenium (bool): If True, uses Selenium to fetch the page.
        
    Returns:
        str: The HTML content of the webpage.
        
    Raises:
        Exception: If the request fails.
    """
    if use_selenium:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--ignore-certificate-errors")
        unique_user_data_dir = tempfile.mkdtemp()
        chrome_options.add_argument(f"--user-data-dir={unique_user_data_dir}")
        driver = webdriver.Chrome(options=chrome_options)
        try:
            driver.get(url)
            time.sleep(5)
            return driver.page_source
        finally:
            driver.quit()
    else:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:112.0) "
                "Gecko/20100101 Firefox/112.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://chaturbate.com/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        session = requests.Session()
        try:
            response = session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logging.error("Direct request failed: %s. Trying Selenium...", e)
            return fetch_page_content(url, use_selenium=True)


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


def scrape_stripchat_data(url, progress_callback=None):
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
    """Run a scraping job and update progress interactively."""
    update_job_progress(job_id, 0, "Starting scrape job")
    if "chaturbate.com" in url:
        result = scrape_chaturbate_data(url, progress_callback=lambda p, m: update_job_progress(job_id, p, m))
    elif "stripchat.com" in url:
        result = scrape_stripchat_data(url, progress_callback=lambda p, m: update_job_progress(job_id, p, m))
    else:
        logging.error("Unsupported platform for URL: %s", url)
        result = None
    if result:
        scrape_jobs[job_id]["result"] = result
    else:
        scrape_jobs[job_id]["error"] = "Scraping failed"
    update_job_progress(job_id, 100, scrape_jobs[job_id].get("error", "Scraping complete"))


    def run_stream_creation_job(job_id, room_url, platform, agent_id=None):
        """Phased stream creation with proper DB handling"""
        with app.app_context():
            try:
                # Initialize job first
                stream_creation_jobs[job_id] = {
                    'start_time': time.time(),
                    'progress': 0,
                    'message': 'Initializing',
                    'estimated_time': 120,
                    'last_updated': time.time(),
                    'error': None,
                    'stream': None
                }

                # Phase 1: Validation with explicit commit
                update_stream_job_progress(job_id, 5, "Validating input parameters")
                with db.session.begin():
                    exists = db.session.query(
                        db.exists().where(Stream.room_url == room_url)
                    ).scalar()
                    
                if exists:
                    raise ValueError(f"Stream {room_url} already exists")

            # Phase 2: Scraping
            update_stream_job_progress(job_id, 10, f"Starting {platform} scraping")
            scraped_data = None
            if platform == "chaturbate":
                scraped_data = scrape_chaturbate_data(
                    room_url,
                    progress_callback=lambda p, m: update_stream_job_progress(
                        job_id, 10 + p*0.35, f"Scraping: {m}")
                )
            else:
                scraped_data = scrape_stripchat_data(
                    room_url,
                    progress_callback=lambda p, m: update_stream_job_progress(
                        job_id, 10 + p*0.35, f"Scraping: {m}")
                )

            if not scraped_data or 'status' not in scraped_data:
                raise RuntimeError("Invalid scraping response")
            if scraped_data.get('status') == 'offline':
                raise RuntimeError("Stream is offline")

            # Phase 3: Database operations
            update_stream_job_progress(job_id, 50, "Creating stream record")
            streamer_username = scraped_data.get("streamer_username") or \
                              room_url.rstrip("/").split("/")[-1]
                              
            stream_class = ChaturbateStream if platform == "chaturbate" else StripchatStream
            stream = stream_class(
                room_url=room_url,
                streamer_username=streamer_username,
                **{f"{platform}_m3u8_url": scraped_data[f"{platform}_m3u8_url"]}
            )
            
            db.session.add(stream)
            db.session.commit()
            db.session.refresh(stream)

            # Phase 4: Agent assignment
            if agent_id:
                update_stream_job_progress(job_id, 70, "Assigning agent")
                if not User.query.get(agent_id):
                    raise ValueError("Invalid agent ID")
                    
                assignment = Assignment(agent_id=agent_id, stream_id=stream.id)
                db.session.add(assignment)
                db.session.commit()

            # Phase 5: Finalization
            update_stream_job_progress(job_id, 90, "Finalizing stream setup")
            try:
                send_telegram_notifications(
                    platform=platform,
                    streamer=streamer_username,
                    room_url=room_url
                )
            except Exception as notification_error:
                logging.error("Notification failed: %s", str(notification_error))

            # Complete successfully
            update_stream_job_progress(job_id, 100, "Stream created successfully")
            stream_creation_jobs[job_id].update({
                "stream": stream.serialize(),
                "estimated_time": 0
            })

        except Exception as e:
            db.session.rollback()
            error_message = f"Creation failed: {str(e)}"
            update_stream_job_progress(job_id, 100, error_message)
            stream_creation_jobs[job_id]["error"] = error_message
            logging.exception("Stream creation error")

        finally:
            try:
                db.session.close()
            except Exception as db_close_error:
                logging.warning("DB session close error: %s", str(db_close_error))

def send_telegram_notifications(platform, streamer, room_url):
    """Handle Telegram notifications with error tracking"""
    try:
        recipients = TelegramRecipient.query.all()
        if not recipients:
            return

        message = (
            f"🚀 New Stream Created\n"
            f"Platform: {platform.capitalize()}\n"
            f"Streamer: {streamer}\n"
            f"URL: {room_url}"
        )
        
        for recipient in recipients:
            try:
                executor.submit(
                    send_text_message,
                    message=message,
                    chat_id=recipient.chat_id,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.error("Telegram send failed for %s: %s", 
                            recipient.chat_id, str(e))
                
    except Exception as e:
        logging.error("Notification system error: %s", str(e))

def fetch_chaturbate_chat_history(room_slug):
    """Fetch chat history from Chaturbate's API endpoint."""
    url = "https://chaturbate.com/push_service/room_history/"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://chaturbate.com/{room_slug}/",
        "Origin": "https://chaturbate.com",
        "Cookie": 'csrftoken=vfO2sk8hUsSXVILMJwtcyGqhPy6WqwhH; stcki="Eg6Gdq=1,kHDa2i=1"'
    }
    
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json().get("0", {}).values()
    except Exception as e:
        logging.error(f"Chat history fetch error: {str(e)}")
        return []


def refresh_chaturbate_stream(room_slug):
    """
    Refresh the m3u8 URL for a Chaturbate stream based on the given room slug.
    Attempts to find a valid m3u8 URL by rotating through edge servers.
    
    Args:
        room_slug (str): The room slug (streamer username).
    
    Returns:
        str or None: The new m3u8 URL if successful, or None if an error occurred.
    """
    # Template for Chaturbate livestream URL
    url_template = (
        "https://edge{edge_num}-sof.live.mmcdn.com/live-edge/"
        "amlst:{room_slug}-sd-2c7654400be3ea198275ea9be7c29a7ed69b094af88455a15e4eda04d8fbc54c_trns_h264/playlist.m3u8"
    )
    
    try:
        # Try edge servers 1-50
        for edge_num in range(1, 50):
            try:
                new_url = url_template.format(edge_num=edge_num, room_slug=room_slug)
                response = requests.head(new_url, timeout=60)
                if response.status_code == 200:
                    stream = ChaturbateStream.query.filter_by(streamer_username=room_slug).first()
                    if stream:
                        stream.chaturbate_m3u8_url = new_url
                        try:
                            db.session.commit()
                            logging.info("Updated stream '%s' with new m3u8 URL: %s", room_slug, new_url)
                            return new_url
                        except Exception as db_e:
                            db.session.rollback()
                            logging.error("Database commit failed: %s", db_e)
                            return None
                    else:
                        logging.info("No existing stream found, but valid URL found: %s", new_url)
                        return new_url
            except Exception as e:
                logging.debug("Edge%s failed for %s: %s", edge_num, room_slug, e)
                continue
        
        logging.error("No valid m3u8 URL found for room slug: %s", room_slug)
        return None
    
    except Exception as e:
        logging.error("Error refreshing stream for room slug %s: %s", room_slug, e)
        return None

def refresh_stripchat_stream(room_url: str) -> str:
    """
    Refresh the M3U8 URL for a Stripchat stream by re-scraping the page.
    
    Args:
        room_url (str): The full URL of the Stripchat room.
    
    Returns:
        str: The new M3U8 URL if successful, None otherwise.
    """
    try:
        scraped_data = scrape_stripchat_data(room_url)
        if not scraped_data:
            return None
        new_url = scraped_data.get("stripchat_m3u8_url")
        if new_url:
            stream = StripchatStream.query.filter_by(room_url=room_url).first()
            if stream:
                stream.stripchat_m3u8_url = new_url
                db.session.commit()
                return new_url
        return None
    except Exception as e:
        logging.error(f"Error refreshing Stripchat stream: {str(e)}")
        return None




