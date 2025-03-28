import requests
from bs4 import BeautifulSoup
import csv
import time

BASE_URL = "https://chaturbate.com"
OUTPUT_FILE = "all_links.csv"
CRAWLED_PAGES = set()  # Track visited pages to avoid loops

def get_all_links(url):
    """
    Recursively crawls Chaturbate pages and extracts all links.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        if url in CRAWLED_PAGES:
            return []
        CRAWLED_PAGES.add(url)

        # Fetch page content
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract all links
        all_links = set()
        for a_tag in soup.find_all("a", href=True):
            link = a_tag["href"]
            if link.startswith("http"):
                full_url = link
            else:
                full_url = BASE_URL + link

            all_links.add(full_url)

        # Find next page (pagination)
        next_page_tag = soup.find("a", {"class": "next"})
        if next_page_tag and "href" in next_page_tag.attrs:
            next_page_url = BASE_URL + next_page_tag["href"]
            print(f"Found next page: {next_page_url}")
            time.sleep(2)  # Prevent rate-limiting
            all_links.update(get_all_links(next_page_url))  # Recursive call

        return all_links

    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

def save_to_csv(links, filename):
    """
    Saves extracted links to a CSV file.
    """
    try:
        with open(filename, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["URL"])
            for link in links:
                writer.writerow([link])
        print(f"Saved {len(links)} links to {filename}")

    except Exception as e:
        print(f"Error writing to CSV: {e}")

# Run recursive crawler
if __name__ == "__main__":
    print("Starting full site crawler...")
    all_links = get_all_links(BASE_URL)
    if all_links:
        save_to_csv(all_links, OUTPUT_FILE)
    else:
        print("No links found.")
