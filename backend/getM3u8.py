import requests
from bs4 import BeautifulSoup
import re
import concurrent.futures
import logging
import json
from urllib.parse import urljoin, urlparse
import time

class M3U8Scraper:
    def __init__(self, websites, max_workers=5, timeout=10):
        """
        Initialize the M3U8 Scraper
        
        :param websites: List of website URLs to scrape
        :param max_workers: Maximum number of concurrent scraping threads
        :param timeout: Request timeout in seconds
        """
        self.websites = websites
        self.max_workers = max_workers
        self.timeout = timeout
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Regex patterns for M3U8 URL matching
        self.m3u8_patterns = [
            r'https?://[^\s]+\.m3u8',  # Basic m3u8 URL pattern
            r'https?://[^\s]+playlist\.m3u8',  # Playlist specific pattern
            r'https?://[^\s]+stream\.m3u8',  # Stream specific pattern
        ]
        
        # Headers to mimic browser request
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

    def extract_m3u8_from_html(self, html, base_url):
        """
        Extract M3U8 URLs from HTML content
        
        :param html: HTML content to search
        :param base_url: Base URL for resolving relative URLs
        :return: List of extracted M3U8 URLs
        """
        m3u8_urls = []
        
        # Search using regex patterns
        for pattern in self.m3u8_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            m3u8_urls.extend(matches)
        
        # Search in script and source tags
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for URLs in script tags
        for script in soup.find_all('script'):
            script_content = script.string
            if script_content:
                matches = re.findall(r'[\'"]([^\'"]*\.m3u8)[\'"]', script_content)
                for match in matches:
                    m3u8_urls.append(urljoin(base_url, match))
        
        # Look for URLs in source tags
        for source in soup.find_all('source'):
            src = source.get('src', '')
            if src.endswith('.m3u8'):
                m3u8_urls.append(urljoin(base_url, src))
        
        # Remove duplicates and validate URLs
        return list(set(url for url in m3u8_urls if self.is_valid_m3u8_url(url)))

    def is_valid_m3u8_url(self, url):
        """
        Validate M3U8 URL
        
        :param url: URL to validate
        :return: Boolean indicating URL validity
        """
        try:
            parsed = urlparse(url)
            return parsed.scheme in ['http', 'https'] and url.endswith('.m3u8')
        except Exception:
            return False

    def fetch_website(self, url):
        """
        Fetch website content and extract M3U8 URLs
        
        :param url: Website URL to scrape
        :return: Dictionary with scraping results
        """
        result = {
            'url': url,
            'm3u8_urls': [],
            'success': False,
            'error': None
        }
        
        try:
            # Attempt multiple strategies
            strategies = [
                self._direct_fetch,
                self._javascript_render,
                self._headers_check
            ]
            
            for strategy in strategies:
                result['m3u8_urls'] = strategy(url)
                if result['m3u8_urls']:
                    result['success'] = True
                    break
        
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"Error scraping {url}: {e}")
        
        return result

    def _direct_fetch(self, url):
        """
        Direct website content fetch and M3U8 extraction
        
        :param url: Website URL
        :return: List of M3U8 URLs
        """
        try:
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=self.timeout
            )
            response.raise_for_status()
            return self.extract_m3u8_from_html(response.text, url)
        except Exception as e:
            self.logger.warning(f"Direct fetch failed for {url}: {e}")
            return []

    def _javascript_render(self, url):
        """
        Attempt to extract M3U8 URLs with potential JavaScript rendering
        
        :param url: Website URL
        :return: List of M3U8 URLs
        """
        # Placeholder for advanced rendering (e.g., using Selenium)
        # This is a simplified mock implementation
        return []

    def _headers_check(self, url):
        """
        Check headers for direct M3U8 links
        
        :param url: Website URL
        :return: List of M3U8 URLs
        """
        try:
            response = requests.head(
                url, 
                headers=self.headers, 
                timeout=self.timeout,
                allow_redirects=True
            )
            location = response.url
            return [location] if location.endswith('.m3u8') else []
        except Exception as e:
            self.logger.warning(f"Headers check failed for {url}: {e}")
            return []

    def scrape(self):
        """
        Scrape M3U8 URLs from multiple websites concurrently
        
        :return: List of scraping results
        """
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit scraping tasks
            future_to_url = {
                executor.submit(self.fetch_website, url): url 
                for url in self.websites
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_url):
                result = future.result()
                results.append(result)
                
                # Log results
                if result['success']:
                    self.logger.info(f"Found {len(result['m3u8_urls'])} M3U8 URLs for {result['url']}")
                else:
                    self.logger.warning(f"No M3U8 URLs found for {result['url']}")
        
        return results

def main():
    # Example usage
    websites = [
        'https://chaturbate.com/maudcouncil/',
        'https://chaturbate.com/myliss/',
        'https://chaturbate.com/myliss/',
        'https://chaturbate.com/avabrooks/',
        'https://chaturbate.com/annacakes95/',
        'https://chaturbate.com/lexasworld1/'
        # Add more websites here
    ]
    
    scraper = M3U8Scraper(websites)
    results = scraper.scrape()
    
    # Save results to JSON
    with open('m3u8_scraping_results.json', 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    main()