import threading
import time
import queue
import requests
from bs4 import BeautifulSoup
import logging
import random
import re
import os
from thread_pool import submit_task

logger = logging.getLogger(__name__)

# Délai entre deux requêtes HTTP (anti-bot)
REQUEST_INTERVAL = 5

# Verrou global pour espacer les requêtes
rate_limit_lock = threading.Lock()

# Liste de User-Agents réalistes pour rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/110.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 Version/15.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Linux; Android 11; Pixel 4) AppleWebKit/537.36 Chrome/114.0.5735.196 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 Version/13.0 Mobile/15E148 Safari/604.1"
]

# Configuration proxy Oxylabs via variables d'environnement
OXYLABS_USERNAME = os.environ.get('OXYLABS_USERNAME', 'USERNAME')
OXYLABS_PASSWORD = os.environ.get('OXYLABS_PASSWORD', 'PASSWORD')
OXYLABS_ENDPOINT_BASE = 'isp.oxylabs.io'
OXYLABS_PORTS = [8001, 8002, 8003, 8004, 8005, 8006, 8007, 8008, 8009, 8010]

# Statistiques globales
stats = {
    "total_requests": 0,
    "detected_blocks": 0
}
stats_lock = threading.Lock()

# File partagée pour toutes les requêtes Web
request_queue = queue.Queue()

def request_worker():
    while True:
        task_id, url, callback, context = request_queue.get()
        try:
            with rate_limit_lock:
                logger.info(f"Requête Web [{task_id}] → {url}")
                headers = {
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept-Language": "fr-FR,fr;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1"
                }

                selected_port = random.choice(OXYLABS_PORTS)
                endpoint = f"{OXYLABS_ENDPOINT_BASE}:{selected_port}"
                proxy_url = f"https://{OXYLABS_USERNAME}:{OXYLABS_PASSWORD}@{endpoint}"
                proxies = {"http": proxy_url, "https": proxy_url}
                logger.debug(f"Proxy utilisé : {proxy_url}")

                response = requests.get(url, headers=headers, timeout=10, proxies=proxies, verify=False)

                with stats_lock:
                    stats["total_requests"] += 1

                if re.search(r"accès automatique aux données d'Amazon", response.text, re.IGNORECASE):
                    logger.warning(f"⚠️ Requête [{task_id}] détectée comme scraping par Amazon.")
                    with stats_lock:
                        stats["detected_blocks"] += 1

                with stats_lock:
                    ratio = (stats["detected_blocks"] / stats["total_requests"] * 100)
                logger.info(f"Statistiques : total={stats['total_requests']}, détectés={stats['detected_blocks']}, ratio={ratio:.2f}%")

                if callback:
                    callback(response, context)

                time.sleep(REQUEST_INTERVAL)
        except Exception as e:
            logger.warning(f"Erreur lors de la requête [{task_id}] : {e}")
        finally:
            request_queue.task_done()

def start_request_dispatcher(thread_count=5):
    for _ in range(thread_count):
        submit_task(request_worker)

def queue_request(task_id, url, callback, context=None):
    request_queue.put((task_id, url, callback, context))
