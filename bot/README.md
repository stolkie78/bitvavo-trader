
# Bitvavo Scalping Bot

The **Bitvavo Scalping Bot** is an automated cryptocurrency trading bot designed to operate on the Bitvavo platform. The bot leverages technical indicators such as RSI and integrates AI models like LightGBM to make buying and selling decisions. It supports features like portfolio rebalancing, stop-loss settings, and Slack notifications for trade updates.

---

## Features

- **Multi-pair Trading**: Supports trading multiple pairs simultaneously.
- **Daily Target**: Stops trading once a specified profit target is reached.
- **Stop-Loss with Retry Count**: Prevents excessive losses by enforcing stop-loss limits with configurable retries.
- **AI Model Integration**: Utilizes LightGBM for advanced decision-making.
- **Portfolio Rebalancing**: Ensures the portfolio aligns with predefined allocations at regular intervals.
- **Slack Notifications**: Sends real-time updates for trade activities.
- **Logging**: Detailed logs for debugging and monitoring.

---

## Configuration

The bot is configured using a JSON file. Below is an explanation of the available parameters:

### General Settings

| Parameter                 | Description                                                                                   | Example             |
|---------------------------|-----------------------------------------------------------------------------------------------|---------------------|
| `BOT_NAME`                | Name of the bot for identification.                                                          | `"TOP5_SCALPING_BOT"` |
| `PAIRS`                   | List of trading pairs to operate on.                                                         | `["BTC-EUR", "ETH-EUR"]` |
| `TOTAL_BUDGET`            | Total budget for the bot, distributed across pairs.                                          | `5000.0`            |
| `DAILY_TARGET`            | Profit target in EUR. The bot stops trading upon reaching this target.                       | `50.0`              |
| `TRADING_PERIOD_HOURS`    | Duration (in hours) the bot will trade before resetting.                                      | `24`                |
| `CHECK_INTERVAL`          | Time interval (in seconds) between trading cycles.                                           | `10`                |

### Technical Settings

| Parameter                 | Description                                                                                   | Example             |
|---------------------------|-----------------------------------------------------------------------------------------------|---------------------|
| `WINDOW_SIZE`             | Number of price points used for RSI calculation.                                              | `3`                 |
| `RETURN_THRESHOLD`        | Threshold for ROI (percentage) to trigger rebalancing or logging.                             | `25.0`              |
| `TRADE_FEE_PERCENTAGE`    | Fee percentage for trades on the platform.                                                    | `0.25`              |
| `MINIMUM_PROFIT_PERCENTAGE` | Minimum profit percentage required for a sell operation.                                    | `1.0`               |
| `STOP_LOSS`               | Maximum loss percentage allowed before triggering a stop-loss.                                | `-5.0`              |
| `STOP_LOSS_RETRY_COUNT`   | Number of retries before enforcing a stop-loss.                                               | `3`                 |
| `BUY_THRESHOLD`           | RSI value below which the bot decides to buy.                                                 | `30.0`              |
| `SELL_THRESHOLD`          | RSI value above which the bot decides to sell.                                                | `70.0`              |

### AI Model Settings

| Parameter                 | Description                                                                                   | Example             |
|---------------------------|-----------------------------------------------------------------------------------------------|---------------------|
| `USE_LIGHTGBM`            | Enables LightGBM for decision-making if `true`.                                               | `true`              |
| `LIGHTGBM_MODEL_PATH`     | Path to the pre-trained LightGBM model.                                                       | `"./models/lightgbm_model.txt"` |

### Rebalancing Settings

| Parameter                 | Description                                                                                   | Example             |
|---------------------------|-----------------------------------------------------------------------------------------------|---------------------|
| `REBALANCE_SETTINGS.ENABLED` | Enables portfolio rebalancing.                                                             | `true`              |
| `REBALANCE_SETTINGS.REBALANCE_INTERVAL_HOURS` | Interval (in hours) for rebalancing.                                      | `24`                |
| `REBALANCE_SETTINGS.REBALANCE_THRESHOLD_PERCENT` | Percentage deviation allowed before triggering rebalancing.             | `10.0`              |
| `REBALANCE_SETTINGS.PORTFOLIO_ALLOCATION` | Portfolio allocation for each pair as percentages.                       | `{ "BTC-EUR": 40, "ETH-EUR": 30 }` |

### Logging and Notifications

| Parameter                 | Description                                                                                   | Example             |
|---------------------------|-----------------------------------------------------------------------------------------------|---------------------|
| `LOGGING.LOG_TO_FILE`     | Enables logging to a file if `true`.                                                         | `true`              |
| `LOGGING.FILE_PATH`       | Path to the log file.                                                                         | `"./logs/bot.log"`  |
| `NOTIFICATIONS.NOTIFY_ON_TRADE` | Sends notifications for trade activities.                                               | `true`              |
| `NOTIFICATIONS.NOTIFY_ON_REBALANCE` | Sends notifications for rebalancing events.                                         | `true`              |

---

## Installation

### Prerequisites

- Python 3.7 - 3.11
- Bitvavo API account with API key and secret.

### Python Dependencies

Install the required Python modules:
```bash
pip install -r requirements.txt
```

### OS Dependencies

For systems using LightGBM, ensure OpenMP is installed. On macOS, run:
```bash
brew install libomp
```

---

## Usage

### Starting the Bot

Run the bot with a specified configuration file:
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

## Development Notes

- Ensure the configuration file matches your trading preferences.
- Regularly monitor logs and adjust thresholds for optimal performance.
- Rebalance settings are crucial for maintaining portfolio integrity.

---

## Disclaimer

This bot is provided for educational purposes. Use it at your own risk. Ensure compliance with local regulations and perform adequate testing before deploying the bot in live environments.
