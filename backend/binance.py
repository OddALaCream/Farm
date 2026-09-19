"""
Módulo para consultar anuncios P2P de Binance.

Usa el endpoint público de Binance P2P (no requiere API keys).
Soporta filtrado por moneda fiat, activo, método de pago y rango de monto.
"""

import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

REQUEST_TIMEOUT = 15  # segundos
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos entre reintentos

SKRILL_PAY_TYPE = "SkrillMoneybookers"
SKRILL_PAY_TYPES = {"skrill", "skrillmoneybookers"}


def _normalize_pay_type(value: str) -> str:
    """Normaliza nombres de método de pago para comparar sin importar el alias."""
    return (value or "").strip().lower().replace("_", "").replace(" ", "")


def _is_skrill_pay_type(value: Optional[str]) -> bool:
    """True si el valor corresponde a Skrill en cualquiera de sus aliases."""
    return _normalize_pay_type(value) in SKRILL_PAY_TYPES


def fetch_p2p_ads(
    fiat: str,
    asset: str = "USDT",
    trade_type: str = "BUY",
    pay_types: Optional[list[str]] = None,
    trans_amount: Optional[float] = None,
    rows: int = 10,
    page: int = 1,
) -> list[dict]:
    """
    Consulta anuncios P2P de Binance.

    Args:
        fiat: Moneda fiat (ej: "USD", "BOB").
        asset: Activo cripto (por defecto "USDT").
        trade_type: "BUY" para comprar, "SELL" para vender.
        pay_types: Lista de métodos de pago (ej: ["Skrill", "BankTransfer"]).
        trans_amount: Monto de la transacción para filtrar anuncios.
        rows: Cantidad de resultados por página.
        page: Número de página.

    Returns:
        Lista de anuncios con precio, límites y métodos de pago.
    """
    payload = {
        "fiat": fiat,
        "asset": asset,
        "tradeType": trade_type,
        "rows": rows,
        "page": page,
        "publisherType": None,
        "merchantCheck": False,
    }

    if pay_types:
        payload["payTypes"] = [
            SKRILL_PAY_TYPE if _is_skrill_pay_type(pay_type) else pay_type
            for pay_type in pay_types
        ]

    if trans_amount is not None:
        payload["transAmount"] = trans_amount

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Consultando Binance P2P: %s %s/%s (intento %d/%d)",
                trade_type,
                asset,
                fiat,
                attempt,
                MAX_RETRIES,
            )

            response = requests.post(
                BINANCE_P2P_URL,
                json=payload,
                headers=DEFAULT_HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            data = response.json()

            if data.get("code") != "000000" or not data.get("success"):
                logger.warning(
                    "Binance P2P respondió con código inesperado: %s",
                    data.get("code"),
                )
                return []

            ads_raw = data.get("data", [])
            ads = _parse_ads(ads_raw)

            logger.info(
                "Obtenidos %d anuncios para %s %s/%s",
                len(ads),
                trade_type,
                asset,
                fiat,
            )
            return ads

        except requests.exceptions.Timeout:
            logger.warning(
                "Timeout al consultar Binance P2P (intento %d/%d)",
                attempt,
                MAX_RETRIES,
            )

        except requests.exceptions.ConnectionError:
            logger.warning(
                "Error de conexión con Binance P2P (intento %d/%d)",
                attempt,
                MAX_RETRIES,
            )

        except requests.exceptions.HTTPError as e:
            logger.error(
                "Error HTTP %s de Binance P2P (intento %d/%d)",
                e.response.status_code if e.response else "desconocido",
                attempt,
                MAX_RETRIES,
            )

        except requests.exceptions.RequestException as e:
            logger.error(
                "Error inesperado al consultar Binance P2P: %s (intento %d/%d)",
                str(e),
                attempt,
                MAX_RETRIES,
            )

        if attempt < MAX_RETRIES:
            logger.info("Reintentando en %d segundos...", RETRY_DELAY)
            time.sleep(RETRY_DELAY)

    logger.error(
        "No se pudo obtener datos de Binance P2P después de %d intentos",
        MAX_RETRIES,
    )
    return []


def _parse_ads(ads_raw: list[dict]) -> list[dict]:
    """Parsea la respuesta de Binance P2P a un formato limpio."""
    parsed = []

    for item in ads_raw:
        adv = item.get("adv", {})
        advertiser = item.get("advertiser", {})

        try:
            ad = {
                "price": float(adv.get("price", 0)),
                "min_amount": float(adv.get("minSingleTransAmount", 0)),
                "max_amount": float(adv.get("maxSingleTransAmount", 0)),
                "available": float(adv.get("surplusAmount", 0)),
                "asset": adv.get("asset", ""),
                "fiat": adv.get("fiatUnit", ""),
                "trade_type": adv.get("tradeType", ""),
                "payment_methods": [
                    method.get("tradeMethodName", "")
                    for method in adv.get("tradeMethods", [])
                ],
                "advertiser_name": advertiser.get("nickName", ""),
                "advertiser_orders": advertiser.get("monthOrderCount", 0),
                "advertiser_completion_rate": float(
                    advertiser.get("monthFinishRate", 0)
                ),
            }
            parsed.append(ad)
        except (ValueError, TypeError) as e:
            logger.warning("Error al parsear anuncio: %s", str(e))
            continue

    return parsed


def _is_skrill_only_ad(ad: dict) -> bool:
    """True si el anuncio acepta únicamente Skrill como método de pago."""
    methods = [method.strip() for method in ad.get("payment_methods", []) if method]
    if not methods:
        return False

    return all(
        _normalize_pay_type(method).startswith("skrill")
        for method in methods
    )


def get_best_buy_price(
    fiat: str,
    asset: str = "USDT",
    pay_types: Optional[list[str]] = None,
    trans_amount: Optional[float] = None,
) -> Optional[dict]:
    """
    Obtiene el mejor precio de COMPRA (el más bajo).

    Returns:
        El anuncio con el mejor precio o None si no hay datos.
    """
    ads = fetch_p2p_ads(
        fiat=fiat,
        asset=asset,
        trade_type="BUY",
        pay_types=pay_types,
        trans_amount=trans_amount,
    )

    if not ads:
        return None

    if pay_types and any(_is_skrill_pay_type(pay_type) for pay_type in pay_types):
        ads = [ad for ad in ads if _is_skrill_only_ad(ad)]
        if not ads:
            logger.warning(
                "No hay anuncios USD → USDT que acepten solo Skrill"
            )
            return None

    # El mejor precio de compra es el más bajo
    return min(ads, key=lambda x: x["price"])


def get_best_sell_price(
    fiat: str,
    asset: str = "USDT",
    pay_types: Optional[list[str]] = None,
    trans_amount: Optional[float] = None,
) -> Optional[dict]:
    """
    Obtiene el mejor precio de VENTA (el más alto).

    Returns:
        El anuncio con el mejor precio o None si no hay datos.
    """
    ads = fetch_p2p_ads(
        fiat=fiat,
        asset=asset,
        trade_type="SELL",
        pay_types=pay_types,
        trans_amount=trans_amount,
    )

    if not ads:
        return None

    # El mejor precio de venta es el más alto
    return max(ads, key=lambda x: x["price"])
