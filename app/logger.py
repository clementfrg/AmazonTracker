from datetime import datetime
import logging
import os
from logging.handlers import RotatingFileHandler



# Dossier de logs
log_dir = "/app/logs"
os.makedirs(log_dir, exist_ok=True)

# Nom du fichier log horodaté
log_filename = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Création du logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Handler fichier (avec rotation)
file_handler = RotatingFileHandler(log_filename, maxBytes=10**6, backupCount=3)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

# Handler console
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
logger.addHandler(stream_handler)

# Test log
logger.info("Hello, world! Log en temps réel ET dans fichier.")