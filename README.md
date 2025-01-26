
# Bitvavo Scalping Bot

The **Bitvavo Scalping Bot** is an automated cryptocurrency trading bot designed to operate on the Bitvavo platform. This bot uses technical indicators such as RSI, integrates AI models like LightGBM for enhanced decision-making, and incorporates dynamic thresholds for buying and selling.

---

## Features

- **Multi-pair Trading**: Supports trading multiple pairs simultaneously.
- **Daily Target**: Stops trading once a specified profit target is reached.
- **Stop-Loss with Retry Count**: Prevents excessive losses by enforcing configurable stop-loss limits.
- **Dynamic Price Drop Detection**: Considers significant price drops before buying.
- **AI Model Integration**: Uses LightGBM for advanced decision-making.
- **Portfolio Rebalancing**: Maintains portfolio alignment with specified allocations.
- **Slack Notifications**: Sends real-time updates for trades and rebalancing activities.
- **Detailed Logging**: Provides comprehensive logs for debugging and monitoring.

---

## Configuration

The bot is configured using a JSON file. Below is an explanation of all the available parameters and how they influence the bot's behavior:

### General Settings

| Parameter                 | Description                                                                                   | Example             |
|---------------------------|-----------------------------------------------------------------------------------------------|---------------------|
| `BOT_NAME`                | Name of the bot for identification in logs and Slack notifications.                          | `"TOP5_SCALPING_BOT"` |
| `PAIRS`                   | List of trading pairs the bot will operate on.                                               | `["BTC-EUR", "ETH-EUR"]` |
| `TOTAL_BUDGET`            | Total trading budget distributed across pairs.                                               | `5000.0`            |
| `DAILY_TARGET`            | Profit target in EUR. The bot stops trading once this target is reached.                     | `50.0`              |
| `TRADING_PERIOD_HOURS`    | Total trading duration before resetting.                                                     | `24`                |
| `CHECK_INTERVAL`          | Time interval (in seconds) between trading cycles.                                           | `10`                |

### Technical Settings

| Parameter                 | Description                                                                                   | Example             |
|---------------------------|-----------------------------------------------------------------------------------------------|---------------------|
| `WINDOW_SIZE`             | Number of price points used for RSI calculation.                                              | `3`                 |
| `RETURN_THRESHOLD`        | Minimum ROI percentage to trigger rebalancing or logging.                                     | `25.0`              |
| `TRADE_FEE_PERCENTAGE`    | Platform's trade fee as a percentage of the trade value.                                      | `0.25`              |
| `MINIMUM_PROFIT_PERCENTAGE` | Minimum profit percentage required for a sell action.                                       | `1.0`               |
| `PRICE_DROP_THRESHOLD`    | Minimum percentage drop in price to consider before buying.                                   | `0.2`               |
| `STOP_LOSS`               | Maximum allowable loss percentage before enforcing a stop-loss.                               | `-5.0`              |
| `STOP_LOSS_RETRY_COUNT`   | Number of retries allowed before enforcing the stop-loss.                                     | `3`                 |
| `BUY_THRESHOLD`           | RSI value below which the bot decides to buy.                                                 | `30.0`              |
| `SELL_THRESHOLD`          | RSI value above which the bot decides to sell.                                                | `70.0`              |

### AI Model Settings

| Parameter                 | Description                                                                                   | Example             |
|---------------------------|-----------------------------------------------------------------------------------------------|---------------------|
| `USE_LIGHTGBM`            | Enables LightGBM for decision-making when set to `true`.                                      | `true`              |
| `LIGHTGBM_MODEL_PATH`     | File path to the pre-trained LightGBM model.                                                  | `"./models/lightgbm_model.txt"` |

### Rebalancing Settings

| Parameter                 | Description                                                                                   | Example             |
|---------------------------|-----------------------------------------------------------------------------------------------|---------------------|
| `ENABLED`                 | Enables portfolio rebalancing when set to `true`.                                             | `true`              |
| `REBALANCE_INTERVAL_HOURS` | Time interval (in hours) for rebalancing.                                                    | `24`                |
| `REBALANCE_THRESHOLD_PERCENT` | Percentage deviation allowed before triggering rebalancing.                                | `10.0`              |
| `PORTFOLIO_ALLOCATION`    | Allocation percentages for each trading pair.                                                 | `{ "BTC-EUR": 40, "ETH-EUR": 30 }` |

