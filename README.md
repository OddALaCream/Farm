# 🚀 Binance P2P Arbitrage Monitor

Bot privado de monitoreo de arbitraje P2P de Binance con alertas automáticas por WhatsApp.

## 📋 Descripción

Sistema que monitorea automáticamente oportunidades de arbitraje en Binance P2P:

```
USD (Skrill/tarjeta)  →  USDT (Binance P2P)  →  BOB (Binance P2P)
```

Calcula el margen de ganancia real considerando comisiones y envía alertas por WhatsApp cuando se detecta una oportunidad rentable.

## 🏗️ Arquitectura

```
┌──────────────────────────────────────────┐
│              Docker Compose              │
│                                          │
│  ┌──────────────┐    ┌───────────────┐   │
│  │   Backend    │    │   WhatsApp    │   │
│  │  (Python)    │───▶│   (Node.js) . │   │
│  │              │    │               │   │
│  │  • Binance   │    │  • wwebjs     │   │
│  │  • Cálculo   │    │  • Express    │   │
│  │  • SQLite    │    │  • Sesión     │   │
│  └──────┬───────┘    └───────────────┘   │
│         │                                │
│         ▼                                │
│  ┌──────────────┐                        │
│  │   SQLite DB  │                        │
│  │  (volumen)   │                        │
│  └──────────────┘                        │
└──────────────────────────────────────────┘
```

## ⚙️ Requisitos

- [Docker](https://docs.docker.com/get-docker/) instalado
- [Docker Compose](https://docs.docker.com/compose/install/) instalado (v2+)
- Conexión a Internet

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone <tu-repositorio>
cd arbitrage-bot
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con tus valores:

```env
# Tipo de cambio USD/BOB
USD_BOB_COST=11.10

# Comisiones de Skrill
SKRILL_DEPOSIT_FEE=0.05
SKRILL_TRANSFER_FEE=0.0145

# Margen mínimo para alertar (%)
MIN_PROFIT_PERCENT=5

# Capital disponible en BOB
CAPITAL_BOB=10000

# Intervalo de verificación (segundos)
CHECK_INTERVAL_SECONDS=60

# Tu número de WhatsApp con código de país
WHATSAPP_NUMBER=591XXXXXXXX

# Zona horaria
TIMEZONE=America/La_Paz
```

### 3. Construir las imágenes

```bash
docker compose build
```

### 4. Iniciar los servicios

```bash
docker compose up -d
```

## 📱 Primer inicio: Vincular WhatsApp

En el primer inicio necesitas escanear un código QR para vincular tu WhatsApp.

### Ver el QR en los logs:

```bash
docker compose logs -f whatsapp
```

Verás algo como:

```
==================================================
  📱 ESCANEAR QR PARA VINCULAR WHATSAPP
==================================================

  ▄▄▄▄▄▄▄ ▄▄▄▄▄ ▄▄▄▄▄▄▄
  █ ▄▄▄ █ █ ▄ █ █ ▄▄▄ █
  ...

  Escanea el código QR con WhatsApp:
  WhatsApp > Dispositivos vinculados > Vincular dispositivo
==================================================
```

### Pasos:
1. Abre WhatsApp en tu teléfono
2. Ve a **Configuración** > **Dispositivos vinculados**
3. Toca **Vincular un dispositivo**
4. Escanea el QR que aparece en los logs

Una vez vinculado, la sesión se guarda automáticamente y no necesitarás escanear de nuevo.

## 📊 Uso

### Ver logs en tiempo real

```bash
# Todos los servicios
docker compose logs -f

# Solo backend
docker compose logs -f backend

# Solo WhatsApp
docker compose logs -f whatsapp
```

### Reiniciar servicios

```bash
docker compose restart
```

### Detener servicios

```bash
docker compose down
```

### Reconstruir después de cambios

```bash
docker compose build
docker compose up -d
```

## 🔢 Fórmula de cálculo

```
costo_real_usdt = USD_BOB_COST × precio_USD_USDT × (1 + deposito_fee) × (1 + transferencia_fee)

margen = (precio_USDT_BOB / costo_real_usdt - 1) × 100
```

### Ejemplo:

| Variable | Valor |
|---|---|
| USD_BOB_COST | 11.10 |
| Precio USD→USDT | 1.005 |
| Precio USDT→BOB | 12.55 |
| Dep. fee (5%) | 0.05 |
| Trans. fee (1.45%) | 0.0145 |

```
costo_real = 11.10 × 1.005 × 1.05 × 1.0145 = 11.88 Bs
margen = (12.55 / 11.88 - 1) × 100 = +5.64%
ganancia = 10000 × 5.64% = 564 Bs
```

## 📬 Formato de alertas

Cuando el margen supera el umbral configurado, recibirás un mensaje como:

```
🚨 OPORTUNIDAD P2P

📥 Compra:
USD → USDT: 1.0050

📤 Venta:
USDT → BOB: 12.5500

💰 Costo real:
11.88 Bs

📊 Margen:
+5.64%

🏦 Capital:
10000 Bs

✅ Ganancia:
564.00 Bs
```

## 🛡️ Anti-spam

El sistema evita enviar alertas repetitivas:
- No envía si el margen no supera el mínimo
- No repite alertas con margen similar (< 0.5% de diferencia)
- Solo re-alerta si el margen cambia significativamente

## 📁 Estructura del proyecto

```
arbitrage-bot/
├── backend/
│   ├── main.py           # Punto de entrada y bucle principal
│   ├── binance.py         # Consultas a Binance P2P
│   ├── calculator.py      # Cálculos de arbitraje
│   ├── database.py        # Gestión SQLite
│   ├── notifier.py        # Alertas WhatsApp
│   ├── requirements.txt   # Dependencias Python
│   └── Dockerfile
│
├── whatsapp/
│   ├── bot.js             # Servicio WhatsApp
│   ├── package.json       # Dependencias Node.js
│   └── Dockerfile
│
├── data/
│   └── arbitrage.db       # Base de datos (auto-generada)
│
├── docker-compose.yml
├── .env                   # Configuración (no commitear)
├── .env.example           # Plantilla de configuración
├── .gitignore
└── README.md
```

## 🔧 Solución de problemas

### El QR no aparece
```bash
docker compose restart whatsapp
docker compose logs -f whatsapp
```

### WhatsApp se desconecta frecuentemente
La sesión se reconecta automáticamente. Si persiste:
```bash
# Eliminar sesión guardada y re-vincular
docker compose down
docker volume rm arbitrage-bot_whatsapp_session
docker compose up -d
docker compose logs -f whatsapp
```

### No se reciben alertas
1. Verificar que WhatsApp esté conectado: `docker compose logs whatsapp`
2. Verificar que el número esté bien configurado en `.env`
3. Verificar que el margen supere `MIN_PROFIT_PERCENT`
4. Revisar logs del backend: `docker compose logs backend`

### Error de conexión con Binance
- Verificar conexión a Internet del VPS
- Binance puede limitar requests; aumentar `CHECK_INTERVAL_SECONDS`
- El bot reintenta automáticamente (3 intentos con 5s de espera)

## ⚠️ Disclaimer

Este bot es **únicamente para monitoreo y alertas**. No realiza:
- Trading automático
- Compras/ventas automáticas
- Gestión de fondos
- Retiros

Toda operación debe ser ejecutada manualmente por el usuario.

## 📄 Licencia

Uso privado.
