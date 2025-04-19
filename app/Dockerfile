FROM python:3.11-slim

# Dépendances système minimales
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ajout du code
COPY . /app

# Arguments pour secrets (injection à la build)
ARG OXYLABS_USERNAME
ARG OXYLABS_PASSWORD

# Export en variables d'environnement dans le conteneur
ENV OXYLABS_USERNAME=$OXYLABS_USERNAME
ENV OXYLABS_PASSWORD=$OXYLABS_PASSWORD

# Dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
