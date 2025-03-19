import joblib
import pandas as pd

class AIDecider:
    def __init__(self, pair_models: dict, logger):
        self.models = {}
        self.logger = logger
        self.expected_features = [
            "rsi", "macd", "signal", "macd_hist", "ema_fast", "ema_slow",
            "support", "resistance", "atr", "momentum", "volume_change",
            "price", "macd_diff", "ema_diff", "price_minus_support", "resistance_minus_price"
        ]

        for pair, model_path in pair_models.items():
            try:
                model = joblib.load(model_path)
                self.models[pair] = model
                self.logger.log(f"✅ Loaded model for {pair} from {model_path}", to_console=True)
            except Exception as e:
                self.logger.log(f"❌ Failed to load model for {pair}: {e}", to_console=True)

    def should_buy(self, pair, *features):
        model = self.models.get(pair)
        if not model:
            raise ValueError(f"No AI model loaded for pair: {pair}")

        try:
            features_df = pd.DataFrame([features], columns=self.expected_features)
        except Exception as e:
            raise ValueError(f"Feature mismatch in BUY for {pair}: {e}")

        probability = model.predict_proba(features_df)[0][1]  # class 1 = BUY
        self.logger.log(f"🧠 AI Decision BUY  → Probability: {probability:.4f}", to_console=True)
        return probability

    def should_sell(self, pair, *features):
        model = self.models.get(pair)
        if not model:
            raise ValueError(f"No AI model loaded for pair: {pair}")

        try:
            features_df = pd.DataFrame([features], columns=self.expected_features)
        except Exception as e:
            raise ValueError(f"Feature mismatch in SELL for {pair}: {e}")

        probability = model.predict_proba(features_df)[0][0]  # class 0 = SELL
        self.logger.log(f"🧠 {pair}: AI Decision SELL  → Probability: {probability:.4f}", to_console=True)
        return probability

