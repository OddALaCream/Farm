"""
Bot de monitoreo de arbitraje P2P de Binance.

Punto de entrada principal. Ejecuta un bucle de monitoreo que:
1. Consulta precios P2P de Binance (USD→USDT y USDT→BOB).
2. Calcula costo real, margen y ganancia estimada.
3. Guarda resultados en SQLite.
4. Envía alertas por WhatsApp si el margen supera el umbral.
"""

import logging
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

from binance import get_best_buy_price, get_best_sell_price
from calculator import calculate_full_arbitrage
from database import init_db, save_operation
from notifier import (
    check_whatsapp_status,
    send_whatsapp_alert,
    should_send_alert,
)

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("main")


def load_config() -> dict:
    """
    Carga la configuración desde variables de entorno.

    Todos los valores provienen del .env; ninguno está hardcodeado.

    Returns:
        Diccionario con la configuración validada.
    """
    config = {
        "usd_bob_cost": float(os.environ.get("USD_BOB_COST", "0")),
        "skrill_deposit_fee": float(os.environ.get("SKRILL_DEPOSIT_FEE", "0")),
        "skrill_transfer_fee": float(
            os.environ.get("SKRILL_TRANSFER_FEE", "0")
        ),
        "min_profit_percent": float(
            os.environ.get("MIN_PROFIT_PERCENT", "5")
        ),
        "capital_bob": float(os.environ.get("CAPITAL_BOB", "10000")),
        "check_interval": int(os.environ.get("CHECK_INTERVAL_SECONDS", "60")),
        "whatsapp_number": os.environ.get("WHATSAPP_NUMBER", ""),
        "timezone": os.environ.get("TIMEZONE", "America/La_Paz"),
    }

    # Validaciones
    errors = []

    if config["usd_bob_cost"] <= 0:
        errors.append("USD_BOB_COST debe ser mayor a 0")

    if config["capital_bob"] <= 0:
        errors.append("CAPITAL_BOB debe ser mayor a 0")

    if not config["whatsapp_number"]:
        errors.append("WHATSAPP_NUMBER es requerido")

    if config["check_interval"] < 10:
        errors.append("CHECK_INTERVAL_SECONDS debe ser >= 10")

    if errors:
        for error in errors:
            logger.error("Error de configuración: %s", error)
        raise ValueError(
            f"Configuración inválida: {'; '.join(errors)}"
        )

    return config


def run_check(config: dict) -> None:
    """
    Ejecuta una iteración del monitoreo.

    1. Obtiene precios P2P.
    2. Calcula arbitraje.
    3. Guarda en BD.
    4. Evalúa y envía alerta si corresponde.
    """
    logger.info("=" * 60)
    logger.info("Iniciando verificación de precios P2P...")
    logger.info("=" * 60)

    # 1. Obtener precio de compra: USD → USDT
    buy_ad = get_best_buy_price(fiat="USD", asset="USDT")

    if buy_ad is None:
        logger.warning("No se encontraron anuncios USD → USDT")
        return

    price_usd_usdt = buy_ad["price"]
    logger.info(
        "Mejor precio compra USD → USDT: %.4f "
        "(vendedor: %s, métodos: %s)",
        price_usd_usdt,
        buy_ad["advertiser_name"],
        ", ".join(buy_ad["payment_methods"]),
    )

    # 2. Obtener precio de venta: USDT → BOB
    sell_ad = get_best_sell_price(fiat="BOB", asset="USDT")

    if sell_ad is None:
        logger.warning("No se encontraron anuncios USDT → BOB")
        return

    price_usdt_bob = sell_ad["price"]
    logger.info(
        "Mejor precio venta USDT → BOB: %.4f "
        "(comprador: %s, métodos: %s)",
        price_usdt_bob,
        sell_ad["advertiser_name"],
        ", ".join(sell_ad["payment_methods"]),
    )

    # 3. Calcular arbitraje
    result = calculate_full_arbitrage(
        usd_bob_cost=config["usd_bob_cost"],
        price_usd_usdt=price_usd_usdt,
        price_usdt_bob=price_usdt_bob,
        deposit_fee=config["skrill_deposit_fee"],
        transfer_fee=config["skrill_transfer_fee"],
        capital_bob=config["capital_bob"],
    )

    # 4. Mostrar resultados en consola
    logger.info("-" * 40)
    logger.info("RESULTADOS:")
    logger.info("  Costo real USDT:  %.4f Bs", result["real_cost"])
    logger.info("  Precio compra:    %.4f USD/USDT", result["buy_price"])
    logger.info("  Precio venta:     %.4f BOB/USDT", result["sell_price"])
    logger.info("  Margen:           %+.2f%%", result["margin_percent"])
    logger.info("  Capital:          %.0f Bs", result["capital"])
    logger.info("  Ganancia est.:    %.2f Bs", result["estimated_profit"])
    logger.info("-" * 40)

    # 5. Guardar en base de datos
    try:
        save_operation(
            precio_usdt_usd=result["buy_price"],
            precio_usdt_bob=result["sell_price"],
            costo_real=result["real_cost"],
            margen=result["margin_percent"],
            capital=result["capital"],
            ganancia_estimada=result["estimated_profit"],
        )
        logger.info("Operación guardada en base de datos")
    except Exception as e:
        logger.error("Error al guardar operación: %s", str(e))

    # 6. Evaluar y enviar alerta
    if should_send_alert(
        current_margin=result["margin_percent"],
        min_profit_percent=config["min_profit_percent"],
    ):
        logger.info(
            "🚨 Margen %.2f%% supera el mínimo (%.2f%%). Enviando alerta...",
            result["margin_percent"],
            config["min_profit_percent"],
        )

        if send_whatsapp_alert(result):
            logger.info("✅ Alerta enviada exitosamente")
        else:
            logger.error("❌ Error al enviar alerta WhatsApp")
    else:
        logger.info(
            "Sin alerta: margen %.2f%% (mínimo: %.2f%%)",
            result["margin_percent"],
            config["min_profit_percent"],
        )


