# Gebruik de minimale Python 3.13.1 image
FROM python:3.13.1-slim

ENV PYTHONPATH=/app

# Installeren van de benodigde OS-pakketten
RUN apt-get update && apt-get install -y \
    build-essential \
    libomp-dev \
    python3-dev \
    gcc \
    g++ \
    libssl-dev \
    libffi-dev \
    zlib1g-dev \
    curl \
    wget \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Stel de werkdirectory in
WORKDIR /app

# Kopieer de Python dependencies
COPY requirements.txt .

# Installeer de Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Kopieer de rest van de applicatie
COPY bot/. bot/
COPY models/. models/

# Stel een standaard entrypoint in
ENTRYPOINT ["python", "bot/scalping_bot.py"]