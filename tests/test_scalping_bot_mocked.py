import unittest
from unittest.mock import MagicMock, patch
import json
import os
from datetime import datetime
from trader import TraderBot
from config_loader import ConfigLoader
from state_manager import StateManager
from trading_utils import TradingUtils
from logging_facility import LoggingFacility
from bitvavo_client import bitvavo

class TestTraderBotWithMocking(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """ Set up testomgeving en laad testconfiguratie met gemockte API. """
        cls.config_path = "test_config.json"
        cls.test_config = {
            "PROFILE": "TRADER",
            "TOTAL_BUDGET": 10000.0,
            "PAIRS": ["BTC-EUR", "ETH-EUR"],
            "TRADE_FEE_PERCENTAGE": 0.1,
            "CHECK_INTERVAL": 1,
            "RSI_POINTS": 14,
            "RSI_INTERVAL": "1M",
            "RSI_BUY_THRESHOLD": 30,
            "RSI_SELL_THRESHOLD": 70,
            "EMA_PROFILE": "MEDIUM",
            "ATR_PERIOD": 14,
            "ATR_MULTIPLIER": 1.5,
            "RISK_PERCENTAGE": 0.01,
            "STOP_LOSS_PERCENTAGE": -5,
            "STOP_LOSS_MAX_RETRIES": 3,
            "STOP_LOSS_WAIT_TIME": 1,
            "MAX_TRADES_PER_PAIR": 1,
            "MINIMUM_PROFIT_PERCENTAGE": 0.5,
            "MAX_DRAWDOWN_PERCENTAGE": -20.0,
            "DRAWDOWN_RECOVERY_TIME": 5,
            "DEMO_MODE": True
        }

        # Set up dependencies
        cls.logger = LoggingFacility(cls.test_config)
        
        # Mock Bitvavo API
        cls.mock_bitvavo = MagicMock()
        cls.mock_bitvavo.getTickerPrice = MagicMock(return_value={"price": "50000"})
        
        # Mock state managers
        cls.state_managers = {
            pair: StateManager(pair, cls.logger, cls.mock_bitvavo, demo_mode=True, bot_name="TESTBOT")
            for pair in cls.test_config["PAIRS"]
        }

        # Start bot in testmodus
        cls.bot = TraderBot(cls.test_config, cls.logger, cls.state_managers, cls.mock_bitvavo, None)

    def test_load_config(self):
        """ Test of de configuratie correct wordt geladen. """
        self.assertEqual(self.bot.config["PROFILE"], "TRADER")
        self.assertIn("BTC-EUR", self.bot.config["PAIRS"])

    def test_portfolio_initialization(self):
        """ Test of de portfolio initialisatie correct verloopt. """
        self.bot.initialize_portfolio()
        self.assertTrue(len(self.bot.pair_budgets) > 0)
        self.assertAlmostEqual(sum(self.bot.pair_budgets.values()), self.bot.config["TOTAL_BUDGET"], delta=1)

    def test_dynamic_portfolio_rebalancing(self):
        """ Test of de portfolioverdeling correct wordt herverdeeld. """
        self.bot.pair_budgets["BTC-EUR"] *= 0.8  # Simuleer verlies
        self.bot.rebalance_portfolio()
        self.assertGreater(self.bot.pair_budgets["ETH-EUR"], self.bot.config["TOTAL_BUDGET"] / 2)

    def test_drawdown_protection(self):
        """ Test of een asset gepauzeerd wordt bij een te grote drawdown. """
        self.bot.pair_budgets["BTC-EUR"] *= 0.7  # Simuleer zware drawdown
        self.bot.rebalance_portfolio()
        self.assertTrue(self.state_managers["BTC-EUR"].is_drawdown_blocked())

    def test_reactivation_after_drawdown(self):
        """ Test of een asset na een wachttijd weer wordt geactiveerd. """
        self.state_managers["BTC-EUR"].set_drawdown_blocked(datetime.now().timestamp() - 10)  # Simuleer tijdsverloop
        self.bot.rebalance_portfolio()
        self.assertFalse(self.state_managers["BTC-EUR"].is_drawdown_blocked())

    @patch("trading_utils.TradingUtils.fetch_current_price", return_value=50000)
    def test_trade_execution(self, mock_fetch_price):
        """ Test of de trade-logica correct werkt met een gemockte API. """
        self.bot.pair_budgets["BTC-EUR"] = 1000  # Simuleer voldoende budget
        price = mock_fetch_price()
        quantity = 0.01

        # Simuleer trade executie
        trade_success = self.state_managers["BTC-EUR"].buy_dynamic(price, quantity, self.bot.config["TRADE_FEE_PERCENTAGE"])
        self.assertTrue(trade_success)

    @classmethod
    def tearDownClass(cls):
        """ Opruimen na de tests. """
        if os.path.exists(cls.config_path):
            os.remove(cls.config_path)

if __name__ == "__main__":
    unittest.main()
