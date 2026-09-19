"""
Módulo de base de datos SQLite para almacenamiento de operaciones.

Gestiona la persistencia de datos de arbitraje incluyendo
precios, márgenes y alertas enviadas.
"""

import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "/app/data/arbitrage.db")


def _get_connection() -> sqlite3.Connection:
    """Obtiene una conexión a la base de datos SQLite."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Inicializa la base de datos creando las tablas necesarias."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                precio_usdt_usd REAL NOT NULL,
                precio_usdt_bob REAL NOT NULL,
                costo_real REAL NOT NULL,
                margen REAL NOT NULL,
                capital REAL NOT NULL,
                ganancia_estimada REAL NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                margen REAL NOT NULL,
                precio_usdt_usd REAL NOT NULL,
                precio_usdt_bob REAL NOT NULL,
                costo_real REAL NOT NULL,
                capital REAL NOT NULL,
                ganancia_estimada REAL NOT NULL,
                sent INTEGER DEFAULT 1
            )
        """)

        conn.commit()
        logger.info("Base de datos inicializada correctamente en %s", DB_PATH)

    except sqlite3.Error as e:
        logger.error("Error al inicializar la base de datos: %s", str(e))
        raise

    finally:
        conn.close()


def save_operation(
    precio_usdt_usd: float,
    precio_usdt_bob: float,
    costo_real: float,
    margen: float,
    capital: float,
    ganancia_estimada: float,
) -> int:
    """
    Guarda una operación de monitoreo en la base de datos.

    Returns:
        ID de la operación guardada.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute(
            """
            INSERT INTO operations
                (timestamp, precio_usdt_usd, precio_usdt_bob, costo_real,
                 margen, capital, ganancia_estimada)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                precio_usdt_usd,
                precio_usdt_bob,
                costo_real,
                margen,
                capital,
                ganancia_estimada,
            ),
        )

        conn.commit()
        operation_id = cursor.lastrowid

        logger.debug("Operación guardada con ID %d", operation_id)
        return operation_id

    except sqlite3.Error as e:
        logger.error("Error al guardar operación: %s", str(e))
        raise

    finally:
        conn.close()


def save_alert(
    margen: float,
    precio_usdt_usd: float,
    precio_usdt_bob: float,
    costo_real: float,
    capital: float,
    ganancia_estimada: float,
) -> int:
    """
    Guarda un registro de alerta enviada.

    Returns:
        ID de la alerta guardada.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute(
            """
            INSERT INTO alerts
                (timestamp, margen, precio_usdt_usd, precio_usdt_bob,
                 costo_real, capital, ganancia_estimada)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                margen,
                precio_usdt_usd,
                precio_usdt_bob,
                costo_real,
                capital,
                ganancia_estimada,
            ),
        )

        conn.commit()
        alert_id = cursor.lastrowid

        logger.info("Alerta guardada con ID %d", alert_id)
        return alert_id

    except sqlite3.Error as e:
        logger.error("Error al guardar alerta: %s", str(e))
        raise

    finally:
        conn.close()


def get_last_alert() -> Optional[dict]:
    """
    Obtiene la última alerta enviada.

    Returns:
        Diccionario con la última alerta o None si no hay alertas.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM alerts
            ORDER BY id DESC
            LIMIT 1
        """)

        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)

    except sqlite3.Error as e:
        logger.error("Error al obtener última alerta: %s", str(e))
        return None

    finally:
        conn.close()


def get_history(limit: int = 50) -> list[dict]:
    """
    Obtiene el historial de operaciones.

    Args:
        limit: Cantidad máxima de registros a retornar.

    Returns:
        Lista de operaciones ordenadas por fecha descendente.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM operations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    except sqlite3.Error as e:
        logger.error("Error al obtener historial: %s", str(e))
        return []

    finally:
        conn.close()
