FROM node:20-slim

WORKDIR /app

# Instalar dependencias del sistema para Chromium (whatsapp-web.js)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Configurar Puppeteer para usar Chromium del sistema
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Copiar e instalar dependencias Node.js
COPY package.json .
RUN npm install --production

# Copiar código fuente
COPY . .

# Crear directorio para sesión persistente
RUN mkdir -p /app/.wwebjs_auth

EXPOSE 3000

CMD ["node", "bot.js"]
