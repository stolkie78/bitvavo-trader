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

    def should_buy(self, pair, *features, coin_rank_score=0.5):
        model = self.models.get(pair)
        if not model:
            raise ValueError(f"No AI model loaded for pair: {pair}")
    
        try:
            features_df = pd.DataFrame([features], columns=self.expected_features)
        except Exception as e:
            raise ValueError(f"Feature mismatch in BUY for {pair}: {e}")
    
        probability = model.predict_proba(features_df)[0][1]  # class 1 = BUY
        risk_score = self.assess_risk_score(
            features_df["rsi"].iloc[0],
            features_df["atr"].iloc[0],
            features_df["momentum"].iloc[0],
            features_df["macd_diff"].iloc[0],
            coin_rank_score
        )
    
        investment_multiplier = min(1.0, max(0.1, risk_score))
        self.logger.log(f"  ↳ 🧠 {pair}: AI Decision BUY → Prob: {probability:.4f}, Risk Score: {risk_score}, Multiplier: {investment_multiplier:.2f}", to_console=True)
    
        return {
            "decision": probability >= 0.5,
            "probability": probability,
            "risk_score": risk_score,
            "multiplier": investment_multiplier
        }

    def should_sell(self, pair, *features):
        model = self.models.get(pair)
        if not model:
            raise ValueError(f"No AI model loaded for pair: {pair}")

        try:
            features_df = pd.DataFrame([features], columns=self.expected_features)
        except Exception as e:
            raise ValueError(f"Feature mismatch in SELL for {pair}: {e}")

        probability = model.predict_proba(features_df)[0][0]  # class 0 = SELL
        self.logger.log(f"  ↳ 🧠 {pair}: AI Decision SELL  → Probability: {probability:.4f}", to_console=True)
        return probability

    def assess_risk_score(self, rsi, atr, momentum, macd_diff, coin_rank_score):
        """
        Calculates a risk score between 0 (hoog risico) en 1 (laag risico).
        Combinatie van volatiliteit (ATR), momentum en RSI.
        """
        try:
            normalized_rsi = max(0.0, min(1.0, rsi / 100)) if rsi else 0.5
            normalized_atr = 1.0 / (1.0 + atr) if atr else 0.5
            normalized_momentum = max(0.0, min(1.0, momentum / 1000)) if momentum else 0.5
            normalized_macd_diff = max(0.0, min(1.0, abs(macd_diff) / 10)) if macd_diff else 0.5
            normalized_rank = max(0.0, min(1.0, coin_rank_score / 200)) if coin_rank_score else 0.5

            # Risk score = combinatie van deze factoren
            score = (normalized_rsi * 0.2 +
                     normalized_atr * 0.2 +
                     normalized_momentum * 0.2 +
                     normalized_macd_diff * 0.2 +
                     normalized_rank * 0.2)

            return round(score, 4)
        except Exception as e:
            self.logger.log(f"⚠️ Risk score error: {e}", to_console=True)
            return 0.5  # fallback