"""Headless-Chrome helpers.

Chrome is only needed for two things:
  1. discovering the showtimes API request (URL + subscription key) that
     cineplex.com makes, by reading Chrome's network performance log;
  2. fetching the API from inside the page as a fallback when plain
     `requests` calls get blocked (401/403).

Everything else runs over plain HTTP.
"""

import json
import logging
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from utils.cineplex_api import API_HOST


def build_driver():
    options = webdriver.ChromeOptions()
    for arg in (
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1440,900",
    ):
        options.add_argument(arg)
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin:
        options.binary_location = chrome_bin
    driver_bin = os.environ.get("CHROMEDRIVER_BIN")
    service = Service(driver_bin) if driver_bin else Service()

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(90)
    driver.set_script_timeout(60)
    return driver


def _drain_api_requests(driver, seen):
    """Pull new requests to apis.cineplex.com out of the performance log."""
    for entry in driver.get_log("performance"):
        try:
            message = json.loads(entry["message"])["message"]
        except (KeyError, ValueError):
            continue
        if message.get("method") != "Network.requestWillBeSent":
            continue
        request = message.get("params", {}).get("request", {})
        url = request.get("url", "")
        if API_HOST in url and url not in seen:
            seen[url] = request.get("headers", {})


def discover_api_config(page_urls, wait_seconds=45):
    """Load Cineplex pages and capture the showtimes API call they make.

    Returns {"url": ..., "headers": ...} for the first request whose URL
    looks like a showtimes query (mentions both a location and a date), or
    None if nothing matching was seen.
    """
    driver = build_driver()
    try:
        captured = {}
        for page_url in [u for u in page_urls if u]:
            logging.info("Discovery: loading %s", page_url)
            try:
                driver.get(page_url)
            except Exception as e:
                logging.warning("Discovery: failed to load %s: %s", page_url, e)
                continue
            deadline = time.time() + wait_seconds
            while time.time() < deadline:
                _drain_api_requests(driver, captured)
                for url, headers in captured.items():
                    low = url.lower()
                    if "showtime" in low and "location" in low and "date" in low:
                        return {"url": url, "headers": headers}
                time.sleep(2)
        if captured:
            logging.warning(
                "Discovery: saw %d apis.cineplex.com request(s) but none "
                "looked like a showtimes query: %s",
                len(captured), list(captured)[:5],
            )
        return None
    finally:
        driver.quit()


_FETCH_JS = """
const url = arguments[0];
const headers = arguments[1];
const done = arguments[arguments.length - 1];
fetch(url, {headers: headers, credentials: 'omit'})
  .then(r => r.text().then(t => done(JSON.stringify({status: r.status, body: t}))))
  .catch(e => done(JSON.stringify({status: 0, body: String(e)})));
"""


def browser_fetch_json(driver, url, headers):
    """Fetch an API URL from inside a cineplex.com page (passes Cloudflare)."""
    raw = driver.execute_async_script(_FETCH_JS, url, headers)
    result = json.loads(raw)
    if result["status"] == 404:
        return []
    if result["status"] != 200:
        raise RuntimeError(
            f"in-browser fetch of {url} failed with status {result['status']}"
        )
    return json.loads(result["body"])
