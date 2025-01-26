# Gebruik een lichte Python-image als basis
FROM python:3.9-slim

# Stel de werkdirectory in
WORKDIR /app

# Kopieer de vereisten en installeer afhankelijkheden
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopieer de code en configuratie
COPY bot/ /app/bot/
COPY config/ /app/config/

# Stel het opstartcommando in
CMD ["python", "bot/scalping_bot.py"]