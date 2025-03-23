import requests
import re
import logging

def fetch_page_content(url, extra_headers=None):
    """
    Fetch the HTML content of the provided URL using a standard User-Agent header.
    
    Args:
        url (str): The URL of the webpage to scrape.
        extra_headers (dict, optional): Additional headers to include in the request.
    
    Returns:
        str: The HTML content of the webpage.
    
    Raises:
        requests.HTTPError: If the request to the webpage fails.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.93 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    if extra_headers:
        headers.update(extra_headers)
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

def scrape_stripchat_data(url, progress_callback=None):
    """
    Scrape Stripchat data and update progress using the new scraper routines.
    
    This function fetches the page content from the given Stripchat URL using a traditional
    HTTP request with additional headers, extracts the first found m3u8 URL from the HTML content
    via regex, and returns the streamer's username along with the m3u8 URL. It also handles
    removing any low latency query parameters from the m3u8 URL.
    
    Args:
        url (str): The Stripchat page URL to scrape.
        progress_callback (callable, optional): A callback function to update progress.
            It should accept two arguments: a percentage (int) and a message (str).
    
    Returns:
        dict or None: A dictionary with 'streamer_username' and 'stripchat_m3u8_url'
            keys if successful, or None if an error occurred.
    """
    try:
        if progress_callback:
            progress_callback(10, "Fetching Stripchat page")
        
        # Add extra headers to avoid 406 errors
        extra_headers = {
            "Referer": "https://stripchat.com/"
        }
        html_content = fetch_page_content(url, extra_headers=extra_headers)
        m3u8_urls = extract_m3u8_urls(html_content)
        if not m3u8_urls:
            logging.error("Failed to fetch m3u8 URL for Stripchat stream.")
            if progress_callback:
                progress_callback(100, "Error: Failed to fetch m3u8 URL")
            return None
        
        # Use the first found m3u8 URL
        stripchat_m3u8_url = m3u8_urls[0]
        
        # Remove any low latency parameters if present
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

# Example usage:
if __name__ == "__main__":
    def progress_update(percent, message):
        print(f"{percent}% - {message}")
    
    test_url = "https://stripchat.com/donna_creamteam"
    result = scrape_stripchat_data(test_url, progress_callback=progress_update)
    if result:
        print("Scraping successful:")
        print(result)
    else:
        print("Scraping failed.")
