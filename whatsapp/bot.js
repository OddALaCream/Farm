/**
 * Servicio de WhatsApp para envío de alertas.
 *
 * Usa whatsapp-web.js para mantener una sesión persistente
 * y expone un API HTTP local para recibir solicitudes de envío.
 *
 * Endpoints:
 *   GET  /status  - Estado de la conexión
 *   POST /send    - Enviar mensaje
 */

const { Client, LocalAuth } = require("whatsapp-web.js");
const express = require("express");
const qrcode = require("qrcode-terminal");
const fs = require("fs");
const path = require("path");

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;

// Estado de la conexión
let isReady = false;
let lastQR = null;

// Limpiar SingletonLock de Chromium si existe por un mal apagado previo
const lockPath = path.join("/app/.wwebjs_auth", "session", "SingletonLock");
if (fs.existsSync(lockPath)) {
  try {
    fs.unlinkSync(lockPath);
    console.log("🔓 Archivo SingletonLock eliminado (previniendo error Code 21)");
  } catch (e) {
    console.error("⚠️ No se pudo eliminar SingletonLock:", e.message);
  }
}

// Inicializar cliente WhatsApp con autenticación local persistente
const client = new Client({
  authStrategy: new LocalAuth({
    dataPath: "/app/.wwebjs_auth",
  }),
  puppeteer: {
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-accelerated-2d-canvas",
      "--no-first-run",
      "--no-zygote",
      "--disable-gpu",
    ],
  },
});

// ===== Eventos del cliente WhatsApp =====

client.on("qr", (qr) => {
  lastQR = qr;
  console.log("");
  console.log("=".repeat(50));
  console.log("  📱 ESCANEAR QR PARA VINCULAR WHATSAPP");
  console.log("=".repeat(50));
  console.log("");
  qrcode.generate(qr, { small: true });
  console.log("");
  console.log("  Escanea el código QR con WhatsApp:");
  console.log("  WhatsApp > Dispositivos vinculados > Vincular dispositivo");
  console.log("=".repeat(50));
  console.log("");
});

client.on("ready", () => {
  isReady = true;
  lastQR = null;
  console.log("");
  console.log("=".repeat(50));
  console.log("  ✅ WHATSAPP CONECTADO Y LISTO");
  console.log("=".repeat(50));
  console.log("");
});

client.on("authenticated", () => {
  console.log("🔐 Sesión autenticada");
});

client.on("auth_failure", (msg) => {
  isReady = false;
  console.error("❌ Error de autenticación:", msg);
});

client.on("disconnected", (reason) => {
  isReady = false;
  console.warn("⚠️  WhatsApp desconectado:", reason);
  console.log("Intentando reconectar en 10 segundos...");
  setTimeout(() => {
    client.initialize().catch((err) => {
      console.error("Error al reinicializar:", err);
    });
  }, 10000);
});

