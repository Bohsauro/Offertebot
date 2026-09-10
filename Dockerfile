FROM python:3.11-slim

# Evita la scrittura di file .pyc e abilita log non bufferizzati
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Rome

WORKDIR /app

# Installazione dipendenze di sistema minime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Installazione dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia del codice sorgente
COPY . .

# Creazione cartella per database persistente
RUN mkdir -p /app/data

VOLUME ["/app/data"]

CMD ["python", "main.py"]
