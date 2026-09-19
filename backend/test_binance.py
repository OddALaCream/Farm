import importlib
import os
import tempfile
import unittest
from unittest.mock import patch

import database
from binance import get_best_buy_price


class TestBinanceSkrillFiltering(unittest.TestCase):
    @patch("binance.fetch_p2p_ads")
    def test_get_best_buy_price_keeps_only_skrill_when_alias_is_used(self, mock_fetch):
        mock_fetch.return_value = [
            {
                "price": 1.00,
                "payment_methods": ["Skrill", "Bank transfer"],
                "advertiser_name": "mixed",
            },
            {
                "price": 1.20,
                "payment_methods": ["Skrill"],
                "advertiser_name": "pure",
            },
        ]

        ad = get_best_buy_price("USD", "USDT", pay_types=["Skrill"])

        self.assertIsNotNone(ad)
        self.assertEqual(ad["advertiser_name"], "pure")
        self.assertEqual(ad["price"], 1.20)


class TestDatabaseStateRefresh(unittest.TestCase):
    def test_last_operation_updates_after_new_save(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "arbitrage.db")
            os.environ["DB_PATH"] = db_path
            try:
                importlib.reload(database)
                database.init_db()
                database.save_operation(
                    precio_usdt_usd=1.0100,
                    precio_usdt_bob=12.5000,
                    costo_real=12.3000,
                    margen=5.2,
                    capital=10000,
                    ganancia_estimada=500.0,
                )
                database.save_operation(
                    precio_usdt_usd=1.0200,
                    precio_usdt_bob=12.6000,
                    costo_real=12.4000,
                    margen=7.5,
                    capital=10000,
                    ganancia_estimada=750.0,
                )

                last = database.get_last_operation()

                self.assertIsNotNone(last)
                self.assertEqual(last["precio_usdt_usd"], 1.02)
                self.assertEqual(last["margen"], 7.5)
            finally:
                os.environ.pop("DB_PATH", None)
                importlib.reload(database)


if __name__ == "__main__":
    unittest.main()
