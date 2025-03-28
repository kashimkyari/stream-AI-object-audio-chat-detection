#!/usr/bin/env python3
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

from concurrent.futures import ThreadPoolExecutor
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from flask import jsonify

# Import models and database session for stream creation.
from models import ChaturbateStream, StripchatStream, Assignment, TelegramRecipient
from extensions import db
from config import app  # Use the Flask app for application context
from notifications import send_text_message

# Global dictionaries to hold job statuses.
scrape_jobs = {}
stream_creation_jobs = {}
executor = ThreadPoolExecutor(max_workers=5)  # Thread pool for parallel scraping

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

# --- New Scraper Helper Functions ---
def fetch_page_content(url):
    """
    Fetch the HTML content of the provided URL using a standard User-Agent header.
    
    Args:
        url (str): The URL of the webpage to scrape.
    
    Returns:
        str: The HTML content of the webpage.
    
    Raises:
        requests.HTTPError: If the request to the webpage fails.
    """
    import requests
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.93 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

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
# --- End of New Scraper Helper Functions ---

# --- Updated Chaturbate Scraping Function (No AJAX) ---
def scrape_chaturbate_data(url, progress_callback=None):
    """
    Scrape Chaturbate data by fetching the room URL's HTML and extracting the m3u8 URL.
    
    This function extracts the room slug from the provided URL, fetches the page's HTML content,
    then looks for m3u8 URLs in the HTML source.
    
    Args:
        url (str): The full Chaturbate room URL (e.g., "https://chaturbate.com/bunnydollstella/").
        progress_callback (callable, optional): A callback function to update progress.
            It should accept two arguments: a percentage (int) and a message (str).
    
    Returns:
        dict or None: A dictionary with 'streamer_username' and 'chaturbate_m3u8_url'
            keys if successful, or None if an error occurred.
    """
    try:
        if progress_callback:
            progress_callback(10, "Extracting room slug")
        # Extract room slug from the URL
        room_slug = url.rstrip("/").split("/")[-1]
        
        if progress_callback:
            progress_callback(20, "Fetching page content")
        # Fetch the page's HTML content
        html_content = fetch_page_content(url)
        
        if progress_callback:
            progress_callback(50, "Extracting m3u8 URL from page")
        # Extract m3u8 URLs from the HTML
        urls = extract_m3u8_urls(html_content)
        
        if not urls:
            error_msg = "No m3u8 URL found in page content"
            logging.error(error_msg)
            if progress_callback:
                progress_callback(100, f"Error: {error_msg}")
            return None
        
        # Use the first found m3u8 URL
        m3u8_url = urls[0]
        if progress_callback:
            progress_callback(100, "Scraping complete")
        return {
            "streamer_username": room_slug,
            "chaturbate_m3u8_url": m3u8_url,
        }
    except Exception as e:
        logging.error("Error scraping Chaturbate URL %s: %s", url, e)
        if progress_callback:
            progress_callback(100, f"Error: {e}")
        return None

# --- Existing Functions Remain Unchanged ---
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
        import requests
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json().get("0", {}).values()
    except Exception as e:
        logging.error(f"Chat history fetch error: {str(e)}")
        return []

def refresh_chaturbate_stream(room_slug):
    """
    Refresh the m3u8 URL for a Chaturbate stream based on the given room slug.
    This function fetches the room page, extracts the m3u8 URL, and updates the corresponding
    ChaturbateStream in the database.
    
    Args:
        room_slug (str): The room slug (streamer username).
    
    Returns:
        str or None: The new m3u8 URL if successful, or None if an error occurred.
    """
    url = f"https://chaturbate.com/{room_slug}/"
    try:
        html_content = fetch_page_content(url)
    except Exception as e:
        logging.error("Error fetching page content for refresh: %s", e)
        return None
    
    urls = extract_m3u8_urls(html_content)
    if not urls:
        logging.error("No m3u8 URL found during refresh")
        return None
    
    new_url = urls[0]
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
