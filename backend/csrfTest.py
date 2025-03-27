#!/usr/bin/env python3
"""
Robust Recursive Selenium Script: Retrieve CSRF Token and Attempt Dummy Login on Chaturbate

This script:
- Opens Chaturbate's login page in a headless Chrome session.
- Uses a recursive helper function to repeatedly try to fetch the CSRF token.
- Similarly attempts to retrieve the username, password fields, and login button.
- Performs a dummy login attempt (with dummy credentials).
- Retries fetching elements if they aren’t found, up to a maximum recursion depth.
"""

import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Maximum recursive attempts
MAX_ATTEMPTS = 5

def recursive_find_element(driver, by, value, attempt=1):
    """
    Recursively attempts to find an element.
    If not found, waits a few seconds, refreshes, and tries again until MAX_ATTEMPTS.
    """
    try:
        wait = WebDriverWait(driver, 5)
        element = wait.until(EC.presence_of_element_located((by, value)))
        return element
    except TimeoutException:
        if attempt < MAX_ATTEMPTS:
            print(f"[!] Attempt {attempt} to locate element ({by}='{value}') failed. Retrying...")
            time.sleep(2)
            driver.refresh()
            return recursive_find_element(driver, by, value, attempt + 1)
        else:
            print(f"[X] Failed to locate element ({by}='{value}') after {MAX_ATTEMPTS} attempts.")
            sys.exit(1)

def main():
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run headless
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Initialize Chrome WebDriver
    driver = webdriver.Chrome(options=chrome_options)

    try:
        login_url = "https://chaturbate.com/auth/login/"
        driver.get(login_url)
        print("[*] Navigated to login page.")

        # Recursively fetch the CSRF token
        csrf_element = recursive_find_element(driver, By.XPATH, "//input[@name='csrfmiddlewaretoken']")
        csrf_token = csrf_element.get_attribute("value")
        print(f"[+] CSRF Token: {csrf_token}")

        # Recursively fetch username field, password field, and login button
        username_field = recursive_find_element(driver, By.NAME, "username")
        password_field = recursive_find_element(driver, By.NAME, "password")
        login_button = recursive_find_element(driver, By.XPATH, "//button[@type='submit']")

        # Fill in dummy credentials
        dummy_username = "journalistafraid"
        dummy_password = '4adPwNBq,g"}+x3'
        username_field.send_keys(dummy_username)
        password_field.send_keys(dummy_password)
        print("[*] Filled in dummy credentials.")

        # Click login
        login_button.click()
        print("[*] Submitted login form.")

        # Wait for response and check for success or failure
        time.sleep(5)
        page_source = driver.page_source.lower()
        if "logout" in page_source:
            print("[+] Login successful!")
        else:
            print("[-] Login failed as expected with dummy credentials.")

        # Debug: print session cookies
        cookies = driver.get_cookies()
        print("[*] Session Cookies:")
        for cookie in cookies:
            print(f"    {cookie['name']}: {cookie['value']}")

    except Exception as e:
        print(f"[X] Error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
