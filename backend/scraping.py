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
from requests.exceptions import RequestException
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from flask import jsonify

# Disable insecure request warnings due to disabled SSL certificate verification.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import models and database session for stream creation.
from models import ChaturbateStream, StripchatStream, Assignment, TelegramRecipient
from extensions import db
from config import app  # Use the Flask app for application context
from notifications import send_text_message

# Global dictionaries to hold job statuses.
scrape_jobs = {}
stream_creation_jobs = {}
executor = ThreadPoolExecutor(max_workers=5)  # Thread pool for parallel scraping

# --- Helper Functions for Job Progress ---
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


# --- New Helper Functions for Chaturbate Scraping ---
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


# Global list of free proxies (IP:port) updated at 2025-03-28 21:42:02 UTC.
PROXY_LIST = [
    "43.153.16.223:13001",
    "170.106.100.130:13001",
    "216.229.112.25:8080",
    "52.73.224.54:3128",
    "43.153.98.125:13001",
    "43.153.103.42:13001",
    "43.153.106.210:13001",
    "43.153.107.10:13001",
    "51.20.19.159:3128",
    "13.55.210.141:3128",
    "16.16.239.39:3128",
    "51.16.179.113:1080",
    "3.97.176.251:3128",
    "15.156.24.206:3128",
    "13.246.184.110:3128",
    "99.80.11.54:3128",
    "13.246.209.48:1080",
    "204.236.176.61:3128",
    "43.130.109.92:13001",
    "43.153.45.169:13001",
    "43.130.11.212:13001",
    "18.228.198.164:80",
    "43.201.121.81:80",
    "35.72.118.126:80",
    "13.208.56.180:80",
    "43.159.132.190:13001",
    "49.51.232.89:13001",
    "4.145.89.88:8080",
    "13.56.192.187:80",
    "184.169.154.119:80",
    "178.63.237.145:7575",
    "13.38.176.104:3128",
    "13.37.59.99:3128",
    "170.106.135.2:13001",
    "18.230.71.1:20202",
    "34.233.124.56:20202",
    "98.81.33.66:20002",
    "18.182.43.188:20201",
    "54.233.45.198:20202",
    "3.22.116.89:20202",
    "54.75.158.178:20201",
    "16.171.52.52:20202",
    "13.251.59.10:20202",
    "15.237.27.182:20201",
    "54.173.153.36:20202",
    "13.251.1.82:20202",
    "54.159.36.185:20201",
    "3.128.90.134:20201",
    "51.44.176.151:20202",
    "13.247.223.169:20202",
    "51.17.85.72:20201",
    "13.203.209.37:20202",
    "43.207.50.162:20202",
    "15.236.92.30:20201",
    "56.155.27.142:20201",
    "3.27.132.207:20201",
    "3.75.101.111:20201",
    "16.170.223.72:45554",
    "13.250.172.255:20202",
    "51.17.115.67:20202",
    "13.214.35.84:20201",
    "54.180.234.231:20201",
    "54.151.71.253:20201",
    "51.17.40.85:20201",
    "13.247.58.145:20201",
    "13.55.192.34:20202",
    "3.88.235.53:20202",
    "50.19.39.56:20201",
    "52.201.245.219:20202",
    "141.95.238.126:8080",
    "54.248.238.110:80",
    "43.153.16.91:13001",
    "43.153.85.209:13001",
    "63.32.1.88:3128",
    "3.97.167.115:3128",
    "13.213.114.238:3128",
    "3.130.65.162:3128",
    "43.130.38.18:13001",
    "35.76.62.196:80",
    "43.159.149.62:13001",
    "43.135.178.216:13001",
    "49.51.193.30:13001",
    "43.153.105.141:13001",
    "49.51.38.113:13001",
    "187.217.194.178:8080",
    "51.84.57.200:20202",
    "35.78.198.199:20202",
    "18.183.24.164:20202",
    "13.244.157.177:20202",
    "51.17.112.131:20202",
    "13.214.122.121:20202",
    "18.230.74.67:20202",
    "3.99.172.72:20201",
    "18.197.127.166:20201",
    "51.16.53.5:20202",
    "3.27.16.79:20201",
    "52.53.183.6:20202",
    "98.81.79.162:20202",
    "13.53.126.216:20201",
    "18.138.241.49:20202",
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
    
    Args:
        room_slug (str): The room slug to query.
        max_attempts (int): Maximum number of attempts with different proxies.
    
    Returns:
        dict: JSON response from the endpoint if successful.
              Expected to contain the key 'hls_url'.
        None: If all attempts fail.
    """
    url = 'https://chaturbate.com/get_edge_hls_url_ajax/'
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Referer': f'https://chaturbate.com/{room_slug}/',
        'X-NewRelic-ID': 'VQIGWV9aDxACUFNVDgMEUw==',
        'newrelic': 'eyJ2IjpbMCwxXSwiZCI6eyJ0eSI6IkJyb3dzZXIiLCJhYyI6IjE0MTg5OTciLCJhcCI6IjI0NTA2NzUwIiwiaWQiOiI3ZWJkMTk3MDQxMTUwOGY5IiwidHIiOiJiYzU3ZDE4Y2RiN2U0ZjVjMjgzMmUxYTdmZTA1ODcyYSIsInRpIjoxNzQzMTg3NDY1MDAyfX0=',
        'traceparent': '00-bc57d18cdb7e4f5c2832e1a7fe05872a-7ebd1970411508f9-01',
        'tracestate': '1418997@nr=0-1-1418997-24506750-7ebd1970411508f9----1743187465002',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'multipart/form-data; boundary=----geckoformboundary6a610b256c356f4fb7599aaf07b1de15',
        'Origin': 'https://chaturbate.com',
        'Connection': 'keep-alive',
        'Cookie': (
            'csrftoken=QBEfLYOhYb02QMAA8FsDhvimMi2rbhTh; '
            'affkey="eJx1jEEKhTAMBa8SsslGrUQ/Qm7zUauiUqmFLsS7S4TiRnfDm8cc6FEAxxC2XYyJMRaDc8PSF61bDWaAnXou+ZeXnHMDXAnXUjfqbFB5kCcB+mhQBvS3Vh+KncJLTt2WTsHPCdv1WRPs012hE88LBBcvuQ=="; '
            'sbr=sec:sbr9f095e3f-07ec-4e77-a51a-051c8118632f:1txykY:nZcRPVNiTcLgruuwAyCND2URhh7k8KiarIG-keMrJm0; '
            'agreeterms=1; *ga*GX0FLQH21P=GS1.1.1743184454.89.1.1743187454.0.0.0; '
            '*ga=GA1.1.1168548972.1740698693; '
            '*_utfpp=f:trnxe24f72c170ba31fce403b24790344164:1tyDuC:xbeHGH_IVk_zJ7fCru4B9cPNtf8CygJAak-5isMJL80; '
            'ag={"18to21-cams":44,"20to30-cams":169,"30to50-cams":1,"teen-cams":7}; '
            '*iidt=S2MQGvAmZ4b0Q9yh/u+gqep47eY16gzG9f3Zk7mjcnUw/NAQdEDPDUFKML3I4WazjVDyDp++4p6Yuw==; '
            '*vid_t=XfyHEnNugyWCCux5Ihh3neS4GdETZcpEz/Uhl7Xq/U70+U0/ZoLRbwlxuB+yb0EfdVPwGwM3W4F5BA==; '
            '__cf_bm=qPhk3uapv9sxmHBNTtrQRBPHv03gc0DZjZeDKte8s7k-1743186615-1.0.1.1-eeYAfpneSLyhG5ii1JiOS.FEI_oSQ5yA.oyYxOoQSv5u5FMuqS2cr5QI4NKDWa4lWDyghY_gyEzgwkUywjtwWwddeHKk.VmaY8kBkrMfIHA; '
            'cf_clearance=tnF75pLB8eFZEUikS5OPTINkrhEvcomnt9vfKMw5JNM-1743187276-1.2.1.1-QLV90oVctAggVWp8bskoOTIPaVnL04Rql8gM4AtI7_nBBGibb6TaAzXUIZzQaDjh_mZGIi2uZujUSW5xBbONM4LY_imBh.ASxLCrtAwtlb17Cy6W5_rotlanU1LlX9UFG6Yf_QS4yagcjpfYoPHnvM9.tOtwfZw655j4TcWXMPb2qj_5NCgKKiUZx77DhLmN4gV4QziW1Ud0QIzMTFgyvb8F0WCXpYsW5fd7TfVoXD3pcDATTZXcV1VDLeIjHqMNw7lOJkeE0AH2sGnVzhdOi3Lb.OEDhZdp0tr3EgqKLdhA7Cz0if26VPFdylei2Q1OS7MYEjdQhEUIIU6_EnGxry..IKM4cUvPVEO8VqB64z1Y; '
            'stcki="Eg6Gdq=1"; '
            f'tbu_{room_slug}={{"source":"df","index":4,"source_filter":"{{}}","room_list_id":"5ed8234b-4ce5-4a52-9699-86ab9105b907"}}; '
            'language_subdomain_continuity=1'
        )
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
            logging.info("Attempt %s: Using proxy %s", attempts+1, proxy_dict['http'])
            response = requests.post(
                url,
                headers=headers,
                data=payload.encode('utf-8'),
                proxies=proxy_dict,
                timeout=10,
                verify=False  # Disable SSL verification due to proxy issues
            )
            response.raise_for_status()  # Raise error for bad HTTP status codes
            logging.info("Request successful using proxy %s", proxy_dict['http'])
            return response.json()
        except RequestException as e:
            logging.error("Request failed with proxy %s: %s", proxy_dict['http'], e)
            attempts += 1
            time.sleep(1)  # Brief pause before retrying
        except ValueError as e:
            logging.error("JSON decoding failed: %s", e)
            return None

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
            hls_url = result.get("hls_url")
            if hls_url:
                if progress_callback:
                    progress_callback(100, "Scraping complete")
                return {
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
    with app.app_context():
        try:
            update_stream_job_progress(job_id, 5, "Initializing scraping...")
            if platform == "chaturbate":
                scraped_data = scrape_chaturbate_data(room_url, progress_callback=lambda p, m: update_stream_job_progress(job_id, 5 + p * 0.45, m))
            else:
                scraped_data = scrape_stripchat_data(room_url, progress_callback=lambda p, m: update_stream_job_progress(job_id, 5 + p * 0.45, m))
            
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
