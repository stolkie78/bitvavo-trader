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
