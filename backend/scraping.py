import sys
import types
import tempfile  # New import for generating unique user-data directories
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

# Global dictionary to hold scraping job statuses.
scrape_jobs = {}
executor = ThreadPoolExecutor(max_workers=5)  # Thread pool for parallel scraping

def update_job_progress(job_id, percent, message):
    """Update the progress of a scraping job."""
    scrape_jobs[job_id] = {
        "progress": percent,
        "message": message,
    }
    logging.info("Job %s progress: %s%% - %s", job_id, percent, message)


def fetch_m3u8_from_page(url, timeout=90):
    """Fetch M3U8 URL with retry fallback mechanisms"""
    # Define configuration attempts (primary and fallback)
    configs = [
        {  # Primary configuration (headless)
            "headless": True,
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "extra_args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars"
            ]
        },
        {  # Fallback configuration (non-headless with different UA)
            "headless": False,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "extra_args": [
                "--window-size=1920,1080",
                "--start-maximized",
                "--disable-web-security"
            ]
        }
    ]

    for attempt, config in enumerate(configs, 1):
        logging.info(f"Attempt {attempt} with config: {config}")
        chrome_options = Options()
        
        if config["headless"]:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument(f"user-agent={config['user_agent']}")
        
        for arg in config["extra_args"]:
            chrome_options.add_argument(arg)

        unique_user_data_dir = tempfile.mkdtemp()
        chrome_options.add_argument(f"--user-data-dir={unique_user_data_dir}")

        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.scopes = ['.*\\.m3u8']
            
            logging.info(f"Loading page (Attempt {attempt})")
            driver.get(url)
            
            # Increased initial load time
            time.sleep(8 if attempt == 1 else 15)
            
            found_url = None
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                for request in driver.requests:
                    if request.response and ".m3u8" in request.url:
                        found_url = request.url
                        logging.info(f"M3U8 found in attempt {attempt}")
                        return found_url
                time.sleep(2)
            
            logging.warning(f"Attempt {attempt} timed out")
        
        except Exception as e:
            logging.error(f"Attempt {attempt} failed: {str(e)}")
        
        finally:
            try:
                driver.quit()
            except Exception as e:
                logging.error(f"Error closing driver: {str(e)}")

    logging.error("All scraping attempts failed")
    return None

def scrape_chaturbate_data(url, progress_callback=None):
    """Enhanced with fallback scraping"""
    try:
        if progress_callback:
            progress_callback(10, "Initial scraping attempt")
        
        # First try direct API call
        try:
            api_url = f"https://chaturbate.com/api/chatvideocontext/{url.split('/')[-2]}/"
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'hls_url' in data:
                    return {
                        "streamer_username": url.rstrip("/").split("/")[-1],
                        "chaturbate_m3u8_url": data['hls_url']
                    }
        except Exception as api_error:
            logging.info("API method failed, falling back to Selenium")

        # If API method fails, use Selenium with retries
        chaturbate_m3u8_url = fetch_m3u8_from_page(url)
        
        if not chaturbate_m3u8_url:
            raise ValueError("Failed to fetch m3u8 URL after multiple attempts")
        
        return {
            "streamer_username": url.rstrip("/").split("/")[-1],
            "chaturbate_m3u8_url": chaturbate_m3u8_url
        }

    except Exception as e:
        logging.error(f"Final scraping error: {str(e)}")
        if progress_callback:
            progress_callback(100, f"Error: {str(e)}")
        return None

def scrape_stripchat_data(url, progress_callback=None):
    """Enhanced with multiple fallback strategies"""
    try:
        if progress_callback:
            progress_callback(10, "Initial scraping attempt")
        
        # First try direct m3u8 pattern match
        try:
            response = requests.get(url, timeout=10)
            match = re.search(r'(https://[\w./-]+\.m3u8)', response.text)
            if match:
                return {
                    "streamer_username": url.rstrip("/").split("/")[-1],
                    "stripchat_m3u8_url": match.group(1)
                }
        except Exception as direct_error:
            logging.info("Direct method failed, falling back to Selenium")

        # If direct method fails, use Selenium with retries
        stripchat_m3u8_url = fetch_m3u8_from_page(url)
        
        if not stripchat_m3u8_url:
            raise ValueError("Failed to fetch m3u8 URL after multiple attempts")
        
        if "playlistType=lowLatency" in stripchat_m3u8_url:
            stripchat_m3u8_url = stripchat_m3u8_url.split('?')[0]

        return {
            "streamer_username": url.rstrip("/").split("/")[-1],
            "stripchat_m3u8_url": stripchat_m3u8_url
        }

    except Exception as e:
        logging.error(f"Final scraping error: {str(e)}")
        if progress_callback:
            progress_callback(100, f"Error: {str(e)}")
        return None

def run_scrape_job(job_id, url):
    """Run a scraping job and update progress."""
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


def run_stream_creation_job(job_id, room_url, platform):
    # Create application context
    with app.app_context():
        try:
            stream_creation_jobs[job_id].update({"progress": 10, "message": "Scraping data..."})
            
            # Scrape data
            if platform == "chaturbate":
                scraped_data = scrape_chaturbate_data(room_url)
            else:
                scraped_data = scrape_stripchat_data(room_url)
            
            if not scraped_data:
                stream_creation_jobs[job_id].update({
                    "progress": 100,
                    "message": "Scraping failed",
                    "status": "error"
                })
                return

            stream_creation_jobs[job_id].update({"progress": 50, "message": "Creating stream..."})
            
            # Create stream object
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
            
            stream_creation_jobs[job_id].update({
                "progress": 100,
                "message": "Stream created",
                "status": "completed",
                "stream": stream.serialize()
            })

        except Exception as e:
            stream_creation_jobs[job_id].update({
                "progress": 100,
                "message": f"Error: {str(e)}",
                "status": "error"
            })