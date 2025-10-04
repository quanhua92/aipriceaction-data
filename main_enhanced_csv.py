"""
Enhanced CSV Generator for GitHub Actions Workflow

This script enhances existing CSV files with calculated technical indicators.
Unlike the example (04_enhanced_csv.py), this script reads from local CSV files
that were already downloaded by previous workflow steps.

Process:
1. Read existing CSVs from market_data/ directory
2. Calculate MA10, MA20, MA50 and their scores per ticker
3. Calculate money flow using matrix approach (full market context)
4. Write enhanced CSVs with 16 columns back to market_data/

Enhanced CSV format (16 columns):
ticker,time,open,high,low,close,volume,ma10,ma20,ma50,
ma10_score,ma20_score,ma50_score,money_flow,dollar_flow,trend_score
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add packages/python to path for imports
sys.path.insert(0, str(Path(__file__).parent / "packages" / "python"))

from aipriceaction.core.matrix_utils import (
    vectorize_ticker_data,
    calculate_money_flow_matrix,
    calculate_daily_totals,
    calculate_flow_percentages,
    calculate_rolling_trend_scores,
    calculate_vnindex_volume_scaling,
    apply_vnindex_volume_scaling
)
from aipriceaction.models import StockDataPoint


def load_csv_files(data_dir: Path) -> dict:
    """Load all CSV files from market_data directory into StockDataPoint format"""
    stock_data = {}

    csv_files = list(data_dir.glob("*.csv"))
    print(f"📁 Found {len(csv_files)} CSV files in {data_dir}")

    for csv_file in csv_files:
        ticker = csv_file.stem  # Filename without .csv extension

        try:
            df = pd.read_csv(csv_file)

            # Convert to StockDataPoint list
            points = []
            for _, row in df.iterrows():
                point = StockDataPoint(
                    time=row['time'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume'])
                )
                points.append(point)

            stock_data[ticker] = points

        except Exception as e:
            print(f"⚠️  Error loading {ticker}: {e}")
            continue

    print(f"✅ Loaded {len(stock_data)} tickers")
    return stock_data


def enhance_csvs(data_dir: Path):
    """Main function to enhance CSV files with technical indicators"""
    print("🚀 Enhanced CSV Generator - GitHub Actions Workflow")
    print("=" * 70)

    # Step 1: Load existing CSV files
    print(f"\n📊 Loading CSV files from {data_dir}...")
    stock_data = load_csv_files(data_dir)

    if len(stock_data) == 0:
        print("❌ No CSV files found. Exiting.")
        return

    # Separate VNINDEX from stock data
    vnindex_data = stock_data.pop("VNINDEX", None)

    if vnindex_data is None:
        print("⚠️  VNINDEX not found. Money flow calculations may be inaccurate.")
    else:
        print(f"✅ VNINDEX: {len(vnindex_data)} rows")

    # Step 2: Convert to DataFrame
    print(f"\n📈 Converting to DataFrame...")
    all_rows = []
    for ticker, points in stock_data.items():
        for p in points:
            all_rows.append({
                'ticker': ticker,
                'time': p.time,
                'open': p.open,
                'high': p.high,
                'low': p.low,
                'close': p.close,
                'volume': p.volume
            })

    # Add VNINDEX rows
    if vnindex_data:
        for p in vnindex_data:
            all_rows.append({
                'ticker': 'VNINDEX',
                'time': p.time,
                'open': p.open,
                'high': p.high,
                'low': p.low,
                'close': p.close,
                'volume': p.volume
            })

    all_tickers_df = pd.DataFrame(all_rows)
    all_tickers_df = all_tickers_df.sort_values(['ticker', 'time'])
    print(f"   Total rows: {len(all_tickers_df):,}")
    print(f"   Tickers: {all_tickers_df['ticker'].nunique()}")

    # Step 3: Calculate MA and MA Scores
    print(f"\n📈 Calculating moving averages...")
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
    print(f"✅ Calculated MA and MA Scores")

    # Step 4: Calculate money flow (if VNINDEX exists)
    if vnindex_data:
        print(f"\n💰 Calculating money flow...")

        # Add VNINDEX back to stock_data for calculations
        stock_data_with_vnindex = stock_data.copy()
        stock_data_with_vnindex["VNINDEX"] = vnindex_data

        # Build date range (reverse chronological)
        all_dates = set()
        for ticker_points in stock_data_with_vnindex.values():
            for point in ticker_points:
                all_dates.add(point.time)
        date_range = sorted(list(all_dates), reverse=True)
        print(f"   Date range: {len(date_range)} days")

        all_tickers = [ticker for ticker in stock_data_with_vnindex.keys() if ticker != "VNINDEX"]

        # Vectorize data
        matrix, dates, ticker_index, date_index = vectorize_ticker_data(
            stock_data_with_vnindex, all_tickers, date_range
        )
        print(f"   Matrix shape: {matrix.shape}")

        # Calculate money flow matrix
        money_flow_matrix = calculate_money_flow_matrix(
            matrix, all_tickers, dates, stock_data_with_vnindex
        )

        # Calculate VNINDEX volume scaling
        vnindex_volume_scaling = calculate_vnindex_volume_scaling(vnindex_data, dates)

        # Apply VNINDEX scaling
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

        # Convert to DataFrame columns
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

        print(f"✅ Enhanced {len(all_tickers_df):,} rows with money flow")
    else:
        # Add empty money flow columns
        all_tickers_df['money_flow'] = np.nan
        all_tickers_df['dollar_flow'] = np.nan
        all_tickers_df['trend_score'] = np.nan
        print(f"⚠️  Skipped money flow calculations (VNINDEX missing)")

    # Step 5: Write enhanced CSVs back to market_data/
    print(f"\n💾 Writing enhanced CSVs to {data_dir}...")

    # Column order for output
    columns = [
        'ticker', 'time', 'open', 'high', 'low', 'close', 'volume',
        'ma10', 'ma20', 'ma50', 'ma10_score', 'ma20_score', 'ma50_score',
        'money_flow', 'dollar_flow', 'trend_score'
    ]

    tickers = all_tickers_df['ticker'].unique()
    for i, ticker in enumerate(tickers, 1):
        ticker_df = all_tickers_df[all_tickers_df['ticker'] == ticker].copy()

        # Select and order columns
        ticker_df = ticker_df[columns]

        # Format output
        ticker_df = ticker_df.round({
            'open': 2, 'high': 2, 'low': 2, 'close': 2,
            'ma10': 2, 'ma20': 2, 'ma50': 2,
            'ma10_score': 4, 'ma20_score': 4, 'ma50_score': 4,
            'money_flow': 4, 'dollar_flow': 4, 'trend_score': 4
        })

        csv_path = data_dir / f"{ticker}.csv"
        ticker_df.to_csv(csv_path, index=False)

        if i % 50 == 0:
            print(f"  Progress: {i}/{len(tickers)}")

    print(f"✅ Written {len(tickers)} enhanced CSVs")
    print("=" * 70)


if __name__ == "__main__":
    # Use market_data directory in the same location as script
    script_dir = Path(__file__).parent
    data_dir = script_dir / "market_data"

    if not data_dir.exists():
        print(f"❌ Directory not found: {data_dir}")
        print("   Make sure market_data/ exists with CSV files from previous steps")
        sys.exit(1)

    enhance_csvs(data_dir)
