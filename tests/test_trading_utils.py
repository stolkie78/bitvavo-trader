import pandas as pd
from ta.momentum import RSIIndicator
from bot.trading_utils import TradingUtils


def test_calculate_rsi_matches_ta():
    prices = [float(i) for i in range(1, 30)]
    result = TradingUtils.calculate_rsi(prices, 14)
    expected = RSIIndicator(pd.Series(prices), window=14).rsi().iloc[-1]
    assert abs(result - expected) < 1e-6


def test_calculate_volume_change():
    volumes = [10.0] * 10 + [20.0]
    result = TradingUtils.calculate_volume_change(volumes)
    vol_series = pd.Series(volumes)
    expected_ma = vol_series.rolling(window=10).mean().iloc[-1]
    expected = vol_series.iloc[-1] / expected_ma
    assert result == expected


def test_calculate_volume_change_insufficient():
    assert TradingUtils.calculate_volume_change([1, 2, 3]) is None


def test_calculate_support_resistance():
    prices = list(range(1, 21))
    support, resistance = TradingUtils.calculate_support_resistance(prices, 20)
    assert support == 1
    assert resistance == 20


def test_calculate_support_resistance_insufficient():
    result = TradingUtils.calculate_support_resistance([1, 2, 3], 5)
    assert result == (None, None)
