#!/usr/bin/env python3
"""
chaturbate_scraper.py

Usage:
    python chaturbate_scraper.py https://chaturbate.com/roomslug/

This script sends a POST request to Chaturbate's endpoint to retrieve the HLS URL
for a given room using free proxies to mask the source IP.
"""

import sys
import logging
import requests
import random
import time
from requests.exceptions import RequestException
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def get_random_proxy() -> dict:
    """
    Select a random proxy from the proxy list.

    Returns:
        dict: A dictionary with HTTP and HTTPS proxies formatted for requests.
    """
    proxy = random.choice(PROXY_LIST)
    # Format proxy for both http and https protocols
    return {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}"
    }

def get_hls_url(room_slug: str, max_attempts: int = 5) -> dict:
    """
    Sends a POST request to Chaturbate's endpoint to fetch the HLS URL for a given room.
    Tries multiple proxies from the free proxy list if necessary.

    Args:
        room_slug (str): The room slug to query.
        max_attempts (int): Maximum number of attempts with different proxies.

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

    attempts = 0
    while attempts < max_attempts:
        proxy_dict = get_random_proxy()
        try:
            logging.info(f"Attempt {attempts+1}: Using proxy {proxy_dict['http']}")
            # Send the POST request with the encoded payload using a random proxy.
            response = requests.post(
                url,
                headers=headers,
                data=payload.encode('utf-8'),
                proxies=proxy_dict,
                timeout=10  # Timeout in seconds for the request.
            )
            response.raise_for_status()  # Raise an error for bad status codes.
            logging.info("Request successful.")
            # Parse and return the JSON response.
            return response.json()
        except RequestException as e:
            logging.error(f"Request failed with proxy {proxy_dict['http']}: {e}")
            attempts += 1
            time.sleep(1)  # Pause briefly before retrying.
        except ValueError as e:
            logging.error(f"JSON decoding failed: {e}")
            return None

    logging.error("Exceeded maximum attempts with proxies.")
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
