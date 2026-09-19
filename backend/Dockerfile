FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Crear directorio para datos
RUN mkdir -p /app/data

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/app/data/arbitrage.db

CMD ["python", "main.py"]
