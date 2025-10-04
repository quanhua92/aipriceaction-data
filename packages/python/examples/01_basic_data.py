#!/usr/bin/env python3
"""
Basic Data Example: VNINDEX OHLCV data fetching

This example demonstrates how to fetch VNINDEX data using the Python
data infrastructure, matching the TypeScript implementation.

Run with: python packages/python/examples/01_basic_data.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from aipriceaction.data import CSVDataService
from aipriceaction.core import extract_ma_values
from aipriceaction.utils import format_k, format_m, validate_with_tolerance


# Expected values from TypeScript example 01 (ACTUAL TS output)
EXPECTED_VNINDEX_DATA = {
    "2025-09-22": {
        "open": 1656.66, "high": 1659.13, "low": 1616.02, "close": 1634.45,
        "volume": 1212478380, "ma10": 1660.06, "ma20": 1661.63, "ma50": 1594.91
    },
    "2025-09-23": {
        "open": 1635.12, "high": 1643.59, "low": 1626.65, "close": 1635.26,
        "volume": 797233705, "ma10": 1659.86, "ma20": 1661.12, "ma50": 1598.46
    },
    "2025-09-24": {
        "open": 1635.36, "high": 1657.46, "low": 1619.09, "close": 1657.46,
        "volume": 998074719, "ma10": 1661.28, "ma20": 1663.29, "ma50": 1602.20
    },
    "2025-09-25": {
        "open": 1661.08, "high": 1668.21, "low": 1654.47, "close": 1666.09,
        "volume": 995617724, "ma10": 1662.11, "ma20": 1663.22, "ma50": 1606.31
    },
    "2025-09-26": {
        "open": 1666.68, "high": 1671.43, "low": 1657.94, "close": 1660.70,
        "volume": 963931987, "ma10": 1661.45, "ma20": 1662.61, "ma50": 1610.02
    },
}




def fetch_basic_data():
    """Fetch and display VNINDEX OHLCV data with MA values"""
    print("🚀 Starting VNINDEX OHLCV data fetch...")

    try:
        # Fetch VNINDEX data (ALL range for trading days)
        vnindex_data = CSVDataService.fetch_vnindex()
        print(f"📊 VNINDEX data loaded: {len(vnindex_data)} points")

        # Calculate moving averages using vectorized system
        print("📈 Calculating moving averages using vectorized-ma-score system...")

        # Create ticker data dict and date range
        ticker_data = {"VNINDEX": vnindex_data}
        date_range = [point.time for point in vnindex_data]

        # Calculate MAs
        ma_values_map = extract_ma_values(ticker_data, ["VNINDEX"], date_range)
        vnindex_ma_values = ma_values_map.get("VNINDEX", [])

        # Merge MA values back into original data
        ma_values_by_date = {item["date"]: item for item in vnindex_ma_values}

        for point in vnindex_data:
            ma_values = ma_values_by_date.get(point.time, {})
            point.ma10 = ma_values.get("ma10")
            point.ma20 = ma_values.get("ma20")
            point.ma50 = ma_values.get("ma50")

        # Get the latest 10 dates
        latest_data = vnindex_data[-10:]

        print("\n📈 VNINDEX: === 10 LATEST DATES ===")

        for i, point in enumerate(latest_data):
            print(
                f"VNINDEX[{i}] {point.time}: "
                f"O:{format_k(point.open)} H:{format_k(point.high)} L:{format_k(point.low)} C:{format_k(point.close)} "
                f"V:{format_m(point.volume)} | "
                f"MA10:{format_k(point.ma10 or 0)} MA20:{format_k(point.ma20 or 0)} MA50:{format_k(point.ma50 or 0)}"
            )

        print("\n✅ Fetch completed successfully!")

        # Validation with tolerance checking
        print("\n🔍 Validating against expected values (5% tolerance):")

        total_tests = 0
        passed_tests = 0

        for point in latest_data:
            expected = EXPECTED_VNINDEX_DATA.get(point.time)
            if expected:
                print(f"\n📊 Validating {point.time}:")

                total_tests += 8  # OHLCV + MA10, MA20, MA50

                if validate_with_tolerance(point.open, expected["open"], 0.05, "Open"):
                    passed_tests += 1
                if validate_with_tolerance(point.high, expected["high"], 0.05, "High"):
                    passed_tests += 1
                if validate_with_tolerance(point.low, expected["low"], 0.05, "Low"):
                    passed_tests += 1
                if validate_with_tolerance(point.close, expected["close"], 0.05, "Close"):
                    passed_tests += 1
                if validate_with_tolerance(point.volume, expected["volume"], 0.05, "Volume"):
                    passed_tests += 1
                if validate_with_tolerance(point.ma10 or 0, expected["ma10"], 0.05, "MA10"):
                    passed_tests += 1
                if validate_with_tolerance(point.ma20 or 0, expected["ma20"], 0.05, "MA20"):
                    passed_tests += 1
                if validate_with_tolerance(point.ma50 or 0, expected["ma50"], 0.05, "MA50"):
                    passed_tests += 1

        # Summary
        percentage = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"\n📈 Validation Summary: {passed_tests}/{total_tests} tests passed ({percentage:.1f}%)")

        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! Data matches expected values within tolerance.")
        else:
            print(f"⚠️  {total_tests - passed_tests} tests failed. Check values above.")

    except Exception as error:
        print(f"❌ Error fetching data: {error}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    fetch_basic_data()
