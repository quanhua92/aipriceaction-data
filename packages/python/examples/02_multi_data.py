#!/usr/bin/env python3
"""
Multi-Ticker Data Example: Fetching multiple tickers with MA values and scores

This example demonstrates multi-ticker data fetching with moving average calculations,
matching the TypeScript implementation.

Run with: uv run python examples/02_multi_data.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from aipriceaction.data import CSVDataService, DateRangeConfig
from aipriceaction.core import extract_ma_values
from aipriceaction.utils import format_k, format_m, validate_with_tolerance


# Expected values from TypeScript example 02 (ACTUAL TS output for 2025-09-26)
# Note: Stock prices are in VND, stored as decimals (e.g., 164.0 = 164k VND)
EXPECTED_VALUES_2025_09_26 = {
    "VIC": {
        "open": 158.0, "high": 164.9, "low": 156.0, "close": 164.0,
        "volume": 2700000, "ma10": 148.3, "ma20": 138.8, "ma50": 126.2,
        "s10": 10.60, "s20": 18.20, "s50": 30.00
    },
    "VCB": {
        "open": 63.2, "high": 63.4, "low": 62.9, "close": 63.0,
        "volume": 4000000, "ma10": 63.6, "ma20": 65.2, "ma50": 63.7,
        "s10": -0.90, "s20": -3.40, "s50": -1.20
    },
    "CTG": {
        "open": 50.3, "high": 51.6, "low": 50.0, "close": 50.7,
        "volume": 10300000, "ma10": 50.9, "ma20": 50.7, "ma50": 48.8,
        "s10": -0.33, "s20": -0.01, "s50": 3.90
    },
    "VIX": {
        "open": 37.4, "high": 37.4, "low": 36.0, "close": 36.0,
        "volume": 22000000, "ma10": 36.8, "ma20": 36.5, "ma50": 31.7,
        "s10": -2.10, "s20": -1.30, "s50": 13.70
    },
}


def fetch_multi_ticker_data():
    """Fetch and display multi-ticker OHLCV data with MA values"""
    print("🚀 Starting multi-ticker data fetch (VNINDEX, VIC, VCB, CTG, VIX)...")

    try:
        # Fetch VNINDEX data
        print("📊 Fetching VNINDEX data...")
        vnindex_data = CSVDataService.fetch_vnindex()
        print(f"✅ VNINDEX data loaded: {len(vnindex_data)} points")

        # Fetch stock ticker data (3M range)
        print("📊 Fetching stock ticker data...")
        stock_tickers = ["VIC", "VCB", "CTG", "VIX"]
        date_range_config = DateRangeConfig(range="3M")
        stock_data = CSVDataService.fetch_tickers(stock_tickers, date_range_config)
        print(f"✅ Stock data loaded for {len(stock_data)} tickers")

        # Calculate moving averages for VNINDEX
        print("📈 Calculating moving averages using vectorized-ma-score system...")
        vnindex_ticker_data = {"VNINDEX": vnindex_data}
        vnindex_date_range = [point.time for point in vnindex_data]
        vnindex_ma_values = extract_ma_values(vnindex_ticker_data, ["VNINDEX"], vnindex_date_range)

        # Merge MA values for VNINDEX
        vnindex_ma_by_date = {item["date"]: item for item in vnindex_ma_values.get("VNINDEX", [])}
        for point in vnindex_data:
            ma_values = vnindex_ma_by_date.get(point.time, {})
            point.ma10 = ma_values.get("ma10")
            point.ma20 = ma_values.get("ma20")
            point.ma50 = ma_values.get("ma50")

        # Calculate moving averages for stock tickers
        for ticker in stock_tickers:
            if ticker in stock_data:
                ticker_points = stock_data[ticker]
                date_range = [point.time for point in ticker_points]
                ticker_data_dict = {ticker: ticker_points}
                ma_values_map = extract_ma_values(ticker_data_dict, [ticker], date_range)
                ma_by_date = {item["date"]: item for item in ma_values_map.get(ticker, [])}

                for point in ticker_points:
                    ma_values = ma_by_date.get(point.time, {})
                    point.ma10 = ma_values.get("ma10")
                    point.ma20 = ma_values.get("ma20")
                    point.ma50 = ma_values.get("ma50")

        # Display VNINDEX - 10 latest dates
        print("\n📈 VNINDEX: === 10 LATEST DATES ===")
        vnindex_latest = vnindex_data[-10:]
        for i, point in enumerate(vnindex_latest):
            print(
                f"VNINDEX[{i}] {point.time}: "
                f"O:{format_k(point.open)} H:{format_k(point.high)} L:{format_k(point.low)} C:{format_k(point.close)} "
                f"V:{format_m(point.volume)} | "
                f"MA10:{format_k(point.ma10 or 0)} MA20:{format_k(point.ma20 or 0)} MA50:{format_k(point.ma50 or 0)}"
            )

        # Display stock tickers - 10 latest dates
        for ticker in stock_tickers:
            if ticker in stock_data:
                ticker_points = stock_data[ticker]
                latest_points = ticker_points[-10:]

                print(f"\n📈 {ticker}: === 10 LATEST DATES ===")
                for i, point in enumerate(latest_points):
                    # Calculate MA scores
                    ma10_score = ((point.close - point.ma10) / point.ma10 * 100) if point.ma10 else 0
                    ma20_score = ((point.close - point.ma20) / point.ma20 * 100) if point.ma20 else 0
                    ma50_score = ((point.close - point.ma50) / point.ma50 * 100) if point.ma50 else 0

                    print(
                        f"{ticker}[{i}] {point.time}: "
                        f"O:{format_k(point.open)} H:{format_k(point.high)} L:{format_k(point.low)} C:{format_k(point.close)} "
                        f"V:{format_m(point.volume)} | "
                        f"MA10:{format_k(point.ma10 or 0)} MA20:{format_k(point.ma20 or 0)} MA50:{format_k(point.ma50 or 0)} "
                        f"S10:{ma10_score:.2f}% S20:{ma20_score:.2f}% S50:{ma50_score:.2f}%"
                    )

        print("\n✅ Multi-ticker fetch completed successfully!")

        # Validation
        print("\n🔍 Validating latest date (2025-09-26) against expected values (5% tolerance):")
        total_tests = 0
        passed_tests = 0

        for ticker in stock_tickers:
            if ticker in stock_data and ticker in EXPECTED_VALUES_2025_09_26:
                ticker_points = stock_data[ticker]

                # Find the specific date point
                target_point = None
                for point in ticker_points:
                    if point.time == "2025-09-26":
                        target_point = point
                        break

                if target_point:
                    expected = EXPECTED_VALUES_2025_09_26[ticker]
                    print(f"\n📊 Validating {ticker}:")

                    total_tests += 11  # OHLCV + MA10, MA20, MA50 + S10, S20, S50

                    if validate_with_tolerance(target_point.open, expected["open"], 0.05, "Open"):
                        passed_tests += 1
                    if validate_with_tolerance(target_point.high, expected["high"], 0.05, "High"):
                        passed_tests += 1
                    if validate_with_tolerance(target_point.low, expected["low"], 0.05, "Low"):
                        passed_tests += 1
                    if validate_with_tolerance(target_point.close, expected["close"], 0.05, "Close"):
                        passed_tests += 1
                    if validate_with_tolerance(target_point.volume, expected["volume"], 0.05, "Volume"):
                        passed_tests += 1
                    if validate_with_tolerance(target_point.ma10 or 0, expected["ma10"], 0.05, "MA10"):
                        passed_tests += 1
                    if validate_with_tolerance(target_point.ma20 or 0, expected["ma20"], 0.05, "MA20"):
                        passed_tests += 1
                    if validate_with_tolerance(target_point.ma50 or 0, expected["ma50"], 0.05, "MA50"):
                        passed_tests += 1

                    # Calculate and validate MA scores
                    ma10_score = ((target_point.close - target_point.ma10) / target_point.ma10 * 100) if target_point.ma10 else 0
                    ma20_score = ((target_point.close - target_point.ma20) / target_point.ma20 * 100) if target_point.ma20 else 0
                    ma50_score = ((target_point.close - target_point.ma50) / target_point.ma50 * 100) if target_point.ma50 else 0

                    if validate_with_tolerance(ma10_score, expected["s10"], 0.05, "MA10 Score"):
                        passed_tests += 1
                    if validate_with_tolerance(ma20_score, expected["s20"], 0.05, "MA20 Score"):
                        passed_tests += 1
                    if validate_with_tolerance(ma50_score, expected["s50"], 0.05, "MA50 Score"):
                        passed_tests += 1

        # Summary
        percentage = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"\n📈 Validation Summary: {passed_tests}/{total_tests} tests passed ({percentage:.1f}%)")

        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! Data matches expected values within tolerance.")
        else:
            print(f"⚠️  {total_tests - passed_tests} tests failed. Check values above.")

        print(f"\n📊 Summary Statistics:")
        print(f"Total tickers processed: {len(stock_data) + 1}")
        print(f"MA score calculations: {len(stock_data)} tickers")

    except Exception as error:
        print(f"❌ Error fetching data: {error}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    fetch_multi_ticker_data()