client.on("message_create", async (msg) => {
  const text = msg.body.trim().toLowerCase();
  if (text === '!estado' || text === '!alerta') {
    const chatId = msg.fromMe ? msg.to : msg.from;
    console.log(`\n📥 Comando ${text} recibido en chat: ${chatId}`);
    
    const sqlite3 = require('sqlite3').verbose();
    const DB_PATH = '/app/data/arbitrage.db';
    
    const db = new sqlite3.Database(DB_PATH, sqlite3.OPEN_READONLY, (err) => {
      if (err) {
        console.error("❌ Error al abrir base de datos:", err.message);
        client.sendMessage(chatId, "❌ Error al acceder a los datos locales.");
        return;
      }
    });

    db.get("SELECT * FROM operations ORDER BY id DESC LIMIT 1", (err, row) => {
      if (err) {
        console.error("❌ Error en query:", err);
        client.sendMessage(chatId, "❌ Error al leer la base de datos.");
      } else if (row) {
        const sign = row.margen >= 0 ? "+" : "";
        
        const message = 
          "📊 *ESTADO ACTUAL P2P*\n" +
          "\n" +
          "📥 *Compra:*\n" +
          `USD → USDT: ${row.precio_usdt_usd.toFixed(4)}\n` +
          "\n" +
          "📤 *Venta:*\n" +
          `USDT → BOB: ${row.precio_usdt_bob.toFixed(4)}\n` +
          "\n" +
          "💰 *Costo real:*\n" +
          `${row.costo_real.toFixed(2)} Bs\n` +
          "\n" +
          "📊 *Margen:*\n" +
          `${sign}${row.margen.toFixed(2)}%\n` +
          "\n" +
          "🏦 *Capital:*\n" +
          `${row.capital.toFixed(0)} Bs\n` +
          "\n" +
          "✅ *Ganancia:*\n" +
          `${row.ganancia_estimada.toFixed(2)} Bs\n` +
          "\n" +
          `_Última actualización: ${row.timestamp.split('T').join(' ').substring(0, 19)}_`;
          
        console.log("📤 Enviando respuesta de estado...");
        client.sendMessage(chatId, message).catch(console.error);
      } else {
        client.sendMessage(chatId, "⚠️ Aún no hay datos registrados. El bot se está ejecutando.");
      }
      db.close();
    });
  }
});

// ===== Endpoints HTTP =====

/**
 * GET /status
 * Retorna el estado actual de la conexión WhatsApp.
 */
app.get("/status", (req, res) => {
  res.json({
    ready: isReady,
    hasQR: lastQR !== null,
    timestamp: new Date().toISOString(),
  });
});

/**
 * GET /health
 * Endpoint de salud para Docker healthcheck.
 */
app.get("/health", (req, res) => {
  res.json({ status: "ok" });
});

/**
 * POST /send
 * Envía un mensaje de WhatsApp.
 *
 * Body:
 *   - number: Número de teléfono con código de país (ej: "591XXXXXXXX")
 *   - message: Texto del mensaje
 */
app.post("/send", async (req, res) => {
  const { number, message } = req.body;

  // Validación de parámetros
  if (!number || !message) {
    return res.status(400).json({
      success: false,
      error: "Se requiere 'number' y 'message' en el body",
    });
  }

  // Verificar conexión
  if (!isReady) {
    return res.status(503).json({
      success: false,
      error: "WhatsApp no está conectado. Escanea el QR primero.",
    });
  }

  try {
    // Formatear número: asegurar que termina en @c.us
    const chatId = number.includes("@c.us") ? number : `${number}@c.us`;

    console.log(`📤 Enviando mensaje a ${chatId}...`);

    await client.sendMessage(chatId, message);

    console.log(`✅ Mensaje enviado exitosamente a ${chatId}`);

    return res.json({
      success: true,
      message: "Mensaje enviado",
      to: chatId,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error("❌ Error al enviar mensaje:", error.message);

    return res.status(500).json({
      success: false,
      error: `Error al enviar: ${error.message}`,
    });
  }
});

// ===== Inicialización =====

// Iniciar servidor HTTP
app.listen(PORT, () => {
  console.log("");
  console.log("=".repeat(50));
  console.log(`  🌐 Servidor HTTP escuchando en puerto ${PORT}`);
  console.log("=".repeat(50));
  console.log("");
});

// Iniciar cliente WhatsApp
console.log("Inicializando cliente WhatsApp...");
client
  .initialize()
  .then(() => {
    console.log("Cliente WhatsApp inicializado");
  })
  .catch((err) => {
    console.error("Error al inicializar WhatsApp:", err);
  });

// Manejo de señales para shutdown limpio
process.on("SIGINT", async () => {
  console.log("\nRecibida señal SIGINT, cerrando...");
  try {
    await client.destroy();
  } catch (e) {
    // Ignorar errores de cierre
  }
  process.exit(0);
});

process.on("SIGTERM", async () => {
  console.log("\nRecibida señal SIGTERM, cerrando...");
  try {
    await client.destroy();
  } catch (e) {
    // Ignorar errores de cierre
  }
  process.exit(0);
});
