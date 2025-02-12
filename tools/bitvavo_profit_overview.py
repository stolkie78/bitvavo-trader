#!/usr/bin/env python3
"""
Script voor het berekenen van de netto winst/verlies (cashflow in EUR) per crypto,
geaggregeerd per dag, week en maand op basis van een CSV-bestand.

Verwachte kolommen in de CSV (eerste rij bevat de headers):
    Timezone,Date,Time,Type,Currency,Amount,Quote Currency,Quote Price,
    Received / Paid Currency,Received / Paid Amount,Fee currency,Fee amount,
    Status,Transaction ID,Address

Het script combineert de kolommen Date en Time tot één datetime en berekent:
    Net = (Received / Paid Amount) - (Fee amount)
Vervolgens worden de resultaten als volgt geaggregeerd:
  - Daily: per dag wordt per crypto de netto cashflow berekend en er komt een totaalrij ("TOTAL") per dag.
  - Weekly: per week (ISO-weeknummer) wordt per crypto de netto cashflow berekend en er komt een totaalrij ("TOTAL") per week.
  - Monthly: per maand (YYYY-MM) wordt per crypto de netto cashflow berekend en er komt een totaalrij ("TOTAL") per maand.
Daaronder wordt in elke aggregatie ook een set rijen toegevoegd met de grand totals (per currency over de gehele dataset)
en als laatste één extra rij met de OVERALL total.
"""

import argparse
import sys
import pandas as pd


def parse_datetime(dt_str: str) -> pd.Timestamp:
    """
    Probeert een datetime-string te parsen met en zonder fractionele seconden.
    
    Args:
        dt_str (str): Datum- en tijdstring (bijv. "2025-02-11 11:23:05.657" of "2025-02-11 11:23:05")
    
    Returns:
        pd.Timestamp: De geparste datetime.
    """
    try:
        return pd.to_datetime(dt_str, format='%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        return pd.to_datetime(dt_str, format='%Y-%m-%d %H:%M:%S')


def read_csv_with_datetime(csv_file: str) -> pd.DataFrame:
    """
    Leest de CSV in en voegt een DateTime-kolom toe door de kolommen 'Date' en 'Time' te combineren.
    
    Args:
        csv_file (str): Pad naar het CSV-bestand.
        
    Returns:
        pd.DataFrame: DataFrame met extra kolom 'DateTime' en berekende 'Net'.
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
    Voegt als laatste één extra rij toe met de overall total over de gehele dataset,
    ongeacht de periode. Het resultaat bevat dan in de kolom period_col de waarde "OVERALL"
    en in 'Currency' de waarde "OVERALL".
    
    Args:
        df_grouped (pd.DataFrame): De reeds gegroepeerde DataFrame.
        period_col (str): De naam van de kolom die de periode bevat ('Day', 'Week' of 'Month').
    
    Returns:
        pd.DataFrame: De DataFrame met een extra row voor de overall total.
    """
    overall_total = pd.DataFrame({
        period_col: ["OVERALL"],
        "Currency": ["OVERALL"],
        "Net": [df_grouped["Net"].sum()]
    })
    return pd.concat([df_grouped, overall_total], ignore_index=True)


def compute_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bereken de dagelijkse netto cashflow per crypto en voeg per dag een totaalrij toe.
    Daarna worden de grand totals per currency (over alle dagen) toegevoegd,
    gevolgd door één overall total rij.
    
    Returns:
        pd.DataFrame: DataFrame met kolommen 'Day', 'Currency' en 'Net', gesorteerd op dag.
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
    Bereken de wekelijkse netto cashflow per crypto en voeg per week een totaalrij toe.
    Hierbij wordt het ISO-weeknummer (als string) gebruikt.
    Daarna worden de grand totals per currency over alle weken toegevoegd,
    gevolgd door één overall total.
    
    Returns:
        pd.DataFrame: DataFrame met kolommen 'Week', 'Currency' en 'Net', gesorteerd op week.
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
    Bereken de maandelijkse netto cashflow per crypto en voeg per maand een totaalrij toe.
    De maand wordt weergegeven als YYYY-MM.
    Daarna worden de grand totals per currency over alle maanden toegevoegd,
    gevolgd door één overall total.
    
    Returns:
        pd.DataFrame: DataFrame met kolommen 'Month', 'Currency' en 'Net', gesorteerd op maand.
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
        description=("Bereken de netto winst/verlies (cashflow in EUR) per crypto, "
                     "geaggregeerd per dag, week en maand. "
                     "Gebruik --period om te kiezen: daily, weekly, monthly of all. "
                     "Voor elke aggregatie wordt per periode een totaalrij ('TOTAL') toegevoegd, "
                     "daaronder de grand totals per currency en als laatste een overall total.")
    )
    parser.add_argument(
        "csv_file", help="Pad naar het CSV-bestand met transactiegegevens.")
    parser.add_argument(
        "--period", choices=["daily", "weekly", "monthly", "all"], default="all",
        help="Aggregatieperiode: daily, weekly, monthly of all (default: all)."
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
        print(f"\nNetto winst/verlies ({key}):")
        print(result.to_string(index=False))


if __name__ == "__main__":
    main()
