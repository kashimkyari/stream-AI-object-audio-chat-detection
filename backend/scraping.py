#!/usr/bin/env python3
"""
chaturbate_scraper_updated.py

This module provides scraping functions for Chaturbate (and Stripchat) streams.
The updated Chaturbate scraper uses a POST request to retrieve the HLS URL 
via free proxies. SSL verification is disabled due to known proxy issues.
"""
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
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
    """Update job progress with safe initialization"""
    now = time.time()
    
    # Initialize job with default values
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

"52.67.10.183:80",
"200.250.131.218:80",
"152.230.215.123:80",
"85.214.107.177:80",
"154.0.14.116:3128",
"141.95.238.126:8080",
"91.134.55.236:8080",
"219.65.73.81:80",
"170.106.135.2:13001",
"43.153.36.22:3334",
"188.68.52.244:80",
"43.153.117.40:13001",
"49.51.250.227:13001",
"43.153.117.193:13001",
"43.153.105.141:13001",
"43.130.32.94:13001",
"170.106.137.158:13001",
"170.106.143.168:13001",
"79.127.158.225:8081",
"49.51.179.85:13001",
"170.106.100.130:13001",
"43.135.161.247:13001",
"170.106.67.179:13001",
"43.153.78.185:13001",
"49.51.197.116:13001",
"170.106.64.187:13001",
"43.135.183.46:13001",
"43.135.129.111:13001",
"43.153.16.149:13001",
"43.153.4.125:13001",
"170.106.196.118:13001",
"170.106.80.237:13001",
"43.159.129.136:13001",
"170.106.82.224:13001",
"49.51.203.51:13001",
"43.135.138.21:13001",
"43.135.172.243:13001",
"51.91.237.124:8080",
"170.106.173.254:13001",
"43.135.179.180:13001",
"43.130.16.92:13001",
"43.130.38.18:13001",
"43.130.0.130:13001",
"170.106.198.54:13001",
"43.130.57.165:13001",
"170.106.192.157:13001",
"170.106.194.126:13001",
"43.135.134.89:13001",
"43.135.130.88:13001",
"43.130.2.30:13001",
"170.106.169.110:13001",
"43.135.164.4:13001",
"43.153.28.45:13001",
"43.130.48.100:13001",
"43.130.37.196:13001",
"43.130.29.139:13001",
"43.135.164.2:13001",
"43.130.42.164:13001",
"43.153.79.9:13001",
"65.49.14.6:3128",
"47.88.137.92:5020",
"43.153.92.57:13001",
"43.153.100.212:13001",
"43.153.79.15:13001",
"43.153.2.3:13001",
"103.213.218.22:13137",
"37.114.192.104:3128",
"51.44.176.151:20202",
"18.223.25.15:80",
"212.33.205.55:3128",
"188.166.230.109:31028",
"65.49.2.99:3128",
"49.51.249.217:13001",
"54.37.214.253:8080",
"63.32.1.88:3128",
"121.200.50.33:3128",
"43.153.21.33:13001",
"43.153.35.252:13001",
"8.219.97.248:80",
"8.210.17.35:9443",
"62.210.15.199:80",
"117.103.68.38:9941",
"15.236.106.236:3128",
"47.252.29.28:11222",
"23.247.136.248:80",
"3.126.147.182:80",
"35.72.118.126:80",
"43.202.154.212:80",
"3.127.62.252:80",
"18.228.149.161:80",
"3.127.121.101:80",
"3.78.92.159:3128",
"51.16.199.206:3128",
"52.63.129.110:3128",
"52.65.193.254:3128",
"51.16.179.113:1080",
"3.212.148.199:3128",
"54.248.238.110:80",
"44.219.175.186:80",
"162.223.90.130:80"

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
    Includes necessary headers and cookies observed from browser DevTools.
    """
    url = 'https://chaturbate.com/get_edge_hls_url_ajax/'
    
    # Dynamic boundary generation
    boundary = uuid.uuid4().hex
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f'https://chaturbate.com/{room_slug}/',
        'Origin': 'https://chaturbate.com',
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Cookie': (
            'csrftoken=QBEfLYOhYb02QMAA8FsDhvimMi2rbhTh; '
            '__cf_bm=aRWJoCGvyxZsRyCS9qMJeMwF1ikmvIEucwTQpB3VDcE-1743303491-1.0.1.1-pc6j_3W8_POkMuCh2yhnhdG18vOaMl1tAsv9bIjj8wDQn9M4W3pGJN5yaucI8_vJp4meSVffE62zILQmuHg.ipapPlEw3OCsfsBNg05dEV0; '
            'sbr=sec:sbr9f095e3f-07ec-4e77-a51a-051c8118632f:1txykY:nZcRPVNiTcLgruuwAyCND2URhh7k8KiarIG-keMrJm0; '
            'agreeterms=1; '
            'stcki="Eg6Gdq=1"'
        )
    }

    # Construct dynamic multipart payload
    payload = (
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="room_slug"\r\n\r\n'
        f'{room_slug}\r\n'
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="bandwidth"\r\n\r\n'
        'high\r\n'
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="current_edge"\r\n\r\n'
        '\r\n'  # Empty current_edge to let server assign
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
            response = requests.post(
                url,
                headers=headers,
                data=payload.encode('utf-8'),
                proxies=proxy_dict,
                timeout=10,
                verify=False
            )
            response.raise_for_status()
            result = response.json()

            if result.get('room_status') == 'offline':
                return {'error': 'room_offline', 'message': 'Stream is offline'}

            hls_url = result.get("hls_url") or result.get("url")
            if hls_url:
                result["hls_url"] = hls_url
                return result
            
            attempts += 1
        except Exception as e:
            attempts += 1
            time.sleep(1)

    return None


# --- Updated Chaturbate Scraping Function (Using AJAX) ---
def scrape_chaturbate_data(url, progress_callback=None):
    """Enhanced Chaturbate scraper with validation"""
    try:
        # Initial validation
        if not url or 'chaturbate.com/' not in url:
            raise ValueError("Invalid Chaturbate URL")

        # Progress tracking
        def update_progress(p, m):
            if progress_callback:
                progress_callback(p, m)

        update_progress(10, "Extracting room slug")
        room_slug = extract_room_slug(url)
        
        update_progress(30, "Fetching HLS URL")
        result = get_hls_url(room_slug)
        
        # Response validation
        if not result:
            raise ValueError("Empty response from Chaturbate API")
        
        if 'error' in result:
            error_msg = result.get('message', 'Unknown error')
            raise RuntimeError(f"Chaturbate API error: {error_msg}")
            
        hls_url = result.get("hls_url") or result.get("url")
        if not hls_url:
            raise ValueError("Missing HLS URL in response")
            
        if 'edge' not in hls_url:
            raise ValueError("Invalid HLS URL format")

        update_progress(100, "Scraping complete")
        return {
            "status": "online",
            "streamer_username": room_slug,
            "chaturbate_m3u8_url": hls_url,
        }

    except Exception as e:
        error_msg = f"Scraping failed: {str(e)}"
        logging.error(error_msg)
        if progress_callback:
            progress_callback(100, error_msg)
        return {
            "status": "error",
            "message": error_msg,
            "details": str(e)
        }


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
    """Stripchat scraper with improved m3u8 extraction from network resources"""
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By

    def update_progress(p, m):
        if progress_callback:
            progress_callback(p, m)

    MAX_ATTEMPTS = 3
    stream_data = None

    for attempt in range(MAX_ATTEMPTS):
        proxy = get_random_proxy()
        update_progress(10, f"Attempt {attempt+1}/{MAX_ATTEMPTS} - Initializing browser")

        try:
            # Configure browser with stealth options
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-web-security")  # Allow cross-origin requests for better network capture
            chrome_options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
            
            # Configure proxy and network monitoring through Selenium Wire
            seleniumwire_options = {
                'proxy': {
                    'http': proxy['http'],
                    'https': proxy['https'],
                    'no_proxy': 'localhost,127.0.0.1'
                },
                'verify_ssl': False,
                'connection_timeout': 30,
                # Enable request storage
                'enable_har': True
            }

            # Create a more targeted request filter to capture m3u8 URLs
            def custom_request_interceptor(request):
                # Add additional headers to bypass anti-bot measures
                request.headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                request.headers['Accept-Language'] = 'en-US,en;q=0.5'
                request.headers['Accept-Encoding'] = 'gzip, deflate, br'
                request.headers['DNT'] = '1'
                request.headers['Connection'] = 'keep-alive'
                request.headers['Upgrade-Insecure-Requests'] = '1'
                request.headers['Sec-Fetch-Dest'] = 'document'
                request.headers['Sec-Fetch-Mode'] = 'navigate'
                request.headers['Sec-Fetch-Site'] = 'none'
                request.headers['Sec-Fetch-User'] = '?1'
                request.headers['Cache-Control'] = 'max-age=0'

            driver = webdriver.Chrome(
                options=chrome_options,
                seleniumwire_options=seleniumwire_options
            )
            
            # Set custom request interceptor
            driver.request_interceptor = custom_request_interceptor

            try:
                update_progress(30, "Loading page via proxy")
                driver.set_page_load_timeout(45)
                
                # Set a specific filter for m3u8 requests before loading the page
                driver.scopes = [
                    '.*\.m3u8.*',  # Capture all m3u8 requests
                    '.*chunklist.*',  # Also capture chunklist requests
                    '.*playlist.*'   # And playlist requests
                ]
                
                driver.get(url)
                update_progress(40, "Waiting for video element")
                
                # Wait for critical elements
                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.XPATH, "//video"))
                    )
                except Exception as wait_error:
                    logging.warning(f"Video element wait timed out: {str(wait_error)}")
                
                # Give extra time for network requests to complete
                update_progress(50, "Capturing network requests")
                time.sleep(5)  # Allow time for requests to process

                # First try: Extract from video element
                m3u8_url = None
                try:
                    m3u8_url = driver.execute_script(
                        "return document.querySelector('video').src"
                    )
                    if m3u8_url and '.m3u8' in m3u8_url:
                        logging.info(f"Found m3u8 URL from video element: {m3u8_url}")
                except Exception as js_error:
                    logging.warning(f"JS extraction failed: {str(js_error)}")

                # Second try: Extract from network requests
                if not m3u8_url or '.m3u8' not in m3u8_url:
                    update_progress(60, "Searching network requests")
                    # Sort requests by time, most recent first
                    for request in reversed(driver.requests):
                        if request.response and '.m3u8' in request.url:
                            # Prioritize higher quality streams (chunklist)
                            if 'chunklist' in request.url:
                                m3u8_url = request.url
                                logging.info(f"Found chunklist m3u8 URL: {m3u8_url}")
                                break
                            # Otherwise take any m3u8 URL
                            elif not m3u8_url:  # Only set if we haven't found a better URL
                                m3u8_url = request.url
                                logging.info(f"Found m3u8 URL from network: {m3u8_url}")

                # Third try: Look for URLs in the page source
                if not m3u8_url or '.m3u8' not in m3u8_url:
                    update_progress(70, "Searching page source")
                    page_source = driver.page_source
                    m3u8_matches = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', page_source)
                    if m3u8_matches:
                        m3u8_url = m3u8_matches[0]
                        logging.info(f"Found m3u8 URL from page source: {m3u8_url}")

                # Fourth try: Execute specific JavaScript to find HLS sources
                if not m3u8_url or '.m3u8' not in m3u8_url:
                    update_progress(80, "Executing JavaScript to find HLS sources")
                    try:
                        hls_sources = driver.execute_script("""
                            const videoElements = document.querySelectorAll('video');
                            const sources = [];
                            
                            for (const video of videoElements) {
                                if (video.src && video.src.includes('.m3u8')) {
                                    sources.push(video.src);
                                }
                                
                                const sourceElements = video.querySelectorAll('source');
                                for (const source of sourceElements) {
                                    if (source.src && source.src.includes('.m3u8')) {
                                        sources.push(source.src);
                                    }
                                }
                            }
                            
                            // Also check for URLs in JSON data
                            const scripts = document.querySelectorAll('script');
                            for (const script of scripts) {
                                const content = script.textContent || '';
                                const m3u8Match = content.match(/(https?:\/\/[^"']+\.m3u8[^"']*)/);
                                if (m3u8Match) {
                                    sources.push(m3u8Match[1]);
                                }
                            }
                            
                            return sources;
                        """)
                        
                        if hls_sources and len(hls_sources) > 0:
                            m3u8_url = hls_sources[0]
                            logging.info(f"Found m3u8 URL from JS extraction: {m3u8_url}")
                    except Exception as js_error:
                        logging.warning(f"Advanced JS extraction failed: {str(js_error)}")

                # Clean and validate the URL
                if m3u8_url and re.match(r'https?://[^\s]+\.m3u8', m3u8_url):
                    # Remove any query parameters for cleaner URL
                    m3u8_url = m3u8_url.split('?')[0] if '?' in m3u8_url else m3u8_url
                    update_progress(90, "Valid m3u8 URL found")
                    
                    # Extract streamer username from URL
                    streamer_username = url.rstrip('/').split('/')[-1]
                    
                    stream_data = {
                        "status": "online",
                        "streamer_username": streamer_username,
                        "stripchat_m3u8_url": m3u8_url
                    }
                    break
                else:
                    update_progress(85, "No valid m3u8 URL found, trying a different approach")

            except Exception as e:
                logging.warning(f"Attempt {attempt+1} failed: {str(e)}")
                try:
                    driver.save_screenshot(f'stripchat_error_{attempt}.png')
                except:
                    pass

            finally:
                driver.quit()
                # Clean up tempfiles
                try:
                    for file in driver._driver_kwargs.get('seleniumwire_options', {}).get('request_storage_base_dir', []):
                        if os.path.exists(file):
                            os.remove(file)
                except:
                    pass

        except Exception as fatal_error:
            logging.error(f"Proxy connection failed: {str(fatal_error)}")

        # Add a small delay between attempts
        time.sleep(2)

    if not stream_data:
        return {
            "status": "error",
            "message": "Failed to extract m3u8 URL after multiple attempts",
            "error_type": "extraction_failure",
            "platform": "stripchat"
        }

    # Verify M3U8 accessibility
    try:
        update_progress(95, "Verifying stream URL")
        verify_response = requests.head(
            stream_data['stripchat_m3u8_url'],
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }
        )
        
        if verify_response.status_code != 200:
            return {
                "status": "error",
                "message": f"Stream URL verification failed with status {verify_response.status_code}",
                "error_type": "verification_failure",
                "platform": "stripchat"
            }
    except Exception as verification_error:
        logging.error(f"Stream verification error: {str(verification_error)}")
        # Continue anyway, as direct verification might be blocked but the URL could still work

    update_progress(100, "Scraping complete")
    return stream_data

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
    """Complete stream creation handler"""
    with app.app_context():
        # Initialize job record
        stream_creation_jobs[job_id] = {
            'start_time': time.time(),
            'progress': 0,
            'message': 'Initializing',
            'estimated_time': 120,
            'last_updated': time.time(),
            'error': None,
            'stream': None
        }
        
        try:
            # Phase 1: Validation
            update_stream_job_progress(job_id, 5, "Validating input")
            with db.session.begin():
                if db.session.query(Stream).filter_by(room_url=room_url).first():
                    raise ValueError(f"Stream exists: {room_url}")

            # Phase 2: Scraping
            update_stream_job_progress(job_id, 10, f"Scraping {platform}")
            scraped_data = None
            try:
                if platform == "chaturbate":
                    scraped_data = scrape_chaturbate_data(
                        room_url,
                        lambda p, m: update_stream_job_progress(
                            job_id, 10 + p*0.35, m)
                    )
                else:
                    scraped_data = scrape_stripchat_data(
                        room_url,
                        lambda p, m: update_stream_job_progress(
                            job_id, 10 + p*0.35, m)
                    )

                # Validate scraping results
                if not scraped_data or 'status' not in scraped_data:
                    raise RuntimeError("Invalid scraping response")
                
                if scraped_data['status'] != 'online':
                    raise RuntimeError(scraped_data.get('message', 'Scraping failed'))
                    
                if not scraped_data.get(f"{platform}_m3u8_url"):
                    raise RuntimeError("Missing stream URL")

            except Exception as e:
                raise RuntimeError(f"Scraping failed: {str(e)}") from e

            # Phase 3: Database
            update_stream_job_progress(job_id, 50, "Creating record")
            try:
                # In the section where the stream is created:
                if platform == "chaturbate":
                    stream = ChaturbateStream(
                        room_url=room_url,
                        streamer_username=scraped_data['streamer_username'],
                        chaturbate_m3u8_url=scraped_data['chaturbate_m3u8_url'],
                        type='chaturbate'
                    )
                else:
                    stream = StripchatStream(
                        room_url=room_url,
                        streamer_username=scraped_data['streamer_username'],
                        stripchat_m3u8_url=scraped_data['stripchat_m3u8_url'],
                        type='stripchat'
                    )
                    
                db.session.add(stream)
                db.session.commit()
                db.session.refresh(stream)
            except Exception as e:
                db.session.rollback()
                raise RuntimeError(f"Database error: {str(e)}")

            # Phase 4: Agent assignment
            if agent_id:
                update_stream_job_progress(job_id, 70, "Assigning agent")
                try:
                    if not User.query.get(agent_id):
                        raise ValueError("Invalid agent ID")
                        
                    assignment = Assignment(
                        agent_id=agent_id,
                        stream_id=stream.id
                    )
                    db.session.add(assignment)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    raise RuntimeError(f"Assignment failed: {str(e)}")

            # Phase 5: Finalization
            update_stream_job_progress(job_id, 90, "Finalizing")
            try:
                send_telegram_notifications(
                    platform,
                    stream.streamer_username,
                    room_url
                )
            except Exception as e:
                logging.error("Notifications failed: %s", str(e))

            # Success
            update_stream_job_progress(job_id, 100, "Stream created")
            stream_creation_jobs[job_id].update({
                'stream': stream.serialize(),
                'estimated_time': 0
            })

        except Exception as e:
            db.session.rollback()
            error_msg = f"Creation failed: {str(e)}"
            logging.error("Full error: %s", error_msg)
            if hasattr(e, '__cause__'):
                logging.error("Root cause: %s", str(e.__cause__))
                
            stream_creation_jobs[job_id].update({
                'error': error_msg,
                'progress': 100,
                'message': error_msg
            })

        finally:
            try:
                db.session.close()
            except Exception as e:
                logging.warning("Session close error: %s", str(e))


def send_telegram_notifications(platform, streamer, room_url):
    """Robust notification handler"""
    try:
        recipients = TelegramRecipient.query.all()
        if not recipients:
            return

        message = (
            f"New Stream: {streamer}\n"
            f"Platform: {platform}\n"
            f"URL: {room_url}"
        )
        
        for recipient in recipients:
            try:
                executor.submit(
                    send_text_message,
                    message=message,
                    chat_id=recipient.chat_id
                )
            except Exception as e:
                logging.error("Failed to notify %s: %s", 
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




