import requests

# Replace with your API host and credentials if needed.
api_url = "http://0.0.0.0:5000/api/streams"
headers = {
    "Content-Type": "application/json",
    # "Authorization": "Bearer <your_token>"  # if using token authentication
}

response = requests.get(api_url, headers=headers)

if response.status_code == 200:
    streams = response.json()
    for stream in streams:
        # Assuming your serialize() method returns a dict that includes these keys.
        room_url = stream.get("room_url")
        # For Chaturbate and Stripchat streams, your stream object might include additional keys:
        m3u8_url = stream.get("chaturbate_m3u8_url") or stream.get("stripchat_m3u8_url")
        print("Stream Room URL:", room_url)
        print("Stream m3u8 URL:", m3u8_url)
else:
    print("Failed to retrieve streams. Status code:", response.status_code)
