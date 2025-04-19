import queue
from bs4 import BeautifulSoup
from request_managment import queue_request
from postrgres_utils import add_product_from_url, get_connection
from thread_pool import submit_task
import logging
import re
import time

logger = logging.getLogger(__name__)

# Liste de pages à scanner (peut être enrichie dynamiquement)
START_PAGES = [
    "https://www.amazon.fr/s?k=rtx+4080",
    "https://www.amazon.fr/s?k=ssd+2to",
    "https://www.amazon.fr/s?k=raspberry+pi+5",
    "https://www.amazon.fr/s?k=processeur&i=computers&crid=298MBH6E01Q9L&sprefix=processeur%2Ccomputers%2C148&ref=nb_sb_ss_ts-doa-p_1_10",
    "https://www.amazon.fr/MORDEER-Chaises-Cuisine-A%C3%A9rodynamique-Lamelles/dp/B0D2RFHRRQ/ref=sr_1_1_sspa?crid=TKM2EGGDVTPI&dib=eyJ2IjoiMSJ9.Jm8I94KmKCN1ZLSYMBugeX-MybHMcKXveSPfJomn3pAS-qnql20hxbIC89Ra0TE4UNleAm4MFDtsM56_cSm1DssdOEcSjaeQfS_c5r8aRdRJDquzN9_Oy8vEw_tpj5KYwzOFBiijsqZv4tBtHT-jFOWSOlYgvdpX07iQpJSw6S69dUal-dChJpbCJZKBee_dvHeVmdHH4vcpBX-moj2ez_6XozC_iGMzXtpKcfXIQZr8UV8R4L4WaeTTlKBAsEK2y0k5o16lIh8KcD6J32vXkJVGk1PE3flS6mfaUxxLeR8.FzSQyu0SzMO7gPvbK7FGJQL7OTDj2T2gv3u3-UIjfkk&dib_tag=se&keywords=chaise%2Bhaute%2Bbois&qid=1745017148&sprefix=chaie%2Caps%2C155&sr=8-1-spons&sp_csd=d2lkZ2V0TmFtZT1zcF9hdGY&th=1"
]

# Nombre de threads logiques (tâches)
DISCOVERY_THREADS = 3

discovery_queue = queue.Queue()

def url_already_known(url):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM products WHERE url = %s LIMIT 1", (url,))
            return cur.fetchone() is not None

def get_all_product_urls():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT url FROM products")
            return [row[0] for row in cur.fetchall() if row[0]]

def handle_listing_response(response, context):
    soup = BeautifulSoup(response.text, "html.parser")
    asins = set()

    for div in soup.find_all("div", attrs={"data-asin": True}):
        asin = div["data-asin"].strip()
        if asin:
            title_elem = div.find("div", id=re.compile(r"ProductTitle-"))
            name = title_elem.text.strip() if title_elem else "Produit Amazon"
            url = f"https://www.amazon.fr/dp/{asin}"
            asins.add((asin, url, name))

    logger.info(f"{len(asins)} produits trouvés sur {context['source']}")

    for asin, url, name in asins:
        if url_already_known(url):
            logger.debug(f"Déjà présent : {url}")
            continue
        try:
            add_product_from_url(url, name)
            logger.info(f"Ajouté : {url} ({name})")
            discovery_queue.put(url)
        except Exception as e:
            logger.warning(f"Erreur ajout produit {url} : {e}")

def worker():
    while True:
        logger.info("Taill de la file de découverte : %d", discovery_queue.qsize())

        try:
            url = discovery_queue.get(timeout=30)
        except queue.Empty:
            logger.info("File vide. Ajout des URLs depuis la base de données.")
            for url in get_all_product_urls():
                discovery_queue.put(url)
            continue

        if not url_already_known(url):
            queue_request(task_id=f"discover:{url}", url=url, callback=handle_listing_response, context={"source": url})
        discovery_queue.task_done()

def start_product_discovery():
    for _ in range(DISCOVERY_THREADS):
        submit_task(worker)

    for page_url in START_PAGES:
        if not url_already_known(page_url):
            discovery_queue.put(page_url)