def main() -> None:
    """Punto de entrada principal del bot."""
    logger.info("=" * 60)
    logger.info("  BINANCE P2P ARBITRAGE MONITOR")
    logger.info("  Iniciado: %s", datetime.now().isoformat())
    logger.info("=" * 60)

    # Cargar configuración
    try:
        config = load_config()
    except ValueError as e:
        logger.critical("Error fatal de configuración: %s", str(e))
        sys.exit(1)

    logger.info("Configuración cargada:")
    logger.info("  USD/BOB cost:       %.2f", config["usd_bob_cost"])
    logger.info("  Skrill dep. fee:    %.2f%%", config["skrill_deposit_fee"] * 100)
    logger.info("  Skrill trans. fee:  %.2f%%", config["skrill_transfer_fee"] * 100)
    logger.info("  Min profit:         %.2f%%", config["min_profit_percent"])
    logger.info("  Capital:            %.0f BOB", config["capital_bob"])
    logger.info("  Intervalo:          %ds", config["check_interval"])
    logger.info("  WhatsApp:           %s", config["whatsapp_number"])
    logger.info("  Timezone:           %s", config["timezone"])

    # Inicializar base de datos
    try:
        init_db()
    except Exception as e:
        logger.critical("Error al inicializar BD: %s", str(e))
        sys.exit(1)

    # Verificar servicio WhatsApp
    logger.info("Verificando servicio WhatsApp...")
    wa_ready = check_whatsapp_status()

    if wa_ready:
        logger.info("✅ WhatsApp conectado y listo")
    else:
        logger.warning(
            "⚠️  WhatsApp no está listo. Las alertas no se enviarán "
            "hasta que esté conectado. Revise los logs del servicio "
            "de WhatsApp para escanear el QR."
        )

    # Bucle principal
    logger.info("Iniciando bucle de monitoreo (cada %ds)...", config["check_interval"])

    while True:
        try:
            run_check(config)
        except KeyboardInterrupt:
            logger.info("Monitoreo detenido por el usuario")
            break
        except Exception as e:
            logger.error(
                "Error en iteración de monitoreo: %s",
                str(e),
                exc_info=True,
            )

        logger.info(
            "Próxima verificación en %d segundos...\n",
            config["check_interval"],
        )

        try:
            time.sleep(config["check_interval"])
        except KeyboardInterrupt:
            logger.info("Monitoreo detenido por el usuario")
            break

    logger.info("Bot finalizado.")


if __name__ == "__main__":
    main()
