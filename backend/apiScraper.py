import re
import base64
import json

def extract_access_token(request_text):
    """
    Extract the access token from a HTTP request
    
    :param request_text: Full HTTP request text
    :return: Extracted access token
    """
    # Find access token in the URL query parameters
    token_match = re.search(r'access_token=([^&\s]+)', request_text)
    
    if token_match:
        access_token = token_match.group(1)
        
        # Optional: Decode JWT to inspect payload
        try:
            # Split JWT into parts
            jwt_parts = access_token.split('.')
            
            # Base64 decode the payload (second part)
            if len(jwt_parts) >= 2:
                payload_json = base64.urlsafe_b64decode(jwt_parts[1] + '==').decode('utf-8')
                payload = json.loads(payload_json)
                
                print("JWT Payload Details:")
                print(json.dumps(payload, indent=2))
        except Exception as e:
            print(f"Error decoding JWT: {e}")
        
        return access_token
    
    return None

def main():
    # Paste the full HTTP request here
    request_text = '''GET /comet/e91GimaiQBnNX6!oL-k6syl0pAQsZdpKmRPOq-9b86d/recv?access_token=eyJhbGciOiJIUzI1NiIsImtpZCI6IktTS3cyZy5MMzZJU2ciLCJ0eXAiOiJKV1QifQ.eyJpYXQiOjE3NDMwOTk3OTgsImV4cCI6MTc0MzE4NjE5OC4wLCJ4LWFibHktY2FwYWJpbGl0eSI6IntcInVzZXI6Z3JvdXBlZDozVzdXUVpWXCI6IFtcInN1YnNjcmliZVwiXX0iLCJ4LWFibHktY2xpZW50SWQiOiIramFjbTgxOGwwZ2wtM1c3V1FaViJ9.x0jm3ydrj7HQ67zqxblHOZLG5QNmnY-qKobBMraMvrw&rnd=9529109463573832 HTTP/2
Host: realtime.pa.highwebmedia.com
User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0
Accept: application/json
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate, br, zstd
Referer: https://chaturbate.com/
Origin: https://chaturbate.com
Connection: keep-alive
Sec-Fetch-Dest: empty
Sec-Fetch-Mode: cors
Sec-Fetch-Site: cross-site
TE: trailers'''
    
    # Extract and print access token
    access_token = extract_access_token(request_text)
    
    if access_token:
        print("\nExtracted Access Token:")
        print(access_token)
    else:
        print("No access token found")

if __name__ == '__main__':
    main()