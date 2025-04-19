from datetime import datetime
import logging
import os
import time
from postrgres_utils import *
from check_price import *
from request_managment import start_request_dispatcher
from product_discovery import start_product_discovery
from thread_pool import init_thread_pool
from price_alert import start_price_alerts

# === Configuration ===
THREAD_POOL_SIZE = 30

# === Initialisation du logging ===
os.makedirs("/app/logs", exist_ok=True)
log_filename = os.path.join("/app/logs", f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Création du logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Handler fichier
file_handler = logging.FileHandler(log_filename)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

# Handler console
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
logger.addHandler(stream_handler)

# === Initialisation de la base et du système de suivi ===
def initialize():
    logger.info("Initialisation de la base de données...")
    init_db()

    logger.info(f"Initialisation du pool de threads global ({THREAD_POOL_SIZE})...")
    init_thread_pool(max_workers=THREAD_POOL_SIZE)

    logger.info("Démarrage du gestionnaire de requêtes web...")
    start_request_dispatcher()

    logger.info("Démarrage de la découverte automatique de produits...")
    start_product_discovery()

    logger.info("Ajout de données de test...")
    add_product_from_url("https://www.amazon.fr/dp/B07PGL2ZSL", "Raspberry Pi 4")
    add_product_from_url("https://www.amazon.fr/dp/B0000C1ZNV", "Clé USB 64Go")

    logger.info("Lancement du suivi des prix...")
    start_price_updater()

    logger.info("Lancement du système d'alertes de prix...")
    start_price_alerts()

# === Boucle principale (peut contenir autre logique métier) ===
def main_loop():
    while True:
        logger.info("Le programme tourne...")
        time.sleep(300)

if __name__ == "__main__":
    initialize()
    main_loop()
