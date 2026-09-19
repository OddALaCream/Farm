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
const WHATSAPP_NUMBER = (process.env.WHATSAPP_NUMBER || "").replace(/\D/g, "");
const DB_PATH = process.env.DB_PATH || path.join(__dirname, "..", "data", "arbitrage.db");

// Estado de la conexión
let isReady = false;
let lastQR = null;
let ownWid = null;
const processedMessageIds = new Set();
const COMMANDS = new Set(["!estado", "!alerta"]);

function normalizePhone(id) {
  if (!id) return "";
  return String(id).split("@")[0].replace(/\D/g, "");
}

function getMessageText(msg) {
  return (msg.body || "").trim().toLowerCase();
}

function isCommand(text) {
  return COMMANDS.has(text);
}

function isOwnNumber(id) {
  if (!id) return false;

  const normalized = normalizePhone(id);
  if (!normalized) return false;

  if (WHATSAPP_NUMBER && normalized === WHATSAPP_NUMBER) return true;
  if (ownWid && id === ownWid) return true;

  if (WHATSAPP_NUMBER && normalized.endsWith(WHATSAPP_NUMBER.slice(-8))) {
    return true;
  }

  return false;
}

function isFromOwner(msg) {
  if (msg.fromMe) return true;
  if (isOwnNumber(msg.from)) return true;
  return false;
}

/**
 * Verifica que el mensaje sea del chat "Mensaje a ti mismo".
 * WhatsApp usa IDs @lid en ese chat; getChat() suele fallar ahí.
 */
async function isSelfChatMessage(msg) {
  if (msg.fromMe && isOwnNumber(msg.from)) return true;
  if (msg.fromMe && msg.to && msg.to.endsWith("@lid")) return true;

  try {
    const chat = await msg.getChat();
    if (chat.isGroup) return false;

    const chatId = chat.id._serialized;
    if (msg.fromMe && msg.from === msg.to) return true;
    if (ownWid && chatId === ownWid) return true;
    if (isOwnNumber(chatId)) return true;

    const contact = await chat.getContact();
    if (contact.isMe) return true;
  } catch (err) {
    console.warn("getChat/getContact no disponible:", err.message);
  }

  return isFromOwner(msg);
}

function getReplyChatId(msg) {
  if (msg.fromMe && msg.to) return msg.to;
  if (msg.from) return msg.from;
  return ownWid;
}

function markProcessed(msg) {
  const id =
    msg.id?._serialized ||
    `${msg.from}|${msg.to}|${msg.body}|${msg.timestamp}`;

  if (processedMessageIds.has(id)) return false;

  processedMessageIds.add(id);
  setTimeout(() => processedMessageIds.delete(id), 60000);
  return true;
}

async function replyInChat(msg, text) {
  const chatId = getReplyChatId(msg);
  const targets = [chatId, msg.to, msg.from, ownWid].filter(Boolean);
  const uniqueTargets = [...new Set(targets)];

  for (const target of uniqueTargets) {
    try {
      await client.sendMessage(target, text);
      console.log(`✅ Mensaje enviado a ${target}`);
      return;
    } catch (err) {
      console.warn(`sendMessage(${target}) falló:`, err.message);
    }
  }

  throw new Error(`No se pudo enviar respuesta. Destinos probados: ${uniqueTargets.join(", ")}`);
}

function queryDb(sql) {
  const sqlite3 = require("sqlite3").verbose();

  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(DB_PATH, sqlite3.OPEN_READONLY, (err) => {
      if (err) {
        reject(err);
        return;
      }

      db.get(sql, (queryErr, row) => {
        db.close();
        if (queryErr) reject(queryErr);
        else resolve(row);
      });
    });
  });
}

function formatStatusMessage(row, title) {
  const sign = row.margen >= 0 ? "+" : "";
  const timestamp = row.timestamp.split("T").join(" ").substring(0, 19);

  return (
    `${title}\n` +
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
    `_Última actualización: ${timestamp}_`
  );
}

// Limpiar SingletonLock de Chromium si existe por un mal apagado previo
const lockPath = path.join("/app/.wwebjs_auth", "session", "SingletonLock");
try {
  fs.unlinkSync(lockPath);
  console.log("🔓 Archivo SingletonLock eliminado (previniendo error Code 21)");
} catch (e) {
  // Ignorar si no existe
}

// Inicializar cliente WhatsApp con autenticación local persistente
const client = new Client({
  authStrategy: new LocalAuth({
    dataPath: "/app/.wwebjs_auth",
  }),
  webVersionCache: {
    type: "remote",
    remotePath:
      "https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.3000.1047947458-alpha.html",
  },
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
  ownWid = client.info?.wid?._serialized || null;
  console.log("");
  console.log("=".repeat(50));
  console.log("  ✅ WHATSAPP CONECTADO Y LISTO");
  console.log(`  📱 Cuenta: ${ownWid || "desconocida"}`);
  console.log("  ⌨️  Comandos activos: !estado, !alerta (chat contigo mismo)");
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

async function handleCommand(msg, source) {
  const text = getMessageText(msg);
  if (!isCommand(text)) return;
  if (!markProcessed(msg)) return;

  console.log(
    `[CMD] ${source} | fromMe=${msg.fromMe} | from=${msg.from} | to=${msg.to} | body="${text}"`
  );

  if (!isFromOwner(msg)) {
    console.log(`Comando ${text} ignorado: remitente no autorizado`);
    return;
  }

  try {
    if (!(await isSelfChatMessage(msg))) {
      console.log(
        `Comando ${text} ignorado: solo responde en tu chat contigo mismo`
      );
      return;
    }

    const chatId = getReplyChatId(msg);
    console.log(`📥 Comando ${text} aceptado en chat propio: ${chatId}`);

    const sql =
      text === "!alerta"
        ? "SELECT * FROM alerts ORDER BY id DESC LIMIT 1"
        : "SELECT * FROM operations ORDER BY id DESC LIMIT 1";

    const row = await queryDb(sql);

    if (!row) {
      const emptyMessage =
        text === "!alerta"
          ? "⚠️ Aún no se ha enviado ninguna alerta."
          : "⚠️ Aún no hay datos registrados. El bot se está ejecutando.";
      await replyInChat(msg, emptyMessage);
      return;
    }

    const title =
      text === "!alerta" ? "🚨 *ÚLTIMA ALERTA P2P*" : "📊 *ESTADO ACTUAL P2P*";

    console.log("📤 Enviando respuesta...");
    await replyInChat(msg, formatStatusMessage(row, title));
    console.log("✅ Respuesta enviada");
  } catch (err) {
    console.error("❌ Error procesando comando:", err.message);
    if (err.stack) console.error(err.stack);
    try {
      await replyInChat(msg, "❌ Error al acceder a los datos locales.");
    } catch (replyErr) {
      console.error("❌ Error al enviar respuesta:", replyErr.message);
      if (replyErr.stack) console.error(replyErr.stack);
    }
  }
}

// message_create: captura mensajes propios enviados desde el celular
client.on("message_create", (msg) => {
  handleCommand(msg, "message_create").catch((err) => {
    console.error("❌ Error en message_create:", err.message);
  });
});

// message: captura mensajes sincronizados que llegan con fromMe=false
client.on("message", (msg) => {
  handleCommand(msg, "message").catch((err) => {
    console.error("❌ Error en message:", err.message);
  });
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
