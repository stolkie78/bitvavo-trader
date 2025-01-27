
# Bitvavo Scalper Bot

This project is a high-frequency trading bot designed to trade cryptocurrency pairs on Bitvavo. 
The bot utilizes various configurations and parameters to optimize its trading strategy and execution.

---

## Table of Contents
1. [Overview](#overview)
2. [Configuration Parameters](#configuration-parameters)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Logging and State Management](#logging-and-state-management)

---

## Overview

The bot uses real-time data to make buy and sell decisions based on indicators like RSI (Relative Strength Index), profit thresholds, and stop-loss settings. You can customize its behavior extensively through the configuration file.

---

## Configuration Parameters

Below is a detailed explanation of each configuration parameter:

### General Settings
- **`BOT_NAME`**: A unique name for the bot, used in logs and Slack notifications.
- **`PAIRS`**: A list of trading pairs (e.g., `BTC-EUR`, `ETH-EUR`) to monitor and trade.
- **`TOTAL_BUDGET`**: The total amount (in EUR) allocated for trading across all pairs.
- **`DAILY_TARGET`**: Profit target in EUR. Once this target is reached, the bot stops trading for the day.
- **`TRADING_PERIOD_HOURS`**: The interval (in hours) after which the bot resets its daily trading state.
- **`CHECK_INTERVAL`**: Time (in seconds) between each cycle of price checks and decision-making.

---

### Trading Logic
- **`WINDOW_SIZE`**: Number of recent data points (candlesticks) used for RSI calculation.
- **`RETURN_THRESHOLD`**: Percentage increase required before re-evaluating portfolio rebalance.
- **`TRADE_FEE_PERCENTAGE`**: The percentage fee taken by the exchange for each trade (e.g., 0.25% = `0.0025`).
- **`MINIMUM_PROFIT_PERCENTAGE`**: Minimum profit margin required to execute a trade.
- **`PRICE_DROP_THRESHOLD`**: The percentage drop in price considered before buying more (e.g., averaging down).
- **`PROFIT_THRESHOLD`**: Profit percentage target for selling a position.
- **`STOP_LOSS`**: Maximum allowable loss percentage before exiting a position.
- **`STOP_LOSS_RETRY_COUNT`**: Number of times the bot will hit the stop-loss threshold before executing a forced sell.
- **`BUY_THRESHOLD`**: RSI threshold below which a buy signal is triggered.
- **`SELL_THRESHOLD`**: RSI threshold above which a sell signal is triggered.

---

### Cost Management
- **`TRADING_COST`**: Total trading costs (fees + slippage) as a percentage. Used for conservative profit calculations.

---

### AI and Advanced Features
- **`USE_LIGHTGBM`**: Whether to use a LightGBM model for enhanced decision-making.
- **`LIGHTGBM_MODEL_PATH`**: Path to the saved LightGBM model file for predictions.

---

### Rebalancing
- **`REBALANCE_SETTINGS`**: Rebalancing configuration.
  - **`ENABLED`**: Enables or disables rebalancing.
  - **`REBALANCE_INTERVAL_HOURS`**: Time interval (in hours) between rebalancing operations.
  - **`REBALANCE_THRESHOLD_PERCENT`**: Percentage deviation required to trigger rebalancing.
  - **`PORTFOLIO_ALLOCATION`**: Percentage allocation for each trading pair.

---

### Logging and Notifications
- **`LOGGING`**: Configuration for logging.
  - **`LOG_TO_FILE`**: Whether to log events to a file.
  - **`FILE_PATH`**: Path to the log file.
- **`NOTIFICATIONS`**: Slack notification settings.
  - **`NOTIFY_ON_TRADE`**: Sends notifications when a trade is executed.
  - **`NOTIFY_ON_REBALANCE`**: Sends notifications when rebalancing occurs.

---

## Docker Deployment

To run the bot in a Docker container, use the following command:
```bash
docker run --rm -v $(pwd)/config:/app/config bitvavo-scalper:latest --config /app/config/scalper.json
```

---

## Kubernetes Deployment

An example Kubernetes deployment can be found in the `kubernetes/` directory. Here's a basic deployment example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bitvavo-scalper
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bitvavo-scalper
  template:
    metadata:
      labels:
        app: bitvavo-scalper
    spec:
      containers:
      - name: bitvavo-scalper
        image: bitvavo-scalper:latest
        env:
        - name: BOT_NAME
          value: "bitvavo-scalper"
        args:
        - "--config"
        - "/app/config/scalper.json"
```

---

## Logging and State Management

The bot logs all activities to a specified file and maintains its state in JSON files stored in the `/data` directory. This ensures that the bot can resume its operations seamlessly after a restart.

- **Trades** are logged in `trades.json`.
- **Portfolio** is logged in `portfolio.json`.

---

Feel free to customize the configuration to optimize the bot for your trading strategy!
