import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import re

logger = logging.getLogger(__name__)

# Connexion à PostgreSQL via variables d'env
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost")
}

def get_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Erreur de connexion à PostgreSQL: {e}")
        raise

def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    asin TEXT UNIQUE,
                    name TEXT,
                    url TEXT UNIQUE
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id SERIAL PRIMARY KEY,
                    product_id INTEGER REFERENCES products(id),
                    price NUMERIC,
                    recorded_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id SERIAL PRIMARY KEY,
                    product_id INTEGER REFERENCES products(id),
                    recorded_at TIMESTAMP DEFAULT NOW()
                );
            """)
            conn.commit()

def extract_asin(url):
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
    return match.group(1) if match else None

def add_product(asin, name, url):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO products (asin, name, url)
                VALUES (%s, %s, %s)
                ON CONFLICT (asin) DO NOTHING;
            """, (asin, name, url))
            conn.commit()
            logger.info(f"Produit ajouté : {asin}")

def add_product_from_url(url, name):
    asin = extract_asin(url)
    if not asin:
        logger.warning(f"ASIN introuvable dans l'URL : {url}")
        return
    add_product(asin, name, url)

def get_product_id(asin):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM products WHERE asin = %s", (asin,))
            result = cur.fetchone()
            return result["id"] if result else None

def add_price(asin, price):
    logger.debug(f"Ajout du prix {price} pour ASIN {asin}")
    product_id = get_product_id(asin)
    if product_id is None:
        logger.warning(f"Produit inconnu pour ASIN: {asin}")
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO price_history (product_id, price)
                VALUES (%s, %s);
            """, (product_id, price))
            conn.commit()
            logger.info(f"Prix {price}€ ajouté pour {asin}")

def add_price_from_url(url, price):
    asin = extract_asin(url)
    if not asin:
        logger.warning(f"ASIN introuvable dans l'URL : {url}")
        return
    add_price(asin, price)

def get_price_history(asin):
    product_id = get_product_id(asin)
    if product_id is None:
        logger.warning(f"Produit inconnu pour ASIN: {asin}")
        return []
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT price, recorded_at FROM price_history
                WHERE product_id = %s
                ORDER BY recorded_at;
            """, (product_id,))
            return cur.fetchall()