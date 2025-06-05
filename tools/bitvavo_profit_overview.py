#!/usr/bin/env python3
"""
Script to calculate the net profit/loss (cash flow in EUR) per cryptocurrency
aggregated by day, week and month from a CSV file.

Expected CSV columns (first row contains headers):
    Timezone,Date,Time,Type,Currency,Amount,Quote Currency,Quote Price,
    Received / Paid Currency,Received / Paid Amount,Fee currency,Fee amount,
    Status,Transaction ID,Address

The script combines the Date and Time columns into a single datetime and computes:
    Net = (Received / Paid Amount) - (Fee amount)
Results are aggregated as follows:
  - Daily: net cash flow per crypto with a "TOTAL" row per day.
  - Weekly: net cash flow per crypto per ISO week with a "TOTAL" row per week.
  - Monthly: net cash flow per crypto per month (YYYY-MM) with a "TOTAL" row per month.
Each aggregation also appends the grand totals per currency
and finally adds one overall total row.
"""

import argparse
import sys
import pandas as pd


def parse_datetime(dt_str: str) -> pd.Timestamp:
    """
    Parse a datetime string with or without fractional seconds.

    Args:
        dt_str (str): Date and time string (e.g. "2025-02-11 11:23:05.657" or "2025-02-11 11:23:05").

    Returns:
        pd.Timestamp: Parsed datetime.
    """
    try:
        return pd.to_datetime(dt_str, format='%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        return pd.to_datetime(dt_str, format='%Y-%m-%d %H:%M:%S')


def read_csv_with_datetime(csv_file: str) -> pd.DataFrame:
    """
    Read the CSV and add a DateTime column by combining the 'Date' and 'Time' columns.

    Args:
        csv_file (str): Path to the CSV file.

    Returns:
        pd.DataFrame: DataFrame with an extra 'DateTime' column and calculated 'Net'.
    """
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        sys.exit(f"Fout bij het inlezen van CSV: {e}")

    required_cols = ["Date", "Time", "Currency",
                     "Received / Paid Amount", "Fee amount"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        sys.exit(f"De CSV mist de volgende kolommen: {missing}")

    try:
        df["DateTime"] = (df["Date"] + " " + df["Time"]).apply(parse_datetime)
    except Exception as e:
        sys.exit(f"Fout bij het omzetten van Date en Time naar datetime: {e}")

    try:
        df["ReceivedPaid"] = pd.to_numeric(
            df["Received / Paid Amount"], errors="coerce")
        df["Fee"] = pd.to_numeric(df["Fee amount"], errors="coerce")
    except Exception as e:
        sys.exit(f"Fout bij het converteren van numerieke kolommen: {e}")

    df["Net"] = df["ReceivedPaid"] - df["Fee"]

    return df


def add_overall_total(df_grouped: pd.DataFrame, period_col: str) -> pd.DataFrame:
    """
    Append a single row with the overall total for the entire dataset,
    regardless of the period. The added row will have the value "OVERALL" in
    both the period column and the "Currency" column.

    Args:
        df_grouped (pd.DataFrame): The already grouped DataFrame.
        period_col (str): Name of the period column ('Day', 'Week' or 'Month').

    Returns:
        pd.DataFrame: The DataFrame with an extra row for the overall total.
    """
    overall_total = pd.DataFrame({
        period_col: ["OVERALL"],
        "Currency": ["OVERALL"],
        "Net": [df_grouped["Net"].sum()]
    })
    return pd.concat([df_grouped, overall_total], ignore_index=True)


def compute_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate daily net cash flow per cryptocurrency and add a total row per day.
    Afterwards the grand totals per currency over all days are appended,
    followed by one overall total row.

    Returns:
        pd.DataFrame: DataFrame with columns 'Day', 'Currency' and 'Net', sorted by day.
    """
    df["Day"] = df["DateTime"].dt.date.astype(str)
    daily_crypto = df.groupby(["Day", "Currency"])["Net"].sum().reset_index()
    daily_total = df.groupby("Day")["Net"].sum().reset_index()
    daily_total["Currency"] = "TOTAL"
    daily = pd.concat([daily_crypto, daily_total], ignore_index=True)
    daily["order"] = daily["Currency"].apply(
        lambda x: 1 if x == "TOTAL" else 0)
    daily = daily.sort_values(
        by=["Day", "order", "Currency"]).drop(columns=["order"])

    # Grand totals per currency over alle dagen
    grand_totals = df.groupby("Currency")["Net"].sum().reset_index()
    grand_totals["Day"] = "GRAND TOTAL"
    grand_totals = grand_totals[["Day", "Currency", "Net"]]
    daily = pd.concat([daily, grand_totals], ignore_index=True)

    # Voeg één overall total toe
    daily = add_overall_total(daily, "Day")
    return daily


def compute_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate weekly net cash flow per cryptocurrency and add a total row per week.
    The ISO week number (as a string) is used. Grand totals per currency over all weeks
    are appended followed by one overall total row.

    Returns:
        pd.DataFrame: DataFrame with columns 'Week', 'Currency' and 'Net', sorted by week.
    """
    df["Week"] = df["DateTime"].dt.isocalendar().week.astype(str)
    weekly_crypto = df.groupby(["Week", "Currency"])["Net"].sum().reset_index()
    weekly_total = df.groupby("Week")["Net"].sum().reset_index()
    weekly_total["Currency"] = "TOTAL"
    weekly = pd.concat([weekly_crypto, weekly_total], ignore_index=True)
    weekly["order"] = weekly["Currency"].apply(
        lambda x: 1 if x == "TOTAL" else 0)
    weekly = weekly.sort_values(
        by=["Week", "order", "Currency"]).drop(columns=["order"])

    # Grand totals per currency over alle weken
    grand_totals = df.groupby("Currency")["Net"].sum().reset_index()
    grand_totals["Week"] = "GRAND TOTAL"
    grand_totals = grand_totals[["Week", "Currency", "Net"]]
    weekly = pd.concat([weekly, grand_totals], ignore_index=True)

    # Voeg één overall total toe
    weekly = add_overall_total(weekly, "Week")
    return weekly


def compute_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate monthly net cash flow per cryptocurrency and add a total row per month.
    The month is displayed as YYYY-MM. Grand totals per currency over all months are appended,
    followed by one overall total row.

    Returns:
        pd.DataFrame: DataFrame with columns 'Month', 'Currency' and 'Net', sorted by month.
    """
    df["Month"] = df["DateTime"].dt.to_period("M").astype(str)
    monthly_crypto = df.groupby(["Month", "Currency"])[
        "Net"].sum().reset_index()
    monthly_total = df.groupby("Month")["Net"].sum().reset_index()
    monthly_total["Currency"] = "TOTAL"
    monthly = pd.concat([monthly_crypto, monthly_total], ignore_index=True)
    monthly["order"] = monthly["Currency"].apply(
        lambda x: 1 if x == "TOTAL" else 0)
    monthly = monthly.sort_values(
        by=["Month", "order", "Currency"]).drop(columns=["order"])

    # Grand totals per currency over alle maanden
    grand_totals = df.groupby("Currency")["Net"].sum().reset_index()
    grand_totals["Month"] = "GRAND TOTAL"
    grand_totals = grand_totals[["Month", "Currency", "Net"]]
    monthly = pd.concat([monthly, grand_totals], ignore_index=True)

    # Voeg één overall total toe
    monthly = add_overall_total(monthly, "Month")
    return monthly


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Calculate net profit/loss (cash flow in EUR) per cryptocurrency, "
            "aggregated by day, week and month. "
            "Use --period to choose: daily, weekly, monthly or all. "
            "Each aggregation adds a 'TOTAL' row per period, "
            "followed by grand totals per currency and one overall total."
        )
    )
    parser.add_argument(
        "csv_file", help="Path to the CSV file with transaction data.")
    parser.add_argument(
        "--period", choices=["daily", "weekly", "monthly", "all"], default="all",
        help="Aggregation period: daily, weekly, monthly or all (default: all)."
    )
    args = parser.parse_args()

    df = read_csv_with_datetime(args.csv_file)

    results = {}
    if args.period in ["daily", "all"]:
        results["Daily"] = compute_daily(df)
    if args.period in ["weekly", "all"]:
        results["Weekly"] = compute_weekly(df)
    if args.period in ["monthly", "all"]:
        results["Monthly"] = compute_monthly(df)

    for key, result in results.items():
        print(f"\nNet profit/loss ({key}):")
        print(result.to_string(index=False))


if __name__ == "__main__":
    main()
