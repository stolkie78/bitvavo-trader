
# Bitvavo Trader Bot

The Bitvavo Trader Bot is an automated cryptocurrency trading bot designed to execute rapid buy and sell operations based on predefined conditions such as RSI thresholds, profit targets, and LightGBM-based AI predictions. This bot is capable of tracking multiple cryptocurrency pairs and includes features like trade logging, restartable states, and Slack notifications.

## Features

- **Real-time Trading:** Executes buy/sell actions based on RSI and other indicators.
- **Restartable State:** Keeps track of open positions and portfolio in JSON files to ensure continuity after a restart.
- **AI Predictions:** Uses LightGBM to predict potential market trends for informed decisions.
- **Trade Logging:** Logs all trades (buy/sell) and states to JSON files for later analysis.
- **Slack Notifications:** Sends updates about trades, errors, and other significant events to Slack.
- **Configurable Parameters:** All thresholds and parameters are configurable through JSON files.

## File Structure

```
bitvavo-trader/
├── bot/
│   ├── trader.py        # Main bot script
│   ├── state_manager.py       # Manages trading state and positions
│   ├── trading_utils.py       # Utility functions for trading
│   ├── config_loader.py       # Handles loading and validation of configuration files
│   ├── logging_facility.py    # Handles console and Slack logging
├── config/
│   ├── bitvavo.json           # API credentials and general settings
│   ├── slack.json             # Slack webhook configuration
│   ├── top_5_crypto_config.json # Example configuration for top 5 cryptos
│   ├── top_10_meme_config.json  # Example configuration for 10 meme coins
├── data/
│   ├── trades.json            # Logs all trades in JSON format
│   ├── portfolio.json         # Stores current portfolio state
├── README.md                  # Detailed documentation
├── Dockerfile                 # Dockerfile for containerization
├── requirements.txt           # Python dependencies
├── run.sh                     # Script to start the bot
├── build.sh                   # Script to build Docker images
```

## State Management

The bot maintains a restartable state by storing:
1. **Trades:** Logged in `data/trades.json` for every buy/sell action.
2. **Portfolio:** Stored in `data/portfolio.json` to keep track of open positions.

These files allow the bot to resume trading without losing its current portfolio or trade history.

## Configuration

### General Configuration Parameters

| Parameter                  | Description                                            |
|----------------------------|--------------------------------------------------------|
| `PAIRS`                    | List of trading pairs (e.g., `BTC-EUR`, `ETH-EUR`)     |
| `RSI_BUY_THRESHOLD`        | RSI value below which the bot considers buying         |
| `RSI_SELL_THRESHOLD`       | RSI value above which the bot considers selling        |
| `TRADE_FEE_PERCENTAGE`     | Fee percentage applied to each trade                   |
| `DAILY_TARGET`             | Daily profit target; bot stops trading upon reaching it|
| `SLACK_ENABLED`            | Enables/disables Slack notifications                  |
| `MODEL_ENABLED`            | Enables/disables AI-based trading                     |

### Example Config: `top_5_crypto_config.json`
```json
{
    "PAIRS": ["BTC-EUR", "ETH-EUR", "BNB-EUR", "XRP-EUR", "ADA-EUR"],
    "RSI_BUY_THRESHOLD": 30,
    "RSI_SELL_THRESHOLD": 70,
    "TRADE_FEE_PERCENTAGE": 0.25,
    "DAILY_TARGET": 50,
    "SLACK_ENABLED": true,
    "MODEL_ENABLED": true
}
```

### Slack Configuration: `slack.json`
```json
{
    "WEBHOOK_URL": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
}
```

### API Configuration: `bitvavo.json`
```json
{
    "API_KEY": "your_api_key",
    "API_SECRET": "your_api_secret",
    "API_URL": "https://api.bitvavo.com/v2"
}
```

## How to Use

### Prerequisites

1. Install Docker and Python (if not already installed).
2. Install necessary OS packages for Python libraries:
   ```bash
   apt-get update && apt-get install -y build-essential libssl-dev libffi-dev python3-dev
   ```
3. Install Python dependencies using `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Bot

#### Locally
```bash
python bot/trader.py --config config/top_5_crypto_config.json
```

#### With Docker
1. Build the Docker image:
   ```bash
   ./build.sh bitvavo-trader latest
   ```
2. Run the container:
   ```bash
   ./run.sh bitvavo-trader latest top_5_crypto_config
   ```

## Trade and Portfolio Logging

- **Trades:** Every trade is logged in `data/trades.json`. Example:
```json
[
    {
        "pair": "BTC-EUR",
        "type": "buy",
        "price": 93830.0,
        "quantity": 0.0212,
        "profit": null,
        "timestamp": "2025-01-27T12:03:47.498396"
    }
]
```

- **Portfolio:** The current portfolio state is logged in `data/portfolio.json`. Example:
```json
{
    "BTC-EUR": {"price": 93830.0, "quantity": 0.0212, "timestamp": "2025-01-27T12:03:47.498396"}
}
```

## Additional Features

- **Slack Notifications:**
  - Buy/Sell actions, errors, and daily summaries are sent to a Slack channel if `SLACK_ENABLED` is true.
- **AI Predictions:**
  - If `MODEL_ENABLED` is true, the bot uses LightGBM for predicting buy/sell opportunities.
- **Restartable Trading:**
  - The bot resumes from its last state using `portfolio.json`.

## FAQ

1. **What happens if the bot crashes?**
   - The bot resumes trading using the latest `portfolio.json` file.
2. **Can I use custom RSI thresholds?**
   - Yes, update the `RSI_BUY_THRESHOLD` and `RSI_SELL_THRESHOLD` in the config file.

## Future Enhancements

- Support for additional technical indicators.
- Enhanced AI model training with historical data.

---
**Note:** Use this bot responsibly and only trade with funds you can afford to lose. Cryptocurrency trading involves significant risk.
