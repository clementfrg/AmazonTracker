import threading
import time
import queue
import os
from bs4 import BeautifulSoup
from postrgres_utils import *
import logging
import re
from request_managment import queue_request
from thread_pool import submit_task

logger = logging.getLogger(__name__)

# Nombre maximal de threads logiques
MAX_THREADS = 1

# Queue des produits à vérifier
product_queue = queue.Queue()

# Délai entre deux checks d’un même produit (1 heure en secondes)
CHECK_INTERVAL = 3600

# Flag pour arrêter le thread (si besoin dans le futur)
stop_flag = threading.Event()

def fetch_all_products():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT asin, url FROM products")
            return cur.fetchall()

def get_last_recorded_time(asin):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT recorded_at FROM price_history
                WHERE product_id = (SELECT id FROM products WHERE asin = %s)
                ORDER BY recorded_at DESC
                LIMIT 1
            """, (asin,))
            result = cur.fetchone()
            return result[0].timestamp() if result else None

def parse_price_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')

    main_price_container = soup.find(id="socialProofingAsinFaceout_feature_div")
    if not main_price_container:
        return None

    price_whole_tag = main_price_container.select_one(".a-price-whole")
    price_decimal_tag = main_price_container.select_one(".a-price-fraction")

    if not price_whole_tag or not price_decimal_tag:
        return None

    price_whole = re.search(r'(\d+)', price_whole_tag.text)
    price_decimal = re.search(r'(\d+)', price_decimal_tag.text)

    if not price_whole or not price_decimal:
        return None

    price_str = f"{price_whole.group(1)}.{price_decimal.group(1)}"
    return float(price_str)

def handle_price_response(response, context):
    asin = context["asin"]
    result_queue = context["result_queue"]
    try:
        price = parse_price_from_html(response.text)
        result_queue.put((asin, price))
    except Exception as e:
        logger.warning(f"Erreur de parsing HTML pour {asin}: {e}")
        result_queue.put((asin, None))

def worker():
    while not stop_flag.is_set():
        asin, url = product_queue.get()
        try:
            last_time = get_last_recorded_time(asin)
            now = time.time()
            if last_time and now - last_time < CHECK_INTERVAL:
                logger.info(f"{asin} déjà vérifié récemment (via DB), ignoré.")
                continue

            logger.info(f"Scraping prix pour {asin}")
            result_queue = queue.Queue()
            queue_request(
                task_id=asin,
                url=url,
                callback=handle_price_response,
                context={"asin": asin, "result_queue": result_queue}
            )
            asin_result, price = result_queue.get()

            if price is not None:
                add_price(asin, price)
                logger.debug(f"Prix trouvé : {price} pour asin : {asin}")
            else:
                logger.warning(f"Prix introuvable pour {asin}")

        finally:
            product_queue.task_done()

def start_price_updater():
    os.makedirs("/app/logs", exist_ok=True)
    logging.basicConfig(
        filename="/app/logs/updater.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    def loop():
        for _ in range(MAX_THREADS):
            submit_task(worker)

        while not stop_flag.is_set():
            products = fetch_all_products()
            for asin, url in products:
                product_queue.put((asin, url))
            logger.info("Cycle terminé. En attente du prochain scan...")
            product_queue.join()
            time.sleep(60)

    submit_task(loop)