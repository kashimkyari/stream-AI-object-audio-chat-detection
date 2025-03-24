#!/usr/bin/env python3
import requests
import sys

def fetch_m3u8_url(room_slug):
    # The endpoint for fetching the HLS m3u8 URL.
    url = "https://chaturbate.com/get_edge_hls_url_ajax/"
    
    # Set up headers just as in your original request.
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": f"https://chaturbate.com/{room_slug}/",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://chaturbate.com",
    }
    
    # Form data based on the captured request. Notice that the CSRF token is hard-coded here.
    # In real usage this might need to be updated dynamically.
    data = {
        "room_slug": room_slug,
        "jpeg": "1",
        "csrfmiddlewaretoken": "vfO2sk8hUsSXVILMJwtcyGqhPy6WqwhH"
    }
    
    # Cookies are provided in the original request. The csrftoken must match the form token.
    cookies = {
        "csrftoken": "vfO2sk8hUsSXVILMJwtcyGqhPy6WqwhH"
    }
    
    # Create a session so that cookies are managed properly.
    session = requests.Session()
    session.cookies.update(cookies)
    
    # Send the POST request. We let requests create the proper multipart boundary.
    try:
        response = session.post(url, data=data, headers=headers)
    except Exception as e:
        print("Error during the request:", e)
        sys.exit(1)
    
    # Check for a successful response.
    if response.status_code != 200:
        print("HTTP error:", response.status_code)
        sys.exit(1)
    
    # Parse the JSON response.
    try:
        result = response.json()
    except ValueError:
        print("Failed to decode JSON response")
        sys.exit(1)
    
    # Check if the response indicates success and return the m3u8 URL.
    if result.get("success"):
        return result.get("url")
    else:
        print("Request was not successful:", result)
        return None

def main():
    # Change this room slug to target a different room.
    room_slug = "bliss_emily"
    
    m3u8_url = fetch_m3u8_url(room_slug)
    if m3u8_url:
        print("m3u8 URL fetched:", m3u8_url)
    else:
        print("Failed to fetch m3u8 URL.")

if __name__ == "__main__":
    main()
