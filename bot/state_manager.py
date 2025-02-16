import os
import json
import threading
import time
from datetime import datetime
from bot.trading_utils import TradingUtils  # Ensure this import works correctly

class StateManager:
    _lock = threading.Lock()  # Lock to prevent race conditions

    def __init__(self, pair, logger, bitvavo, demo_mode=False, bot_name="TradingBot"):
        """
        Initialize the StateManager.

        Args:
            pair (str): The trading pair (e.g. 'BTC-EUR').
            logger: The logger used for logging.
            bitvavo: The Bitvavo API client.
            demo_mode (bool): If True, orders are placed in demo mode.
            bot_name (str): Bot name for logging.
        """
        self.pair = pair
        self.logger = logger
        self.bitvavo = bitvavo
        self.demo_mode = demo_mode
        self.bot_name = bot_name
        self.positions = []
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.trades_file = os.path.join(self.data_dir, "trades.json")
        self.portfolio = self.load_portfolio()

        # Ensure the data directory exists
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # Restore positions if they exist in the portfolio for this pair
        if self.pair in self.portfolio:
            stored = self.portfolio[self.pair]
            if isinstance(stored, list):
                self.positions = stored
            else:
                self.positions = [stored]

    def has_position(self):
        """Check if there is at least one open position for the pair."""
        self.portfolio = self.load_portfolio()  # Always load the fresh portfolio
        positions = self.portfolio.get(self.pair, [])
        if not isinstance(positions, list):
            positions = [positions]
        return len(positions) > 0

    def get_open_positions(self):
        """Return a list of open positions for the pair."""
        self.portfolio = self.load_portfolio()  # Ensure portfolio is up-to-date
        positions = self.portfolio.get(self.pair, [])
        if not isinstance(positions, list):
            positions = [positions]
        return positions

    def load_portfolio(self):
        """Load the entire portfolio from a JSON file."""
        if os.path.exists(self.portfolio_file) and os.path.getsize(self.portfolio_file) > 0:
            try:
                with open(self.portfolio_file, "r") as f:
                    self.portfolio = json.load(f)
                # Ensure positions for the pair are stored as a list
                if self.pair in self.portfolio:
                    stored = self.portfolio[self.pair]
                    if not isinstance(stored, list):
                        self.portfolio[self.pair] = [stored]
                return self.portfolio
            except (json.JSONDecodeError, IOError):
                self.logger.log(
                    f"[{self.bot_name}] 👽❗ Error loading portfolio.json, resetting file.",
                    to_console=True
                )
                return {}
        return {}

    def save_portfolio(self):
        """Save the portfolio to a JSON file."""
        with self._lock:  # Prevent race conditions
            try:
                with open(self.portfolio_file, "w") as f:
                    json.dump(self.portfolio, f, indent=4)
                self.portfolio = self.load_portfolio()  # Reload to confirm changes
                self.logger.log(
                    f"[{self.bot_name}] 👽 Portfolio updated: {json.dumps(self.portfolio, indent=4)}",
                    to_console=True
                )
            except Exception as e:
                self.logger.log(
                    f"[{self.bot_name}] 👽❌ Error saving portfolio: {e}", to_console=True)

    def adjust_quantity(self, quantity):
        """Adjust the quantity according to market requirements."""
        market_info = self.bitvavo.markets()
        for market in market_info:
            if market['market'] == self.pair:
                min_amount = float(market.get('minOrderInBaseAsset', 0.0))
                precision = int(market.get('decimalPlacesBaseAsset', 6))
                adjusted_quantity = max(min_amount, round(quantity, precision))
                return adjusted_quantity
        self.logger.log(
            f"[{self.bot_name}] ⚠️ Market info not found for {self.pair}. Returning original quantity.",
            to_console=True
        )
        return quantity

    def buy(self, price, budget, fee_percentage):
        """
        Execute a buy order and add a new position for the pair.
        Checks for sufficient funds before placing the order.
        """
        try:
            available_balance = TradingUtils.get_account_balance(
                self.bitvavo, asset="EUR")
        except Exception as e:
            self.logger.log(f"[{self.bot_name}] ❌ Error retrieving account balance: {e}",
                            to_console=True, to_slack=True)
            return

        if available_balance < budget:
            self.logger.log(
                f"[{self.bot_name}] ❌ Insufficient funds for {self.pair}. Required: {budget:.2f} EUR, available: {available_balance:.2f} EUR",
                to_console=True, to_slack=True
            )
            return

        quantity = (budget / price) * (1 - fee_percentage / 100)
        quantity = self.adjust_quantity(quantity)

        if quantity <= 0:
            self.logger.log(
                f"[{self.bot_name}] ❌ Invalid quantity for {self.pair}: {quantity}",
                to_console=True, to_slack=True
            )
            return

        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "buy", quantity, demo_mode=self.demo_mode
        )

        if order.get("status") == "demo" or "orderId" in order:
            new_position = {
                "price": price,
                "quantity": quantity,
                "spent": budget,
                "timestamp": datetime.now().isoformat()
            }
            if self.pair not in self.portfolio:
                self.portfolio[self.pair] = []
            elif not isinstance(self.portfolio[self.pair], list):
                self.portfolio[self.pair] = [self.portfolio[self.pair]]
            self.portfolio[self.pair].append(new_position)
            self.save_portfolio()
            self.log_trade("buy", price, quantity)
            self.logger.log(
                f"[{self.bot_name}] 👽 Bought {self.pair}: Price={price:.2f}, Quantity={quantity:.6f}",
                to_console=True, to_slack=True
            )
        else:
            self.logger.log(
                f"[{self.bot_name}] 👽 Failed to execute buy order for {self.pair}: {order}",
                to_console=True, to_slack=True
            )

    def sell(self, price, fee_percentage):
        """
        Execute a sell order for all open positions and remove them from the portfolio.
        """
        open_positions = self.get_open_positions()
        if not open_positions:
            self.logger.log(
                f"[{self.bot_name}] 👽 No position to sell for {self.pair}.", to_console=True)
            return

        for position in list(open_positions):
            self.sell_position(position, price, fee_percentage)


    def sell_position(self, position, price, fee_percentage):
        """
        Execute a sell order for a specific position and remove it from the portfolio.
        """
        open_positions = self.get_open_positions()
        if position not in open_positions:
            self.logger.log(
                f"[{self.bot_name}] ❌ No matching position to sell for {self.pair}.",
                to_console=True
            )
            return

        quantity = position.get("quantity", 0)
        quantity = self.adjust_quantity(quantity)
        if quantity <= 0:
            self.logger.log(
                f"[{self.bot_name}] ❌ Invalid quantity for {self.pair}: {quantity}",
                to_console=True,
                to_slack=True
            )
            return

        # ✅ Bereken de winst/verlies
        cost_basis = position.get("spent", position["price"] * quantity)
        revenue = price * quantity * (1 - fee_percentage / 100)
        estimated_profit = revenue - cost_basis

        # ✅ Plaats verkooporder
        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "sell", quantity, demo_mode=self.demo_mode)

        if order.get("status") == "demo" or "orderId" in order:
            order_id = order.get("orderId")
            actual_profit = None
            if order_id:
                actual_profit = self.get_actual_trade_profit(
                    order_id, position, fee_percentage)
            profit_to_log = actual_profit if actual_profit is not None else estimated_profit

            # ✅ Log en update portfolio
            self.log_trade("sell", price, quantity, profit=profit_to_log)
            if self.pair in self.portfolio and isinstance(self.portfolio[self.pair], list):
                try:
                    self.portfolio[self.pair].remove(position)
                except ValueError:
                    self.logger.log(
                        f"[{self.bot_name}] ❌ Position not found in portfolio for {self.pair}.",
                        to_console=True
                    )
            self.save_portfolio()
            self.pair_budgets[self.pair] += revenue  # ✅ Update budget na verkoop
            self.logger.log(
                f"[{self.bot_name}] 🔴 Sold {self.pair}: Price={price:.2f}, Profit={profit_to_log:.2f}",
                to_console=True, to_slack=False
            )
        else:
            self.logger.log(
                f"[{self.bot_name}] ❌ Failed to execute sell order for {self.pair}: {order}",
                to_console=True,
                to_slack=True
            )


    def sell_position_with_retry(self, position, current_price, fee_percentage, max_retries=3, wait_time=5):
        """
        Execute a Stoploss sell order for a specific position with a retry mechanism.
        If the available balance is lower than the position size, it adjusts the sell amount accordingly.
        """
        position_quantity = position.get("quantity", 0)
        position_quantity = self.adjust_quantity(position_quantity)
    
        if position_quantity <= 0:
            self.logger.log(
                f"[{self.bot_name}] ❌ Invalid quantity for {self.pair} during Stoploss sell: {position_quantity}",
                to_console=True, to_slack=True
            )
            return False
    
        # **Haal het daadwerkelijk beschikbare saldo op**
        base_asset = self.pair.split("-")[0]
        actual_balance = TradingUtils.get_account_balance(
            self.bitvavo, asset=base_asset)
    
        # **Verkoop alleen wat beschikbaar is**
        sell_quantity = min(position_quantity, actual_balance)
    
        if sell_quantity <= 0:
            self.logger.log(
                f"[{self.bot_name}] ❌ Cannot sell {self.pair}, zero balance available.",
                to_console=True, to_slack=True
            )
            return False
    
        cost_basis = position.get("spent", position["price"] * sell_quantity)
    
        for attempt in range(1, max_retries + 1):
            revenue = current_price * sell_quantity * (1 - fee_percentage / 100)
            profit = revenue - cost_basis
    
            self.logger.log(
                f"[{self.bot_name}] ⛔️ {self.pair}: Stoploss attempt {attempt}: Trying to sell {sell_quantity:.6f} at {current_price:.2f} (Profit: {profit:.2f})",
                to_console=True
            )
    
            order = TradingUtils.place_order(
                self.bitvavo, self.pair, "sell", sell_quantity, demo_mode=self.demo_mode
            )
    
            if order.get("status") == "demo" or "orderId" in order:
                executed_quantity = order.get("filledAmount", sell_quantity)
    
                # **🚀 Controleer of de order slechts gedeeltelijk is uitgevoerd**
                if executed_quantity < sell_quantity:
                    self.logger.log(
                        f"[{self.bot_name}] ⚠️ Partial sell detected for {self.pair}: Expected {sell_quantity}, executed {executed_quantity}.",
                        to_console=True
                    )
                    sell_quantity = executed_quantity  # Pas aan naar wat daadwerkelijk verkocht is
    
                self.log_trade("sell", current_price, sell_quantity, profit)
    
                # **✅ Update de portfolio correct**
                if self.pair in self.portfolio and isinstance(self.portfolio[self.pair], list):
                    try:
                        for pos in self.portfolio[self.pair]:
                            if pos["quantity"] == position["quantity"]:  # Zoek de juiste positie
                                # Verminder alleen de verkochte hoeveelheid
                                pos["quantity"] -= sell_quantity
                                if pos["quantity"] <= 0:
                                    # Verwijder als alles verkocht is
                                    self.portfolio[self.pair].remove(pos)
                                break
                    except ValueError:
                        self.logger.log(
                            f"[{self.bot_name}] ❌ Position not found in portfolio for {self.pair}.",
                            to_console=True
                        )
    
                self.save_portfolio()
                self.logger.log(
                    f"[{self.bot_name}] ✅ Stoploss sold {self.pair}: Price={current_price:.2f}, Quantity={sell_quantity:.6f}, Profit={profit:.2f}",
                    to_console=True, to_slack=False
                )
                return True
            else:
                self.logger.log(
                    f"[{self.bot_name}] 👽 Stoploss sell attempt {attempt} failed for {self.pair}: {order}",
                    to_console=True
                )
                time.sleep(wait_time)
    
        self.logger.log(
            f"[{self.bot_name}] ❌ Stoploss sell failed for {self.pair} after {max_retries} attempts.",
            to_console=True
        )
        return False


    def calculate_profit(self, current_price, fee_percentage):
        """
        Calculate aggregated profit or loss for all open positions.
        """
        open_positions = self.get_open_positions()
        if not open_positions:
            self.logger.log(
                f"[{self.bot_name}] ❌ No active position for {self.pair}. Skipping profit calculation.",
                to_console=True
            )
            return None

        total_cost = 0
        total_revenue = 0
        for position in open_positions:
            quantity = position.get("quantity", 0)
            cost_basis = position.get("spent", position["price"] * quantity)
            revenue = current_price * quantity * (1 - fee_percentage / 100)
            total_cost += cost_basis
            total_revenue += revenue
        profit = total_revenue - total_cost
        return (profit / total_cost) * 100 if total_cost != 0 else 0

    def calculate_profit_for_position(self, position, current_price, fee_percentage):
        """
        Calculate the profit or loss for a specific position.
        """
        quantity = position.get("quantity", 0)
        cost_basis = position.get("spent", position["price"] * quantity)
        revenue = current_price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis
        return (profit / cost_basis) * 100 if cost_basis != 0 else 0

    def log_trade(self, trade_type, price, quantity, profit=None):
        """
        Log trade details to a JSON file.
        """
        trade = {
            "pair": self.pair,
            "type": trade_type,
            "price": price,
            "quantity": quantity,
            "timestamp": datetime.now().isoformat()
        }
        if trade_type.lower() == "sell" and profit is not None:
            trade["profit_eur"] = profit

        try:
            if not os.path.exists(self.trades_file):
                with open(self.trades_file, "w") as f:
                    json.dump([trade], f, indent=4)
            else:
                with open(self.trades_file, "r") as f:
                    trades = json.load(f)
                trades.append(trade)
                with open(self.trades_file, "w") as f:
                    json.dump(trades, f, indent=4)
        except Exception as e:
            self.logger.log(
                f"[{self.bot_name}] 👽❌ Error logging trade: {e}", to_console=True)


    def get_actual_trade_profit(self, order_id, position, fee_percentage):
        """
        Retrieve actual order details and calculate true profit.
        """
        try:
            # Voeg self.pair toe als market argument
            order_details = TradingUtils.get_order_details(
                self.bitvavo, self.pair, order_id)
    
            total_executed_value = 0.0
            total_fee = 0.0
    
            for trade in order_details.get("trades", []):
                trade_price = float(trade.get("price", 0))
                trade_quantity = float(trade.get("quantity", 0))
                fee = trade.get("fee")
                if fee is not None:
                    fee = float(fee)
                else:
                    fee = trade_price * trade_quantity * (fee_percentage / 100)
                total_executed_value += trade_price * trade_quantity
                total_fee += fee
    
            cost_basis = position.get(
                "spent", position["price"] * position["quantity"])
            actual_profit = total_executed_value - cost_basis - total_fee
            return actual_profit
        except Exception as e:
            self.logger.log(
                f"[{self.bot_name}] ❌ Error retrieving trade details for order {order_id}: {e}",
                to_console=True
            )
            return None


    def buy_dynamic(self, price, quantity, fee_percentage, pair_budgets):
        """
        Execute a buy order with the dynamically calculated quantity, ensuring it fits within budget.
        """
        try:
            available_balance = TradingUtils.get_account_balance(
                self.bitvavo, asset="EUR")
        except Exception as e:
            self.logger.log(
                f"[{self.bot_name}] ❌ Error retrieving account balance: {e}",
                to_console=True,
                to_slack=True
            )
            return
    
        # ✅ Haal het toegekende budget op voor deze trading pair
        allocated_budget = pair_budgets.get(self.pair, 0)
        if allocated_budget <= 0:
            self.logger.log(
                f"[{self.bot_name}] ❌ No budget allocated for {self.pair}.",
                to_console=True,
                to_slack=True
            )
            return
    
        # ✅ Controleer of er genoeg budget is voor de aankoop
        cost = price * quantity
        if cost > allocated_budget:
            self.logger.log(
                f"[{self.bot_name}] ❌ Not enough budget for {self.pair}. Needed: {cost:.2f}, Available: {allocated_budget:.2f}",
                to_console=True,
                to_slack=True
            )
            return
    
        quantity = self.adjust_quantity(quantity)
        if quantity <= 0:
            self.logger.log(
                f"[{self.bot_name}] ❌ Invalid quantity for {self.pair}: {quantity}",
                to_console=True,
                to_slack=True
            )
            return
    
        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "buy", quantity, demo_mode=self.demo_mode)
    
        if order.get("status") == "demo" or "orderId" in order:
            new_position = {
                "price": price,
                "quantity": quantity,
                "spent": cost,
                "timestamp": datetime.now().isoformat()
            }
            if self.pair not in self.portfolio:
                self.portfolio[self.pair] = []
            elif not isinstance(self.portfolio[self.pair], list):
                self.portfolio[self.pair] = [self.portfolio[self.pair]]
            self.portfolio[self.pair].append(new_position)
            self.save_portfolio()
            self.log_trade("buy", price, quantity)
            self.logger.log(
                f"[{self.bot_name}] 👽 Bought {self.pair}: Price={price:.2f}, Quantity={quantity:.6f}",
                to_console=True,
                to_slack=True
            )
            # ✅ Trek het bestede bedrag af van het budget
            pair_budgets[self.pair] -= cost
        else:
            self.logger.log(
                f"[{self.bot_name}] 👽 Failed to execute buy order for {self.pair}: {order}",
                to_console=True,
                to_slack=True
            )

    def check_stop_loss(self, current_price, fee_percentage, atr_value=None, atr_multiplier=1.5, stop_loss_percentage=-5, max_retries=3, wait_time=5):
        """
        Checks if any open position should trigger a Stoploss.
        For each open position, calculates a dynamic Stoploss:
        If atr_value is provided: dynamic_stoploss = position["price"] - (atr_value * atr_multiplier)
        Else: uses stop_loss_percentage.
        If current_price falls below the threshold, attempts to sell via a retry mechanism.
        """
        open_positions = self.get_open_positions()
        for position in open_positions:
            if atr_value is not None:
                dynamic_stoploss = position["price"] - \
                    (atr_value * atr_multiplier)
            else:
                dynamic_stoploss = position["price"] * \
                    (1 + stop_loss_percentage / 100)
            if current_price <= dynamic_stoploss:
                self.logger.log(
                    f"⛔️ {self.pair}: Stoploss triggered: current price {current_price:.2f} is below {dynamic_stoploss:.2f}",
                    to_slack=True
                )
                success = self.sell_position_with_retry(
                    position, current_price, fee_percentage, max_retries, wait_time)
                if success:
                    self.logger.log(
                        f"✅ {self.pair}: Stoploss sell succeeded at {current_price:.2f}", to_slack=True)
                else:
                    self.logger.log(
                        f"❌ {self.pair}: Stoploss sell failed, retrying...", to_slack=True)

    @staticmethod
    def log_portfolio_distribution(pair_budgets, logger, action=""):
        """
        Logs the portfolio distribution as percentages.
        """
        total_budget = sum(pair_budgets.values())
        distribution = {
            pair: f"{(pair_budgets[pair] / total_budget) * 100:.2f}%" for pair in pair_budgets}
        logger.log(
            f"📊 Portfolio distribution after {action}: {json.dumps(distribution, indent=2)}", to_slack=True)

    @staticmethod
    def initialize_portfolio(config, data_dir, logger):
        """
        Initializes the dynamic portfolio allocation.
        If a portfolio_alloc.json exists, it is loaded; otherwise, an even split is used.
        Returns the pair_budgets dictionary.
        """
        portfolio_alloc_file = os.path.join(data_dir, "portfolio_alloc.json")
        total_budget = config.get("TOTAL_BUDGET", 10000.0)

        if os.path.exists(portfolio_alloc_file):
            try:
                with open(portfolio_alloc_file, "r") as f:
                    allocation_data = json.load(f)
                    if "pair_budgets" in allocation_data:
                        pair_budgets = allocation_data["pair_budgets"]
                        logger.log(
                            "✅ Portfolio allocation loaded from file.", to_slack=True)
                        StateManager.log_portfolio_distribution(
                            pair_budgets, logger, "startup")
                        return pair_budgets
            except Exception as e:
                logger.log(
                    f"❌ Error loading portfolio allocation: {e}", to_slack=True)

        pairs = config["PAIRS"]
        num_pairs = len(pairs)
        pair_budgets = {pair: total_budget / num_pairs for pair in pairs}
        logger.log(
            f"🔄 Starting portfolio allocation: {json.dumps(pair_budgets, indent=2)}", to_slack=True)
        StateManager.log_portfolio_distribution(
            pair_budgets, logger, "startup")
        return pair_budgets


    @staticmethod
    def rebalance_portfolio(config, state_managers, pair_budgets, logger):
        """
        Rebalances the portfolio based on performance momentum and the chosen rebalancing period.
        The REBALANCING_PERIOD parameter in the config determines the lookback window.
        """
        total_budget = sum(pair_budgets.values())
        performance_scores = {}

        # Define lookback window based on the REBALANCING_PERIOD parameter
        rebalancing_period = config.get("REBALANCING_PERIOD", "MEDIUM").lower()
        if rebalancing_period == "SHORT":
            lookback = 5
        elif rebalancing_period == "LONG":
            lookback = 30
        else:  # default to medium
            lookback = 15

        for pair in config["PAIRS"]:
            # Ensure this method returns a list of returns
            historical_returns = state_managers[pair].get_historical_returns()
            # Use the most recent 'lookback' data points for momentum calculation
            if historical_returns and len(historical_returns) >= lookback:
                relevant_returns = historical_returns[-lookback:]
            else:
                relevant_returns = historical_returns or []

            # Calculate momentum using a utility function, e.g., TradingUtils.calculate_momentum
            momentum = TradingUtils.calculate_momentum(
                relevant_returns) if relevant_returns else 0
            performance_scores[pair] = max(momentum, 0)

        total_score = sum(performance_scores.values())
        if total_score > 0:
            new_allocations = {
                pair: (performance_scores[pair] / total_score) * total_budget
                for pair in performance_scores.keys()
            }
        else:
            new_allocations = pair_budgets

        portfolio_alloc_file = os.path.join(config.get(
            "DATA_DIR", "data"), "portfolio_alloc.json")
        try:
            with open(portfolio_alloc_file, "w") as f:
                json.dump({"pair_budgets": new_allocations}, f, indent=4)
        except Exception as e:
            logger.log(f"❌ Error saving portfolio allocation: {e}", to_slack=True)

        logger.log(
            f"🔄 Portfolio rebalanced: {json.dumps(new_allocations, indent=2)}", to_slack=True)
        StateManager.log_portfolio_distribution(
            new_allocations, logger, "rebalancing")
        return new_allocations
