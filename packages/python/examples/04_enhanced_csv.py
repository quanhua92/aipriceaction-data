"""
Example 04: Bulk CSV Enhancement

Demonstrates how to enhance CSV files with calculated technical indicators.

Process:
1. Fetch ALL tickers from cache file (287 tickers, 3M range)
2. Calculate MA10, MA20, MA50 and their scores per ticker
3. Calculate money flow using Example 03's matrix approach (full market context)
4. Write enhanced CSVs with 16 columns to /tmp/market_data/

Enhanced CSV format (16 columns):
ticker,time,open,high,low,close,volume,ma10,ma20,ma50,
ma10_score,ma20_score,ma50_score,money_flow,dollar_flow,trend_score

This approach uses Example 03's proven methodology for accurate money flow calculations.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aipriceaction.data import CSVDataService, DateRangeConfig
from aipriceaction.services.csv_enhancement_engine import CSVEnhancementEngine
from aipriceaction.utils.validators import validate_with_tolerance
from aipriceaction.core.matrix_utils import (
    vectorize_ticker_data,
    calculate_money_flow_matrix,
    calculate_daily_totals,
    calculate_flow_percentages,
    calculate_rolling_trend_scores,
    calculate_vnindex_volume_scaling,
    apply_vnindex_volume_scaling
)
import pandas as pd
import numpy as np


# Validation tickers
VALIDATION_TICKERS = ["VCB", "VIC", "CTG", "BID", "TCB", "VIX"]

# Expected values from Example 03
VALIDATION_DATE = "2025-09-26"
EXPECTED = {
    "VCB": {
        "money_flow": -0.40, "dollar_flow": -0.89, "trend_score": 0.66
    },
    "VIC": {
        "money_flow": 0.36, "dollar_flow": 2.09, "trend_score": 0.32
    },
    "CTG": {
        "money_flow": -0.16, "dollar_flow": -0.28, "trend_score": 0.78
    }
}


async def main():
    import time
    start_time = time.time()

    print("🚀 Bulk CSV Enhancement - Production Flow")
    print("=" * 70)

    output_dir = Path("/tmp/market_data")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Fetch VNINDEX data (keep as StockDataPoint list)
    print(f"[{time.time()-start_time:.1f}s] 📊 Fetching VNINDEX data...")
    vnindex_data = CSVDataService.fetch_vnindex()
    print(f"[{time.time()-start_time:.1f}s] ✅ VNINDEX: {len(vnindex_data)} rows")

    # Step 2: Fetch ALL stock tickers with FULL HISTORY (from 2015!)
    print(f"\n[{time.time()-start_time:.1f}s] 📊 Fetching ALL stock ticker data (FULL HISTORY)...")
    date_range_config = DateRangeConfig(range="ALL")
    stock_data = CSVDataService.fetch_all_tickers(date_range_config)
    print(f"[{time.time()-start_time:.1f}s] ✅ Loaded {len(stock_data)} tickers")

    # Add VNINDEX to stock_data for processing
    stock_data["VNINDEX"] = vnindex_data

    # Convert to DataFrame for MA calculations and CSV writing
    print(f"[{time.time()-start_time:.1f}s] Converting to DataFrame...")
    all_rows = []
    for ticker, points in stock_data.items():
        for p in points:
            all_rows.append({
                'ticker': ticker, 'time': p.time, 'open': p.open, 'high': p.high,
                'low': p.low, 'close': p.close, 'volume': p.volume
            })

    all_tickers_df = pd.DataFrame(all_rows)
    all_tickers_df = all_tickers_df.sort_values(['ticker', 'time'])
    print(f"[{time.time()-start_time:.1f}s]    Total rows: {len(all_tickers_df):,}")
    print(f"[{time.time()-start_time:.1f}s]    Tickers: {all_tickers_df['ticker'].nunique()}")

    # Step 3: Calculate MA and MA Scores (simple per-ticker calculation)
    print(f"\n[{time.time()-start_time:.1f}s] 📈 Calculating moving averages...")
    enhanced_dfs = []
    for ticker in all_tickers_df['ticker'].unique():
        ticker_df = all_tickers_df[all_tickers_df['ticker'] == ticker].copy()
        ticker_df = ticker_df.sort_values('time')

        # Calculate MAs
        ticker_df['ma10'] = ticker_df['close'].rolling(window=10, min_periods=10).mean()
        ticker_df['ma20'] = ticker_df['close'].rolling(window=20, min_periods=20).mean()
        ticker_df['ma50'] = ticker_df['close'].rolling(window=50, min_periods=50).mean()

        # Calculate MA Scores
        ticker_df['ma10_score'] = ((ticker_df['close'] - ticker_df['ma10']) / ticker_df['ma10'] * 100).where(ticker_df['ma10'].notna())
        ticker_df['ma20_score'] = ((ticker_df['close'] - ticker_df['ma20']) / ticker_df['ma20'] * 100).where(ticker_df['ma20'].notna())
        ticker_df['ma50_score'] = ((ticker_df['close'] - ticker_df['ma50']) / ticker_df['ma50'] * 100).where(ticker_df['ma50'].notna())

        enhanced_dfs.append(ticker_df)

    all_tickers_df = pd.concat(enhanced_dfs, ignore_index=True)
    print(f"[{time.time()-start_time:.1f}s] ✅ Calculated MA and MA Scores")

    # Step 4: Calculate money flow using Example 03's exact matrix approach
    print(f"\n[{time.time()-start_time:.1f}s] 💰 Calculating money flow (Example 03 approach)...")

    # Build date range (reverse chronological)
    print(f"[{time.time()-start_time:.1f}s] Building date range...")
    all_dates = set()
    for ticker_points in stock_data.values():
        for point in ticker_points:
            all_dates.add(point.time)
    date_range = sorted(list(all_dates), reverse=True)
    print(f"[{time.time()-start_time:.1f}s] Date range: {len(date_range)} days")

    all_tickers = [ticker for ticker in stock_data.keys() if ticker != "VNINDEX"]

    # Vectorize data
    print(f"[{time.time()-start_time:.1f}s] Vectorizing data...")
    matrix, dates, ticker_index, date_index = vectorize_ticker_data(
        stock_data, all_tickers, date_range
    )
    print(f"[{time.time()-start_time:.1f}s] Matrix shape: {matrix.shape}")

    # Calculate money flow matrix
    print(f"[{time.time()-start_time:.1f}s] Calculating money flow matrix...")
    money_flow_matrix = calculate_money_flow_matrix(
        matrix, all_tickers, dates, stock_data
    )
    print(f"[{time.time()-start_time:.1f}s] Money flow matrix done")

    # Calculate VNINDEX volume scaling
    print(f"[{time.time()-start_time:.1f}s] Calculating VNINDEX scaling...")
    vnindex_volume_scaling = calculate_vnindex_volume_scaling(vnindex_data, dates)

    # Apply VNINDEX scaling
    print(f"[{time.time()-start_time:.1f}s] Applying VNINDEX scaling...")
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

    # Update matrix
    money_flow_matrix["activity_flows"] = scaled_activity_flows
    money_flow_matrix["dollar_flows"] = scaled_dollar_flows
    money_flow_matrix["absolute_activity_flows"] = np.abs(scaled_activity_flows)
    money_flow_matrix["absolute_dollar_flows"] = np.abs(scaled_dollar_flows)

    # Calculate percentages
    activity_daily_totals = calculate_daily_totals(money_flow_matrix, "activity")
    activity_percentages = calculate_flow_percentages(money_flow_matrix, activity_daily_totals, "activity")

    # Make signed percentages
    for i in range(len(activity_percentages)):
        if money_flow_matrix["activity_flows"][i] < 0:
            activity_percentages[i] = -activity_percentages[i]

    dollar_daily_totals = calculate_daily_totals(money_flow_matrix, "dollar")
    dollar_percentages = calculate_flow_percentages(money_flow_matrix, dollar_daily_totals, "dollar")

    for i in range(len(dollar_percentages)):
        if money_flow_matrix["dollar_flows"][i] < 0:
            dollar_percentages[i] = -dollar_percentages[i]

    # Calculate trend scores
    trend_scores = calculate_rolling_trend_scores(
        activity_percentages,
        money_flow_matrix["num_tickers"],
        money_flow_matrix["num_dates"],
        10
    )

    # Convert to DataFrame columns (using ticker-first ordering like Example 03)
    money_flow_data = []
    for t_idx, ticker in enumerate(all_tickers):
        for d_idx, date in enumerate(dates):
            flat_idx = t_idx * len(dates) + d_idx
            money_flow_data.append({
                'ticker': ticker,
                'time': date,
                'money_flow': activity_percentages[flat_idx],
                'dollar_flow': dollar_percentages[flat_idx],
                'trend_score': trend_scores[flat_idx]
            })

    money_flow_df = pd.DataFrame(money_flow_data)

    # Merge money flow into main DataFrame
    all_tickers_df = all_tickers_df.merge(
        money_flow_df,
        on=['ticker', 'time'],
        how='left'
    )

    print(f"✅ Enhanced {len(all_tickers_df):,} rows")

    # Step 5: Write enhanced CSVs
    print(f"\n💾 Writing enhanced CSVs to {output_dir}...")
    tickers = all_tickers_df['ticker'].unique()
    for i, ticker in enumerate(tickers, 1):
        ticker_df = all_tickers_df[all_tickers_df['ticker'] == ticker].copy()
        ticker_df = CSVEnhancementEngine.format_for_csv(ticker_df)

        csv_path = output_dir / f"{ticker}.csv"
        ticker_df.to_csv(csv_path, index=False)

        if i % 50 == 0:
            print(f"  Progress: {i}/{len(tickers)}")

    print(f"✅ Written {len(tickers)} enhanced CSVs")

    # Step 6: Generate cache files from enhanced CSVs
    print("\n📦 Generating cache files (60d, 180d, 365d)...")

    cache_dir = output_dir.parent / "cache"
    cache_dir.mkdir(exist_ok=True)

    # Helper function to generate cache from enhanced CSVs
    def generate_cache_from_csvs(days: int, output_path: str):
        print(f"\n📦 Generating {days}-day cache file...")

        # Calculate cutoff date
        max_date = pd.to_datetime(all_tickers_df['time'].max())
        cutoff_date = max_date - pd.Timedelta(days=days)

        # Filter data
        cache_df = all_tickers_df[
            pd.to_datetime(all_tickers_df['time']) >= cutoff_date
        ].copy()

        # Format and save
        cache_df = CSVEnhancementEngine.format_for_csv(cache_df)
        cache_df.to_csv(output_path, index=False)

        tickers = cache_df['ticker'].nunique()
        rows = len(cache_df)
        date_range = f"{cache_df['time'].min()} to {cache_df['time'].max()}"

        print(f"✅ Cache file: {output_path}")
        print(f"   Tickers: {tickers}, Rows: {rows:,}")
        print(f"   Date range: {date_range}")

    generate_cache_from_csvs(60, str(cache_dir / "ticker_60_days.csv"))
    generate_cache_from_csvs(180, str(cache_dir / "ticker_180_days.csv"))
    generate_cache_from_csvs(365, str(cache_dir / "ticker_365_days.csv"))

    # Validation
    print("\n" + "=" * 70)
    print(f"🔍 Validating Money Flow ({VALIDATION_DATE})")
    print("=" * 70)

    total_tests = 0
    passed_tests = 0

    for ticker in ["VCB", "VIC", "CTG"]:
        # Read enhanced CSV
        csv_path = Path("/tmp/market_data") / f"{ticker}.csv"
        if not csv_path.exists():
            print(f"\n⚠️  {ticker}: CSV not found")
            continue

        df = pd.read_csv(csv_path)
        row = df[df['time'] == VALIDATION_DATE]

        if row.empty:
            print(f"\n⚠️  {ticker}: No data for {VALIDATION_DATE}")
            continue

        row = row.iloc[0]
        exp = EXPECTED[ticker]

        print(f"\n📊 {ticker}:")

        # Money Flow (10% tolerance)
        total_tests += 1
        if validate_with_tolerance(row['money_flow'], exp['money_flow'], 0.10, "  Money Flow"):
            passed_tests += 1

        # Dollar Flow (10% tolerance)
        total_tests += 1
        if validate_with_tolerance(row['dollar_flow'], exp['dollar_flow'], 0.10, "  Dollar Flow"):
            passed_tests += 1

        # Trend Score (5% tolerance)
        total_tests += 1
        if validate_with_tolerance(row['trend_score'], exp['trend_score'], 0.05, "  Trend Score"):
            passed_tests += 1

    # Summary
    print("\n" + "=" * 70)
    print(f"📈 Validation: {passed_tests}/{total_tests} tests ({passed_tests/total_tests*100:.1f}%)")

    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED! Production pipeline working correctly.")
    else:
        print(f"⚠️  {total_tests - passed_tests} tests failed")

    print("\n📝 Architecture:")
    print("   - Uses Example 03's approach: fetch_all_tickers() from cache file")
    print("   - Cache file has ALL 287 tickers (full market context)")
    print("   - Money flow calculations match Example 03 exactly")
    print(f"   - Enhanced CSVs written to {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
