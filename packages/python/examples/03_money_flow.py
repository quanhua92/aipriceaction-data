#!/usr/bin/env python3
"""
Money Flow Analysis Example: Vectorized money flow calculations

This example demonstrates advanced money flow analysis with vectorized calculations,
matching the TypeScript implementation.

Run with: uv run python examples/03_money_flow.py
"""

import sys
from pathlib import Path
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from aipriceaction.data import CSVDataService, DateRangeConfig
from aipriceaction.core.matrix_utils import (
    vectorize_ticker_data,
    calculate_money_flow_matrix,
    calculate_daily_totals,
    calculate_flow_percentages,
    calculate_rolling_trend_scores,
    calculate_vnindex_volume_scaling,
    apply_vnindex_volume_scaling
)
from aipriceaction.utils import validate_with_tolerance


def format_flow(value: float) -> str:
    """Format flow value with sign"""
    if value >= 0:
        return f"+{value:.2f}"
    return f"{value:.2f}"


# Expected values from TypeScript example 03 (ACTUAL TS output for 2025-09-26 after date order fix)
EXPECTED_VALUES = {
    "BID": {"mf": -0.38, "af": -0.38, "df": -0.55, "ts": 0.69},
    "CTG": {"mf": -0.16, "af": -0.16, "df": -0.28, "ts": 0.78},
    "TCB": {"mf": 0.17, "af": 0.17, "df": 0.23, "ts": 1.74},
    "VCB": {"mf": -0.40, "af": -0.40, "df": -0.89, "ts": 0.66},
    "VIC": {"mf": 0.36, "af": 0.36, "df": 2.09, "ts": 0.32},
    "VIX": {"mf": -3.40, "af": -3.40, "df": -4.35, "ts": 4.39},
}


