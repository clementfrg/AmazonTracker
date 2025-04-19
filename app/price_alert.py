import logging
import time
import requests  # Ajout manquant
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from postrgres_utils import get_connection
from thread_pool import submit_task
from request_managment import queue_request

logger = logging.getLogger(__name__)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1363039224571498646/ylmxjGRnpnjIDjUuDVNk1q1g-CYPtooedLa3iGGJnUSoy-O7F1-qomFSsv7F453l-hV4"
CHECK_INTERVAL = 600  # 10 minutes
DROP_THRESHOLD = 0.20  # 20% de baisse
ALERT_COOLDOWN_HOURS = 24

def fetch_price_history():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.name, p.url, ph.price, ph.recorded_at, p.id
                FROM products p
                JOIN (
                    SELECT product_id, MAX(recorded_at) as last_time
                    FROM price_history
                    GROUP BY product_id
                ) latest ON latest.product_id = p.id
                JOIN price_history ph ON ph.product_id = p.id AND ph.recorded_at = latest.last_time
            """)
            return cur.fetchall()

def fetch_average_price_excluding_latest(product_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT AVG(price)
                FROM price_history
                WHERE product_id = %s AND recorded_at < (
                    SELECT MAX(recorded_at) FROM price_history WHERE product_id = %s
                )
            """, (product_id, product_id))
            result = cur.fetchone()
            return result[0] if result and result[0] else None

def already_alerted_recently(product_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT MAX(recorded_at)
                FROM price_alerts
                WHERE product_id = %s
            """, (product_id,))
            result = cur.fetchone()
            if result and result[0]:
                last_alert_time = result[0]
                return (datetime.utcnow() - last_alert_time) < timedelta(hours=ALERT_COOLDOWN_HOURS)
            return False

def log_alert(product_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO price_alerts (product_id, recorded_at) VALUES (%s, NOW())", (product_id,))
            conn.commit()

def handle_product_info_response(response, context):
    #logger.info("Received product info response" + response.text)
    url = context["url"]
    current = context["current"]
    average = context["average"]
    product_id = context["product_id"]
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find("span", id="productTitle")
        img_tag = soup.find("img", {"id": "landingImage"})
        name = title.text.strip() if title else "Produit Amazon"
        image_url = img_tag['src'] if img_tag else None

        embed = {
            "title": name,
            "url": url,
            "description": f"🔻 **Baisse de prix détectée !**",
            "fields": [
                {"name": "Prix moyen précédent", "value": f"{average:.2f} €", "inline": True},
                {"name": "Nouveau prix", "value": f"{current:.2f} €", "inline": True}
            ],
            "color": 15258703
        }
        if image_url:
            embed["thumbnail"] = {"url": image_url}

        payload = {"embeds": [embed]}
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if resp.status_code in [200, 204]:
            logger.info(f"Message envoyé pour {name}")
            log_alert(product_id)
        else:
            logger.warning(f"Erreur envoi Discord : {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.warning(f"Erreur d'extraction d'information produit : {e}")

def check_price_drops():
    logger.info("Vérification des baisses de prix...")
    rows = fetch_price_history()
    for _, url, current_price, _, product_id in rows:
        average_price = fetch_average_price_excluding_latest(product_id)
        if not average_price or current_price >= average_price:
            continue
        drop_ratio = (average_price - current_price) / average_price
        if drop_ratio >= DROP_THRESHOLD:
            if not already_alerted_recently(product_id):
                queue_request(
                    task_id=f"alert:{product_id}",
                    url=url,
                    callback=handle_product_info_response,
                    context={
                        "url": url,
                        "current": current_price,
                        "average": average_price,
                        "product_id": product_id
                    }
                )
            else:
                logger.info(f"Alerte déjà envoyée récemment pour produit {product_id}, ignorée.")

def start_price_alerts():
    def loop():
        while True:
            try:
                check_price_drops()
            except Exception as e:
                logger.warning(f"Erreur alerte prix : {e}")
            time.sleep(CHECK_INTERVAL)

    submit_task(loop)
