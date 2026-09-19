"""
Módulo de notificaciones.

Envía alertas al servicio de WhatsApp y gestiona la lógica
anti-spam para evitar mensajes duplicados.
"""

import logging
import os
from typing import Optional

import requests

from database import get_last_alert, save_alert

logger = logging.getLogger(__name__)

WHATSAPP_SERVICE_URL = os.environ.get(
    "WHATSAPP_SERVICE_URL", "http://whatsapp:3000"
)
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")
MARGIN_CHANGE_THRESHOLD = 0.5  # % de cambio mínimo para re-alertar


def should_send_alert(
    current_margin: float,
    min_profit_percent: float,
) -> bool:
    """
    Determina si se debe enviar una alerta.

    Condiciones para enviar:
    1. El margen supera el mínimo configurado.
    2. No se ha enviado una alerta reciente con margen similar.
    3. Si ya hay una alerta previa, el margen debe haber cambiado
       significativamente (más de MARGIN_CHANGE_THRESHOLD%).

    Args:
        current_margin: Margen actual calculado.
        min_profit_percent: Margen mínimo para alertar.

    Returns:
        True si se debe enviar la alerta.
    """
    if current_margin < min_profit_percent:
        logger.debug(
            "Margen %.2f%% < mínimo %.2f%%, no se envía alerta",
            current_margin,
            min_profit_percent,
        )
        return False

    last_alert = get_last_alert()

    if last_alert is None:
        logger.info("No hay alertas previas, se enviará la primera alerta")
        return True

    last_margin = last_alert.get("margen", 0)
    margin_diff = abs(current_margin - last_margin)

    if margin_diff < MARGIN_CHANGE_THRESHOLD:
        logger.debug(
            "Cambio de margen (%.2f%%) menor que umbral (%.2f%%), "
            "no se envía alerta duplicada",
            margin_diff,
            MARGIN_CHANGE_THRESHOLD,
        )
        return False

    logger.info(
        "Cambio significativo de margen: %.2f%% → %.2f%% (diff: %.2f%%)",
        last_margin,
        current_margin,
        margin_diff,
    )
    return True


def format_alert_message(result: dict) -> str:
    """
    Formatea el mensaje de alerta para WhatsApp.

    Args:
        result: Diccionario con los resultados del cálculo de arbitraje.

    Returns:
        Mensaje formateado listo para enviar.
    """
    sign = "+" if result["margin_percent"] >= 0 else ""

    message = (
        "🚨 *OPORTUNIDAD P2P*\n"
        "\n"
        "📥 *Compra:*\n"
        f"USD → USDT: {result['buy_price']:.4f}\n"
        "\n"
        "📤 *Venta:*\n"
        f"USDT → BOB: {result['sell_price']:.4f}\n"
        "\n"
        "💰 *Costo real:*\n"
        f"{result['real_cost']:.2f} Bs\n"
        "\n"
        "📊 *Margen:*\n"
        f"{sign}{result['margin_percent']:.2f}%\n"
        "\n"
        "🏦 *Capital:*\n"
        f"{result['capital']:.0f} Bs\n"
        "\n"
        "✅ *Ganancia:*\n"
        f"{result['estimated_profit']:.2f} Bs"
    )

    return message


def send_whatsapp_alert(result: dict) -> bool:
    """
    Envía una alerta por WhatsApp.

    Args:
        result: Diccionario con los resultados del cálculo.

    Returns:
        True si se envió exitosamente, False en caso contrario.
    """
    if not WHATSAPP_NUMBER:
        logger.error("WHATSAPP_NUMBER no configurado")
        return False

    message = format_alert_message(result)

    try:
        response = requests.post(
            f"{WHATSAPP_SERVICE_URL}/send",
            json={
                "number": WHATSAPP_NUMBER,
                "message": message,
            },
            timeout=10,
        )

        if response.status_code == 200:
            logger.info("Alerta WhatsApp enviada exitosamente")

            # Guardar registro de alerta
            save_alert(
                margen=result["margin_percent"],
                precio_usdt_usd=result["buy_price"],
                precio_usdt_bob=result["sell_price"],
                costo_real=result["real_cost"],
                capital=result["capital"],
                ganancia_estimada=result["estimated_profit"],
            )

            return True
        else:
            logger.error(
                "Error al enviar alerta WhatsApp: HTTP %d - %s",
                response.status_code,
                response.text,
            )
            return False

    except requests.exceptions.ConnectionError:
        logger.error(
            "No se pudo conectar al servicio de WhatsApp en %s",
            WHATSAPP_SERVICE_URL,
        )
        return False

    except requests.exceptions.Timeout:
        logger.error("Timeout al enviar alerta WhatsApp")
        return False

    except requests.exceptions.RequestException as e:
        logger.error("Error inesperado al enviar alerta: %s", str(e))
        return False


def check_whatsapp_status() -> bool:
    """
    Verifica que el servicio de WhatsApp esté activo y conectado.

    Returns:
        True si el servicio está listo.
    """
    try:
        response = requests.get(
            f"{WHATSAPP_SERVICE_URL}/status",
            timeout=5,
        )

        if response.status_code == 200:
            data = response.json()
            is_ready = data.get("ready", False)

            if is_ready:
                logger.info("Servicio WhatsApp conectado y listo")
            else:
                logger.warning(
                    "Servicio WhatsApp activo pero no conectado "
                    "(posiblemente esperando QR)"
                )

            return is_ready

        return False

    except requests.exceptions.RequestException:
        logger.warning("Servicio WhatsApp no disponible")
        return False
