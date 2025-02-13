
# Bitvavo Scalping Bot

The Bitvavo Scalping Bot is an automated cryptocurrency trading bot designed to execute rapid buy and sell operations based on predefined conditions such as RSI thresholds, profit targets, and LightGBM-based AI predictions. This bot is capable of tracking multiple cryptocurrency pairs and includes features like trade logging, restartable states, and Slack notifications.

## Features

- **Real-time Trading:** Executes buy/sell actions based on RSI and other indicators.
- **Restartable State:** Keeps track of open positions and portfolio in JSON files to ensure continuity after a restart.
- **AI Predictions:** Uses LightGBM to predict potential market trends for informed decisions.
- **Trade Logging:** Logs all trades (buy/sell) and states to JSON files for later analysis.
- **Slack Notifications:** Sends updates about trades, errors, and other significant events to Slack.
- **Configurable Parameters:** All thresholds and parameters are configurable through JSON files.

## File Structure

```
bitvavo-scalper/
├── bot/
│   ├── scalping_bot.py        # Main bot script
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
python bot/scalping_bot.py --config config/top_5_crypto_config.json
```

#### With Docker
1. Build the Docker image:
   ```bash
   ./build.sh bitvavo-scalper latest
   ```
2. Run the container:
   ```bash
   ./run.sh bitvavo-scalper latest top_5_crypto_config
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


# Crypto Scalping Bot

The Crypto Scalping Bot is an asynchronous trading system designed for dynamic crypto scalping using the Bitvavo API. The bot integrates technical indicators (RSI, EMA, ATR) with dynamic stop-loss and portfolio rebalancing strategies. It supports multiple trading profiles, each tailored for different timeframes: day trading, week trading, and month trading.

## Profiles

The bot uses JSON configuration files to define its behavior. Three sample profiles are provided:

- **day_trader.json** – Designed for short-term, high-frequency trading.
- **week_trader.json** – Configured for trades that are held over several days.
- **month_trader.json** – Tuned for longer-term positions held over weeks or months.

Each profile has a total budget of 10,000 EUR and distinct settings that affect the sensitivity of indicators, risk management, and portfolio rebalancing.

## Configuration Parameters

Below is a description of each parameter used in the configuration files:

- **PROFILE**  
  *Description:* The name of the trading profile. Used for logging and identifying the bot's operating mode.  
  *Example:* `"DAY_TRADER"`, `"WEEK_TRADER"`, `"MONTH_TRADER"`

- **TOTAL_BUDGET**  
  *Description:* The total amount of capital available for trading.  
  *Example:* `10000.0` (EUR)

- **PAIRS**  
  *Description:* A list of trading pairs that the bot will monitor and trade.  
  *Example:* `["BTC-EUR", "ETH-EUR", "SHIB-EUR"]`

- **TRADE_FEE_PERCENTAGE**  
  *Description:* The percentage fee charged on each trade (both buy and sell orders).  
  *Example:* `0.33`

- **CHECK_INTERVAL**  
  *Description:* The time interval (in seconds) between each cycle of the bot’s main loop. Shorter intervals are typical for day trading.  
  *Example:* `5` for day trading, `10` for week trading, `20` for month trading.

- **RSI_POINTS**  
  *Description:* The number of data points used to calculate the Relative Strength Index (RSI). A lower value produces a more responsive indicator.  
  *Example:* `14` for day trading, `20` for week trading, `30` for month trading.

- **RSI_INTERVAL**  
  *Description:* The time interval for each RSI candle. This affects the responsiveness of the RSI indicator.  
  *Example:* `"1m"` (1 minute) for day trading, `"5m"` (5 minutes) for week trading, `"1h"` (1 hour) for month trading.

- **RSI_BUY_THRESHOLD**  
  *Description:* The RSI value below which the bot considers a buying opportunity.  
  *Example:* `30` for day trading, `35` for week trading, `40` for month trading.

- **RSI_SELL_THRESHOLD**  
  *Description:* The RSI value above which the bot considers a selling opportunity.  
  *Example:* `70` for day trading, `65` for week trading, `60` for month trading.

- **EMA_PROFILES**  
  *Description:* A dictionary defining window sizes for various Exponential Moving Average (EMA) profiles.  
  *Example:*  

  ```json
  {
    "ULTRASHORT": 9,
    "SHORT": 21,
    "MEDIUM": 50,
    "LONG": 200
  }
