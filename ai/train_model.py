import argparse
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from imblearn.over_sampling import RandomOverSampler

FEATURE_COLUMNS = [
    "rsi", "macd", "signal", "macd_hist", "ema_fast", "ema_slow",
    "support", "resistance", "atr", "momentum", "volume_change",
    "price", "macd_diff", "ema_diff", "price_minus_support", "resistance_minus_price"
]
LABEL_COLUMN = "label"


def load_training_data(path):
    df = pd.read_csv(path)
    missing = [col for col in FEATURE_COLUMNS + [LABEL_COLUMN] if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in training data: {missing}")
    return df


def balance_data(X, y):
    print("⚖️  Performing class balancing with RandomOverSampler...")
    ros = RandomOverSampler(random_state=42)
    X_bal, y_bal = ros.fit_resample(X, y)
    print(f"📊 Balanced class distribution: {dict(pd.Series(y_bal).value_counts())}")
    return X_bal, y_bal


def train_model(df, balance=False):
    X = df[FEATURE_COLUMNS]
    y = df[LABEL_COLUMN]

    if balance:
        X, y = balance_data(X, y)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    print("\n📊 Classification Report:")
    print(classification_report(y_test, y_pred))

    return clf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--balance", default="no", choices=["yes", "no"])
    args = parser.parse_args()

    df = load_training_data(args.data)
    balance = args.balance.lower() == "yes"
    model = train_model(df, balance=balance)
    joblib.dump(model, args.output)
    print(f"✅ Model saved to {args.output}")


if __name__ == "__main__":
    main()