def analyze_money_flow():
    """Analyze money flow with vectorized calculations"""
    print("🚀 Starting Money Flow Analysis with Vectorized Calculations...")

    try:
        # Validation tickers (matching TypeScript example)
        validation_tickers = ["BID", "CTG", "TCB", "VCB", "VIC", "VIX"]

        # Fetch VNINDEX data for volume weighting
        print("📊 Fetching VNINDEX data for volume weighting...")
        vnindex_data = CSVDataService.fetch_vnindex()
        print(f"✅ VNINDEX data loaded: {len(vnindex_data)} points")

        # Fetch ALL stock ticker data for complete market context (3M range)
        print("📊 Fetching ALL stock ticker data for complete market context...")
        date_range_config = DateRangeConfig(range="3M")
        stock_data = CSVDataService.fetch_all_tickers(date_range_config)
        print(f"✅ Stock data loaded for {len(stock_data)} tickers")

        # Build date range from ticker data
        all_dates = set()
        for ticker_points in stock_data.values():
            for point in ticker_points:
                all_dates.add(point.time)

        date_range = sorted(list(all_dates), reverse=True)  # Reverse chronological order
        print(f"📈 Using {len(date_range)} dates for money flow calculations")

        # Get all ticker names for vectorization (exclude VNINDEX like TypeScript)
        all_tickers = [ticker for ticker in stock_data.keys() if ticker != "VNINDEX"]
        print(f"📊 Using {len(all_tickers)} tickers for complete market context (excluding VNINDEX)")

        # Vectorize ticker data for ALL tickers
        matrix, dates, ticker_index, date_index = vectorize_ticker_data(
            stock_data, all_tickers, date_range
        )

        # Calculate money flow matrix
        print("💰 Calculating vectorized money flow...")
        money_flow_matrix = calculate_money_flow_matrix(
            matrix, all_tickers, dates, stock_data
        )

        # Calculate VNINDEX volume scaling
        print("📊 Calculating VNINDEX volume scaling...")
        vnindex_volume_scaling = calculate_vnindex_volume_scaling(vnindex_data, dates)

        # Apply VNINDEX volume scaling to flows
        print("📊 Applying VNINDEX volume scaling to flows...")
        scaled_activity_flows = apply_vnindex_volume_scaling(
            money_flow_matrix["activity_flows"],
            vnindex_volume_scaling,
            dates,
            len(all_tickers)
        )
        scaled_dollar_flows = apply_vnindex_volume_scaling(
            money_flow_matrix["dollar_flows"],
            vnindex_volume_scaling,
            dates,
            len(all_tickers)
        )

        # Update matrix with scaled flows
        money_flow_matrix["activity_flows"] = scaled_activity_flows
        money_flow_matrix["dollar_flows"] = scaled_dollar_flows
        # Also update absolute flows for daily total calculations
        money_flow_matrix["absolute_activity_flows"] = np.abs(scaled_activity_flows)
        money_flow_matrix["absolute_dollar_flows"] = np.abs(scaled_dollar_flows)

        # Calculate daily totals and percentages for activity flows
        activity_daily_totals = calculate_daily_totals(money_flow_matrix, "activity")
        activity_percentages = calculate_flow_percentages(money_flow_matrix, activity_daily_totals, "activity")

        # Make signed percentages (preserve sign from activity flows)
        for i in range(len(activity_percentages)):
            if money_flow_matrix["activity_flows"][i] < 0:
                activity_percentages[i] = -activity_percentages[i]

        # Calculate daily totals and percentages for dollar flows
        dollar_daily_totals = calculate_daily_totals(money_flow_matrix, "dollar")
        dollar_percentages = calculate_flow_percentages(money_flow_matrix, dollar_daily_totals, "dollar")

        # Make signed percentages (preserve sign from dollar flows)
        for i in range(len(dollar_percentages)):
            if money_flow_matrix["dollar_flows"][i] < 0:
                dollar_percentages[i] = -dollar_percentages[i]

        # Calculate trend scores from activity percentages
        trend_scores = calculate_rolling_trend_scores(
            activity_percentages,
            money_flow_matrix["num_tickers"],
            money_flow_matrix["num_dates"],
            window_size=10
        )

        # Test single date calculation (using 2025-09-26 to match TypeScript)
        test_date = "2025-09-26"
        try:
            test_date_index = dates.index(test_date)
        except ValueError:
            print(f"❌ Test date {test_date} not found in data. Available dates: {dates[0]} to {dates[-1]}")
            sys.exit(1)

        print(f"\n📊 === Single Date Money Flow Results ({test_date}) ===\n")


        # Display results for validation tickers
        for ticker in validation_tickers:
            t_idx = ticker_index.get(ticker)
            if t_idx is not None:
                idx = t_idx * money_flow_matrix["num_dates"] + test_date_index

                mf_pct = activity_percentages[idx]
                af_pct = activity_percentages[idx]
                df_pct = dollar_percentages[idx]
                ts = trend_scores[idx]


                print(
                    f"{ticker}: MF:{format_flow(mf_pct)}% "
                    f"AF:{format_flow(af_pct)} "
                    f"DF:{format_flow(df_pct)} "
                    f"TS:{ts:.2f}"
                )

        print("\n✅ Money Flow Analysis completed successfully!")

        # Validation
        print("\n🔍 Validating results against expected values (10% tolerance for flows, 5% for trend scores):")
        total_tests = 0
        passed_tests = 0

        for ticker in validation_tickers:
            if ticker in EXPECTED_VALUES:
                t_idx = ticker_index.get(ticker)
                if t_idx is not None:
                    idx = t_idx * money_flow_matrix["num_dates"] + test_date_index
                    expected = EXPECTED_VALUES[ticker]

                    print(f"\n📊 Validating {ticker}:")
                    total_tests += 4  # MF, AF, DF, TS

                    mf_pct = activity_percentages[idx]
                    af_pct = activity_percentages[idx]
                    df_pct = dollar_percentages[idx]
                    ts = trend_scores[idx]

                    if validate_with_tolerance(mf_pct, expected["mf"], 0.10, "Money Flow %"):
                        passed_tests += 1
                    if validate_with_tolerance(af_pct, expected["af"], 0.10, "Activity Flow %"):
                        passed_tests += 1
                    if validate_with_tolerance(df_pct, expected["df"], 0.10, "Dollar Flow %"):
                        passed_tests += 1
                    if validate_with_tolerance(ts, expected["ts"], 0.05, "Trend Score"):
                        passed_tests += 1

        # Summary
        percentage = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"\n📈 Validation Summary: {passed_tests}/{total_tests} tests passed ({percentage:.1f}%)")

        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! Data matches expected values within tolerance.")
        else:
            print(f"⚠️  {total_tests - passed_tests} tests failed. Check values above.")

        # Summary statistics
        print(f"\n📊 Summary Statistics:")
        print(f"Total tickers analyzed: {len(all_tickers)} (validation tickers: {len(validation_tickers)})")
        print(f"Date range analyzed: {len(date_range)} dates")
        print(f"Total calculations: {money_flow_matrix['num_tickers'] * money_flow_matrix['num_dates']}")
        print(f"VNINDEX volume weighting: enabled")

    except Exception as error:
        print(f"❌ Error in money flow analysis: {error}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    analyze_money_flow()
