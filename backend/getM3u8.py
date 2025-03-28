#!/usr/bin/env python3
"""
chaturbate_scraper.py

Usage:
    python chaturbate_scraper.py https://chaturbate.com/roomslug/

This script sends a POST request to Chaturbate's endpoint to retrieve the HLS URL
for a given room. The room slug is extracted from the provided URL.
"""

import sys
import logging
import requests
from requests.exceptions import RequestException
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    # The room slug should be the first element in the path (ignoring empty strings)
    path_parts = [part for part in parsed_url.path.split('/') if part]
    if not path_parts:
        raise ValueError("No room slug found in the URL.")
    return path_parts[0]

def get_hls_url(room_slug: str) -> dict:
    """
    Sends a POST request to Chaturbate endpoint to fetch the HLS URL for a given room.
    
    Args:
        room_slug (str): The room slug to query.
    
    Returns:
        dict: JSON response from the endpoint if successful.
        None: If an error occurs during the request.
    """
    url = 'https://chaturbate.com/get_edge_hls_url_ajax/'
    
    # Define headers exactly as specified
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
        # Boundary value must not include prefixed dashes in header.
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
            'cf_clearance=tnF75pLB8eFZEUikS5OPTINkrhEvcomnt9vfKMw5JNM-1743187276-1.2.1.1-QLV90oVctAggVWp8bskoOTIPaVnL04Rql8gM4AtI7_nBBGibb6TaAzXUIZzQaDjh_mZGIi2uZujUSW5xBbONM4LY_imBh.ASxLCrtAwtlb17Cy6V.rotlanU1LlX9UFG6Yf_QS4yagcjpfYoPHnvM9.tOtwfZw655j4TcWXMPb2qj_5NCgKKiUZx77DhLmN4gV4QziW1Ud0QIzMTFgyvb8F0WCXpYsW5fd7TfVoXD3pcDATTZXcV1VDLeIjHqMNw7lOJkeE0AH2sGnVzhdOi3Lb.OEDhZdp0tr3EgqKLdhA7Cz0if26VPFdylei2Q1OS7MYEjdQhEUIIU6_EnGxry..IKM4cUvPVEO8VqB64z1Y; '
            'stcki="Eg6Gdq=1"; '
            f'tbu_{room_slug}={{"source":"df","index":4,"source_filter":"{{}}","room_list_id":"5ed8234b-4ce5-4a52-9699-86ab9105b907"}}; '
            'language_subdomain_continuity=1'
        )
    }
    
    # Define the boundary string (without prefixed dashes).
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
    
    try:
        # Send the POST request with the encoded payload.
        response = requests.post(url, headers=headers, data=payload.encode('utf-8'))
        response.raise_for_status()  # Raise error for bad status codes.
        logging.info("Request successful.")
        
        # Parse and return JSON response.
        return response.json()
    except RequestException as e:
        logging.error(f"Request failed: {e}")
        return None
    except ValueError as e:
        logging.error(f"JSON decoding failed: {e}")
        return None

def main():
    """
    Main entry point for the script. Expects a URL as a command-line argument.
    """
    if len(sys.argv) != 2:
        print("Usage: python chaturbate_scraper.py https://chaturbate.com/roomslug/")
        sys.exit(1)
    
    input_url = sys.argv[1]
    
    try:
        room_slug = extract_room_slug(input_url)
        logging.info(f"Extracted room slug: {room_slug}")
    except ValueError as e:
        logging.error(f"Error extracting room slug: {e}")
        sys.exit(1)
    
    result = get_hls_url(room_slug)
    if result:
        print("HLS URL Response:")
        print(result)
    else:
        print("Failed to fetch HLS URL.")

if __name__ == '__main__':
    main()
