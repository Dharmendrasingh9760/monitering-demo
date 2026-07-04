"""Continuously calls the sample app so Prometheus has live data to scrape."""
import time
import random
import requests

APP_URL = "http://app:5000"
ENDPOINTS = ["/api/orders", "/api/payments", "/api/inventory"]

while True:
    ep = random.choice(ENDPOINTS)
    try:
        requests.get(APP_URL + ep, timeout=2)
    except Exception as e:
        print("load generator error:", e)
    time.sleep(random.uniform(0.1, 0.5))
