"""
Módulo de cálculo de arbitraje P2P.

Implementa el cálculo de costo real, margen y ganancia estimada
considerando comisiones de Skrill y tipo de cambio.
"""

import logging

logger = logging.getLogger(__name__)


def calculate_real_cost(
    usd_bob_cost: float,
    price_usd_usdt: float,
    deposit_fee: float,
    transfer_fee: float,
) -> float:
    """
    Calcula el costo real de 1 USDT en BOB.

    Fórmula:
        costo_real = USD_BOB_COST * precio_USD_USDT * (1 + deposito_fee) * (1 + transferencia_fee)

    Args:
        usd_bob_cost: Costo de 1 USD en BOB (tipo de cambio base).
        price_usd_usdt: Precio de compra de 1 USDT en USD (P2P).
        deposit_fee: Comisión de depósito Skrill (ej: 0.05 = 5%).
        transfer_fee: Comisión de transferencia Skrill (ej: 0.0145 = 1.45%).

    Returns:
        Costo real de 1 USDT en BOB.
    """
    real_cost = (
        usd_bob_cost
        * price_usd_usdt
        * (1 + deposit_fee)
        * (1 + transfer_fee)
    )

    logger.debug(
        "Costo real USDT: %.4f BOB "
        "(USD/BOB=%.2f, USD/USDT=%.4f, dep_fee=%.4f, trans_fee=%.4f)",
        real_cost,
        usd_bob_cost,
        price_usd_usdt,
        deposit_fee,
        transfer_fee,
    )

    return real_cost


def calculate_margin(
    price_usdt_bob: float,
    real_cost_usdt: float,
) -> float:
    """
    Calcula el margen de ganancia en porcentaje.

    Fórmula:
        margen = (precio_USDT_BOB / costo_real_usdt - 1) * 100

    Args:
        price_usdt_bob: Precio de venta de 1 USDT en BOB (P2P).
        real_cost_usdt: Costo real de 1 USDT en BOB.

    Returns:
        Margen de ganancia en porcentaje.
    """
    if real_cost_usdt <= 0:
        logger.error("Costo real USDT es <= 0, no se puede calcular margen")
        return 0.0

    margin = (price_usdt_bob / real_cost_usdt - 1) * 100

    logger.debug(
        "Margen: %.2f%% (venta=%.4f BOB, costo_real=%.4f BOB)",
        margin,
        price_usdt_bob,
        real_cost_usdt,
    )

    return margin


def calculate_estimated_profit(
    capital_bob: float,
    margin_percent: float,
) -> float:
    """
    Calcula la ganancia estimada en BOB.

    Args:
        capital_bob: Capital disponible en BOB.
        margin_percent: Margen de ganancia en porcentaje.

    Returns:
        Ganancia estimada en BOB.
    """
    profit = capital_bob * (margin_percent / 100)

    logger.debug(
        "Ganancia estimada: %.2f BOB (capital=%.2f BOB, margen=%.2f%%)",
        profit,
        capital_bob,
        margin_percent,
    )

    return profit


def calculate_full_arbitrage(
    usd_bob_cost: float,
    price_usd_usdt: float,
    price_usdt_bob: float,
    deposit_fee: float,
    transfer_fee: float,
    capital_bob: float,
) -> dict:
    """
    Ejecuta el cálculo completo de arbitraje.

    Returns:
        Diccionario con todos los resultados del cálculo:
        - real_cost: Costo real de 1 USDT en BOB
        - buy_price: Precio de compra USD→USDT
        - sell_price: Precio de venta USDT→BOB
        - margin_percent: Margen de ganancia en %
        - capital: Capital utilizado en BOB
        - estimated_profit: Ganancia estimada en BOB
    """
    real_cost = calculate_real_cost(
        usd_bob_cost=usd_bob_cost,
        price_usd_usdt=price_usd_usdt,
        deposit_fee=deposit_fee,
        transfer_fee=transfer_fee,
    )

    margin = calculate_margin(
        price_usdt_bob=price_usdt_bob,
        real_cost_usdt=real_cost,
    )

    profit = calculate_estimated_profit(
        capital_bob=capital_bob,
        margin_percent=margin,
    )

    result = {
        "real_cost": round(real_cost, 4),
        "buy_price": round(price_usd_usdt, 4),
        "sell_price": round(price_usdt_bob, 4),
        "margin_percent": round(margin, 2),
        "capital": round(capital_bob, 2),
        "estimated_profit": round(profit, 2),
    }

    logger.info(
        "Cálculo completo: costo_real=%.4f, compra=%.4f, venta=%.4f, "
        "margen=%.2f%%, capital=%.2f, ganancia=%.2f",
        result["real_cost"],
        result["buy_price"],
        result["sell_price"],
        result["margin_percent"],
        result["capital"],
        result["estimated_profit"],
    )

    return result
