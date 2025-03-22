import sys
import types
import tempfile  # For generating unique user-data directories
import os

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
import logging
import uuid
import time
from concurrent.futures import ThreadPoolExecutor
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from flask import jsonify

# Import models and database session for stream creation.
from models import ChaturbateStream, StripchatStream, Assignment
from extensions import db
from config import app  # Use the Flask app for application context

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

def scrape_chaturbate_data(url, progress_callback=None):
    """Scrape Chaturbate data and update progress."""
    try:
        if progress_callback:
            progress_callback(10, "Fetching Chaturbate page")
        chaturbate_m3u8_url = fetch_m3u8_from_page(url)
        if not chaturbate_m3u8_url:
            logging.error("Failed to fetch m3u8 URL for Chaturbate stream.")
            if progress_callback:
                progress_callback(100, "Error: Failed to fetch m3u8 URL")
            return None
        streamer_username = url.rstrip("/").split("/")[-1]
        result = {
            "streamer_username": streamer_username,
            "chaturbate_m3u8_url": chaturbate_m3u8_url,
        }
        logging.info("Scraped details: %s", result)
        if progress_callback:
            progress_callback(100, "Scraping complete")
        return result
    except Exception as e:
        logging.error("Error scraping Chaturbate URL %s: %s", url, e)
        if progress_callback:
            progress_callback(100, f"Error: {e}")
        return None

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
            stream_creation_jobs[job_id]["stream"] = stream.serialize()
        except Exception as e:
            update_stream_job_progress(job_id, 100, f"Error: {str(e)}")
