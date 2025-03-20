import os
import argparse
import json
from subprocess import run


def retrain_models(config_path, limit=1000, interval="1h"):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r") as f:
        config = json.load(f)

    pairs = config.get("PAIRS", [])
    pair_models = config.get("PAIR_MODELS", {})

    if not pairs:
        print("⚠️ No pairs defined in config.")
        return

    os.makedirs("data", exist_ok=True)
    os.makedirs("models", exist_ok=True)

    for pair in pairs:
        symbol = pair.split("-")[0].lower()
        data_file = f"data/{symbol}_training.csv"
        model_file = pair_models.get(pair, f"models/buy_model_{symbol}.pkl")

        print(f"\n🔄 Retraining for {pair}...")

        generate_cmd = [
            "python", "ai/generate_training_data.py",
            "--pair", pair,
            "--limit", str(limit),
            "--interval", interval,
            "--output", data_file
        ]

        train_cmd = [
            "python", "ai/train_model.py",
            "--data", data_file,
            "--output", model_file
        ]

        result_gen = run(generate_cmd)
        if result_gen.returncode != 0:
            print(f"❌ Failed to generate training data for {pair}")
            continue

        result_train = run(train_cmd)
        if result_train.returncode != 0:
            print(f"❌ Failed to train model for {pair}")
        else:
            print(f"✅ Model retrained and saved for {pair}: {model_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrain AI models for all pairs in config")
    parser.add_argument("--config", type=str, default="config/ai_trader.json", help="Path to ai_trader config")
    parser.add_argument("--limit", type=int, default=1000, help="Candle limit for training data")
    parser.add_argument("--interval", type=str, default="1h", help="Candle interval (e.g., 1h, 1d)")
    args = parser.parse_args()

    retrain_models(args.config, args.limit, args.interval)