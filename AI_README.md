# AI Trader — Crypto Tradingbot met Per Pair AI-Model

Deze repository bevat een geavanceerde AI-gedreven crypto tradingbot die handelt via de Bitvavo API. Elke trading pair wordt gestuurd door een eigen getraind AI-model, waardoor je nauwkeurige en datagedreven beslissingen kunt nemen op basis van technische indicatoren.

---

## ⚙️ AI Trader Workflow

1. **Candle data ophalen via Bitvavo API**
2. **Technische indicatoren berekenen** (RSI, MACD, EMA, ATR, Momentum, etc.)
3. **AI-model per pair doet koop-/verkoopbeslissing**
4. **StateManager verwerkt transacties en logt portfolio updates**

---

## 📁 Bestandsstructuur

```
├── bot/
│   ├── ai_trader.py                → Main bot (AI-only)
│   ├── ai_decider.py              → AI-beslissingsmodule per pair
│   ├── generate_training_data.py  → Genereert trainingsdata van Bitvavo candles
│   ├── train_model.py             → Trained model op CSV-featureset
│   ├── trading_utils.py           → Indicatorberekeningen
│   ├── state_manager.py           → Portfolio & tradebeheer
│   └── config/
│       └── aitrader.json          → Configuratiebestand per run
```

---

## 🔧 Voorbeeldconfiguratie (`aitrader.json`)

```json
{
  "PROFILE": "AITRADER",
  "PAIRS": ["XRP-EUR", "BTC-EUR"],
  "TOTAL_BUDGET": 10000,
  "PORTFOLIO_ALLOCATION": {
    "XRP-EUR": 50,
    "BTC-EUR": 50
  },
  "CANDLES": 60,
  "CANDLE_INTERVAL": "1h",
  "CHECK_INTERVAL": 900,
  "TRADE_FEE_PERCENTAGE": 0.25,
  "ALLOW_SELL": true,
  "MAX_TRADES_PER_PAIR": 2,
  "MINIMUM_PROFIT_PERCENTAGE": 1.0,
  "BUY_PROBABILITY_THRESHOLD": 0.8,
  "SELL_PROBABILITY_THRESHOLD": 0.8,
  "STOPLOSS_ATR_MULTIPLIER": 1.5,
  "DEMO_MODE": false,
  "PAIR_MODELS": {
    "XRP-EUR": "models/buy_model_xrp.pkl",
    "BTC-EUR": "models/buy_model_btc.pkl"
  }
}
```

---

## 📊 Trainingsdata genereren per pair
Gebruik historische candles om trainingsdata met technische features te genereren:

```bash
python bot/generate_training_data.py \
  --pair XRP-EUR \
  --limit 500 \
  --interval 1h \
  --output data/xrp_training.csv
```

---

## 🤖 AI-model trainen per pair
Train een RandomForest-model op de gegenereerde dataset:

```bash
python bot/train_model.py \
  --data data/xrp_training.csv \
  --output models/buy_model_xrp.pkl
```

Herhaal dit per trading pair (BTC-EUR, ETH-EUR, etc.).

---

## 🚀 Bot starten

```bash
python bot/ai_trader.py --config config/aitrader.json
```

---

## 📥 Indicatoren als AI-features
De AI gebruikt de volgende indicatoren:
- price
- rsi
- macd
- signal
- macd_diff
- ema_fast / ema_slow / ema_diff
- support / resistance / afstand tot support/resistance
- atr (volatiliteit)
- momentum
- volume_change
- macd_histogram

---

## 📌 Belangrijk
- Zorg dat elk model getraind is op data van zijn eigen pair.
- Zorg dat `PAIR_MODELS` correcte paden heeft.
- AI beslist volledig. RSI-thresholds zijn niet meer nodig.

---

Veel succes met je AI-driven trading! 💸