### Logging and Notifications

| Parameter                 | Description                                                                                   | Example             |
|---------------------------|-----------------------------------------------------------------------------------------------|---------------------|
| `LOG_TO_FILE`             | Logs all trading activity to a file when set to `true`.                                       | `true`              |
| `FILE_PATH`               | Path to the log file.                                                                         | `"./logs/top5_scalping_bot.log"`  |
| `NOTIFY_ON_TRADE`         | Sends notifications for every trade action.                                                   | `true`              |
| `NOTIFY_ON_REBALANCE`     | Sends notifications when rebalancing occurs.                                                  | `true`              |

---

## How the Bot Works

### **Buying Logic**
The bot decides to buy a pair if:
1. The **RSI value** is less than or equal to the `BUY_THRESHOLD` (e.g., 30.0).
2. The **price has dropped significantly**, meeting the `PRICE_DROP_THRESHOLD` (e.g., a 0.2% drop).
3. The bot is not already holding a position for the pair.

If all conditions are met, the bot executes a buy order and logs the action.

### **Selling Logic**
The bot decides to sell a pair if:
1. The **RSI value** is greater than or equal to the `SELL_THRESHOLD` (e.g., 70.0).
2. The expected profit is above the `MINIMUM_PROFIT_PERCENTAGE` (e.g., 1.0%).
3. The bot is currently holding a position for the pair.

If these conditions are met, the bot executes a sell order and calculates the profit.

---

## Installation

### Prerequisites

- Python version 3.7 to 3.11
- A Bitvavo API account with API key and secret.

### Python Dependencies

Install the required Python packages:
```bash
pip install -r requirements.txt
```

### OS Dependencies

If using LightGBM, ensure OpenMP is installed. On macOS, install it using:
```bash
brew install libomp
```

---

## Running the Bot

### Starting the Bot

Run the bot with the specified configuration file:
```bash
python bot/scalping_bot.py --config config/top_5_crypto_config.json
```

### Example Configuration File

```json
{
    "BOT_NAME": "TOP5_SCALPING_BOT",
    "PAIRS": ["BTC-EUR", "ETH-EUR", "BNB-EUR", "XRP-EUR", "ADA-EUR"],
    "TOTAL_BUDGET": 5000.0,
    "DAILY_TARGET": 50.0,
    "TRADING_PERIOD_HOURS": 24,
    "CHECK_INTERVAL": 10,
    "WINDOW_SIZE": 3,
    "RETURN_THRESHOLD": 25.0,
    "TRADE_FEE_PERCENTAGE": 0.25,
    "MINIMUM_PROFIT_PERCENTAGE": 1.0,
    "PRICE_DROP_THRESHOLD": 0.2,
    "STOP_LOSS": -5.0,
    "STOP_LOSS_RETRY_COUNT": 3,
    "BUY_THRESHOLD": 30.0,
    "SELL_THRESHOLD": 70.0,
    "USE_LIGHTGBM": true,
    "LIGHTGBM_MODEL_PATH": "./models/lightgbm_model.txt",
    "REBALANCE_SETTINGS": {
        "ENABLED": true,
        "REBALANCE_INTERVAL_HOURS": 24,
        "REBALANCE_THRESHOLD_PERCENT": 10.0,
        "PORTFOLIO_ALLOCATION": {
            "BTC-EUR": 40,
            "ETH-EUR": 30,
            "BNB-EUR": 15,
            "XRP-EUR": 10,
            "ADA-EUR": 5
        }
    },
    "LOGGING": {
        "LOG_TO_FILE": true,
        "FILE_PATH": "./logs/top5_scalping_bot.log"
    },
    "NOTIFICATIONS": {
        "NOTIFY_ON_TRADE": true,
        "NOTIFY_ON_REBALANCE": true
    }
}
```

---

## Disclaimer

This bot is for educational purposes only. Use it at your own risk and ensure compliance with all relevant regulations.
