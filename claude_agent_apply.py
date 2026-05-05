#!/usr/bin/env python3
"""
LinkedIn Auto Apply - Claude Agent Browser Controller
Launches Chrome with Selenium and exposes helper functions.
"""

import json
import sys
import time
import os
import random
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementClickInterceptedException,
    StaleElementReferenceException, ElementNotInteractableException
)

# ── Paths ──
BASE_DIR = "/Users/nayangadhari/Desktop/Auto_job_applier_linkedIn"
APPLIED_CSV = os.path.join(BASE_DIR, "all excels", "all_applied_applications_history.csv")
FAILED_CSV = os.path.join(BASE_DIR, "all excels", "all_failed_applications_history.csv")
LOG_FILE = os.path.join(BASE_DIR, "logs", "log.txt")
RESUME_PATH = os.path.join(BASE_DIR, "all resumes", "#Resume - Nayan.pdf")

# Ensure directories exist
os.makedirs(os.path.dirname(APPLIED_CSV), exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def random_delay(lo=1.0, hi=3.0):
    time.sleep(random.uniform(lo, hi))


def launch_browser():
    """Launch Chrome with a persistent profile to reuse LinkedIn sessions."""
    opts = Options()
    # Use a dedicated profile directory so cookies persist across runs
    profile_dir = os.path.join(BASE_DIR, "chrome_profile")
    opts.add_argument(f"--user-data-dir={profile_dir}")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    log("Browser launched successfully.")
    return driver


def check_login(driver):
    """Return True if already logged in to LinkedIn."""
    driver.get("https://www.linkedin.com/feed/")
    time.sleep(3)
    url = driver.current_url
    if "/feed" in url:
        log("Already logged in to LinkedIn.")
        return True
    log("Not logged in – on login page.")
    return False


def do_login(driver, email, password):
    """Fill the login form and submit."""
    driver.get("https://www.linkedin.com/login")
    time.sleep(2)
    try:
        email_field = driver.find_element(By.ID, "username")
        email_field.clear()
        email_field.send_keys(email)
        random_delay(0.5, 1.0)

        pw_field = driver.find_element(By.ID, "password")
        pw_field.clear()
        pw_field.send_keys(password)
        random_delay(0.5, 1.0)

        pw_field.send_keys(Keys.RETURN)
        time.sleep(5)

        url = driver.current_url
        if "/feed" in url:
            log("Login successful.")
            return True
        elif "checkpoint" in url or "challenge" in url:
            log("CAPTCHA or 2FA detected – waiting for manual resolution.")
            return "VERIFICATION_NEEDED"
        else:
            log(f"Login may have failed. Current URL: {url}")
            return False
    except Exception as e:
        log(f"Login error: {e}")
        return False


# ── Main: launch and check login ──
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "launch"

    if cmd == "launch":
        driver = launch_browser()
        logged_in = check_login(driver)
        if logged_in:
            print("STATUS:LOGGED_IN")
        else:
            print("STATUS:LOGIN_REQUIRED")
        # Keep browser alive – write PID info
        with open(os.path.join(BASE_DIR, "browser_session.json"), "w") as f:
            json.dump({
                "session_id": driver.session_id,
                "executor_url": driver.command_executor._url,
                "status": "LOGGED_IN" if logged_in else "LOGIN_REQUIRED"
            }, f)
        # Keep process alive
        print("BROWSER_READY")
        sys.stdout.flush()
        # Wait for stdin commands
        for line in sys.stdin:
            line = line.strip()
            if line == "QUIT":
                driver.quit()
                break
            elif line == "CHECK_LOGIN":
                print("LOGGED_IN" if "/feed" in driver.current_url else "NOT_LOGGED_IN")
                sys.stdout.flush()
