
class StateManager:
    def __init__(self, pair, logger):
        self.pair = pair
        self.logger = logger
        self.position = None  # Holds the current position (if any)

    def has_position(self):
        return self.position is not None

    def buy(self, price, budget, trade_fee_percentage):
        if self.has_position():
            raise RuntimeError(f"Already holding a position for {self.pair}. Cannot buy again.")
        
        quantity = budget / price
        self.position = {
            "buy_price": price,
            "quantity": quantity,
        }
        self.logger.log(f"🟢 Bought {self.pair}: Price={price:.2f}, Quantity={quantity:.6f}")

    def sell(self, price, trade_fee_percentage):
        if not self.has_position():
            raise RuntimeError(f"No position to sell for {self.pair}.")
        
        buy_price = self.position['buy_price']
        quantity = self.position['quantity']
        profit = self.calculate_profit(price, trade_fee_percentage)

        self.logger.log(
            f"🔴 Sold {self.pair}: Price={price:.2f}, Quantity={quantity:.6f}, Profit={profit:.2f}%"
        )

        self.position = None

    def calculate_profit(self, current_price, trade_fee_percentage):
        if not self.has_position():
            raise ValueError(f"No position to calculate profit for {self.pair}.")

        buy_price = self.position['buy_price']
        quantity = self.position['quantity']

        total_cost = buy_price * quantity * (1 + trade_fee_percentage / 100)
        current_value = current_price * quantity * (1 - trade_fee_percentage / 100)

        profit_percentage = ((current_value - total_cost) / total_cost) * 100
        return profit_percentage
