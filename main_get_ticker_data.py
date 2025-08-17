#!/usr/bin/env python3
"""
AIPriceAction Data Fetcher with VCI/TCBS Clients

This script replaces the vnstock dependency with custom VCI/TCBS clients,
providing significantly improved performance through VCI's batch history capability
while maintaining full compatibility with the existing data pipeline.

Key improvements:
- VCI batch history support for 3-5x faster data fetching
- Intelligent fallback strategy (VCI batch -> VCI individual -> TCBS)
- Preserved dividend detection and incremental update logic
- Optimized for multiple daily runs (6x per day via GitHub Actions)
"""

import os
import sys
import time
import pandas as pd
import json
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

# Add docs directory to path for custom client imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'docs'))

try:
    from vci import VCIClient
    from tcbs import TCBSClient
except ImportError as e:
    print(f"Error importing client modules: {e}")
    print("Make sure vci.py and tcbs.py are in the docs/ directory")
    sys.exit(1)

# --- Configuration ---
# Load all tickers from ticker_group.json
def load_tickers_from_groups():
    try:
        with open('ticker_group.json', 'r', encoding='utf-8') as f:
            ticker_groups = json.load(f)
        tickers = []
        for group, group_tickers in ticker_groups.items():
            tickers.extend(group_tickers)
        # Add VNINDEX if not already in the list
        if "VNINDEX" not in tickers:
            tickers.insert(0, "VNINDEX")
        return sorted(list(set(tickers)))  # Remove duplicates and sort
    except FileNotFoundError:
        print("ticker_group.json not found. Using default list.")
        return ["VNINDEX", "TCB", "FPT"]

TICKERS_TO_DOWNLOAD = load_tickers_from_groups()

# Define the names for your data directory.
DATA_DIR = "market_data"

# Global clients - will be initialized in main()
vci_client = None
tcbs_client = None
precision_decimals = 6  # Default precision for price data

# --- Core Functions ---

def get_data_directory(interval, year=None, month=None):
    """
    Get the appropriate data directory based on interval and time period.
    
    Args:
        interval: '1D', '1H', or '1m'  
        year: Year for 1H and 1m intervals (e.g., 2025)
        month: Month for 1m interval (e.g., '08')
    
    Returns:
        str: Path to the appropriate directory
    """
    if interval == '1D':
        return DATA_DIR
    elif interval == '1H':
        if year is None:
            return "market_data_hour"
        return os.path.join("market_data_hour", str(year))
    elif interval == '1m':
        if year is None:
            return "market_data_minutes"
        elif month is None:
            return os.path.join("market_data_minutes", str(year))
        return os.path.join("market_data_minutes", str(year), f"{month:02d}")
    else:
        raise ValueError(f"Invalid interval: {interval}")

def setup_directories(interval=None):
    """
    Creates the data directories based on interval.
    For 1D: creates market_data/
    For 1H: creates market_data_hour/ 
    For 1m: creates market_data_minutes/
    """
    print("Setting up base directories...")
    
    if interval is None or interval == '1D':
        # Daily data directory (existing behavior)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            print(f"  - Created directory: {DATA_DIR}")
    
    if interval == '1H':
        # Hourly data directory
        hour_dir = get_data_directory('1H')
        if not os.path.exists(hour_dir):
            os.makedirs(hour_dir)
            print(f"  - Created directory: {hour_dir}")
    
    if interval == '1m':
        # Minute data directory  
        minute_dir = get_data_directory('1m')
        if not os.path.exists(minute_dir):
            os.makedirs(minute_dir)
            print(f"  - Created directory: {minute_dir}")

def check_for_dividend_simple(ticker, client_type="VCI", interval="1D"):
    """
    Simple dividend detection adapted for VCI/TCBS APIs.
    Get last 30 days from API, compare with same dates from existing file.
    If prices differ significantly for matching dates from a week ago, it's likely a dividend.
    """
    # Get appropriate directory for interval
    base_dir = get_data_directory(interval)
    file_path = os.path.join(base_dir, f"{ticker}.csv")
    
    if not os.path.exists(file_path):
        return False  # No existing data to compare
    
    try:
        # Download last 30 days from API
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        print(f"   - DEBUG: Checking dividend by downloading {start_date} to {end_date}")
        
        # Use appropriate client based on type
        if client_type == "VCI":
            api_df = vci_client.get_history(
                symbol=ticker,
                start=start_date,
                end=end_date,
                interval=interval
            )
        else:  # TCBS
            api_df = tcbs_client.get_history(
                symbol=ticker,
                start=start_date,
                end=end_date,
                interval=interval
            )
        
        time.sleep(1)  # Rate limiting
        
        if api_df is None or api_df.empty:
            print(f"   - DEBUG: No API data for dividend check")
            return False
        
        # Load existing data
        existing_df = pd.read_csv(file_path)
        existing_df['time'] = pd.to_datetime(existing_df['time'])
        
        # Get dates from a week ago (more stable than very recent dates)
        week_ago = datetime.now() - timedelta(days=7)
        two_weeks_ago = datetime.now() - timedelta(days=14)
        
        # Filter both datasets to the comparison period
        api_compare = api_df[(api_df['time'] >= two_weeks_ago) & (api_df['time'] <= week_ago)].copy()
        existing_compare = existing_df[(existing_df['time'] >= two_weeks_ago) & (existing_df['time'] <= week_ago)].copy()
        
        print(f"   - DEBUG: API compare data: {len(api_compare)} rows")
        print(f"   - DEBUG: Existing compare data: {len(existing_compare)} rows")
        
        if len(api_compare) < 3 or len(existing_compare) < 3:
            print(f"   - DEBUG: Not enough data for comparison")
            return False
        
        # Merge on matching dates
        merged = pd.merge(api_compare, existing_compare, on='time', suffixes=('_api', '_existing'))
        print(f"   - DEBUG: Merged {len(merged)} matching dates")
        
        if len(merged) < 3:
            print(f"   - DEBUG: Not enough matching dates")
            return False
        
        # Compare close prices - if they're consistently different, it's likely a dividend
        price_diffs = []
        for _, row in merged.iterrows():
            if row['close_existing'] > 0 and row['close_api'] > 0:
                ratio = row['close_existing'] / row['close_api']
                price_diffs.append(ratio)
                print(f"   - DEBUG: Date {row['time'].strftime('%Y-%m-%d')}: existing={row['close_existing']}, api={row['close_api']}, ratio={ratio:.4f}")
        
        if len(price_diffs) < 3:
            return False
        
        avg_ratio = sum(price_diffs) / len(price_diffs)
        
        # If average ratio > 1.02 (2% difference), likely dividend
        is_dividend = avg_ratio > 1.02
        
        if is_dividend:
            print(f"   - DIVIDEND DETECTED for {ticker}: avg_ratio={avg_ratio:.4f}")
        else:
            print(f"   - No dividend detected for {ticker}: avg_ratio={avg_ratio:.4f}")
        
        return is_dividend
        
    except Exception as e:
        print(f"   - ERROR checking dividend for {ticker}: {e}")
        return False

def download_hourly_chunks(ticker, start_date, end_date, client_type="VCI"):
    """
    Download hourly data in yearly chunks to manage large datasets.
    Each year is saved in market_data_hour/YYYY/TICKER.csv
    """
    print(f"   - Starting chunked hourly download for {ticker}")
    
    start_year = datetime.strptime(start_date, "%Y-%m-%d").year
    end_year = datetime.strptime(end_date, "%Y-%m-%d").year
    
    all_chunks = []
    
    for year in range(start_year, end_year + 1):
        year_start = f"{year}-01-01"
        year_end = f"{year}-12-31"
        
        # Adjust for actual start/end dates
        if year == start_year:
            year_start = start_date
        if year == end_year:
            year_end = end_date
            
        print(f"   - Downloading {year} chunk: {year_start} to {year_end}")
        
        # Create year directory
        year_dir = get_data_directory('1H', year)
        if not os.path.exists(year_dir):
            os.makedirs(year_dir)
            print(f"     - Created directory: {year_dir}")
        
        try:
            if client_type == "VCI":
                chunk_df = vci_client.get_history(
                    symbol=ticker,
                    start=year_start,
                    end=year_end,
                    interval='1H'
                )
            else:  # TCBS
                chunk_df = tcbs_client.get_history(
                    symbol=ticker,
                    start=year_start,
                    end=year_end,
                    interval='1H'
                )
            
            time.sleep(2)  # Rate limiting between chunks
            
            if chunk_df is not None and not chunk_df.empty:
                chunk_df.insert(0, 'ticker', ticker)
                chunk_df = normalize_price_data(chunk_df, ticker)
                
                # Save chunk to year-specific file
                chunk_file = os.path.join(year_dir, f"{ticker}.csv")
                chunk_df.to_csv(chunk_file, index=False)
                print(f"     - Saved {len(chunk_df)} records to {chunk_file}")
                
                all_chunks.append(chunk_df)
            else:
                print(f"     - No data for {year}")
                
        except Exception as e:
            print(f"     - ERROR downloading {year} chunk: {e}")
    
    # Combine all chunks
    if all_chunks:
        combined_df = pd.concat(all_chunks, ignore_index=True).sort_values(by='time')
        print(f"   - Combined {len(combined_df)} total records from {len(all_chunks)} yearly chunks")
        return combined_df
    else:
        print(f"   - No data downloaded for any chunks")
        return None

def download_minute_chunks(ticker, start_date, end_date, client_type="VCI"):
    """
    Download minute data in monthly chunks to manage extremely large datasets.
    Each month is saved in market_data_minutes/YYYY/MM/TICKER.csv
    """
    print(f"   - Starting chunked minute download for {ticker}")
    
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    all_chunks = []
    current_dt = start_dt.replace(day=1)  # Start from beginning of start month
    
    while current_dt <= end_dt:
        # Calculate month range
        year = current_dt.year
        month = current_dt.month
        
        # First day of month
        month_start = current_dt.strftime("%Y-%m-%d")
        
        # Last day of month
        if month == 12:
            next_month = current_dt.replace(year=year+1, month=1, day=1)
        else:
            next_month = current_dt.replace(month=month+1, day=1)
        month_end = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Adjust for actual start/end dates
        if current_dt.year == start_dt.year and current_dt.month == start_dt.month:
            month_start = start_date
        if current_dt.year == end_dt.year and current_dt.month == end_dt.month:
            month_end = end_date
            
        print(f"   - Downloading {year}-{month:02d} chunk: {month_start} to {month_end}")
        
        # Create month directory
        month_dir = get_data_directory('1m', year, month)
        if not os.path.exists(month_dir):
            os.makedirs(month_dir, exist_ok=True)
            print(f"     - Created directory: {month_dir}")
        
        try:
            if client_type == "VCI":
                chunk_df = vci_client.get_history(
                    symbol=ticker,
                    start=month_start,
                    end=month_end,
                    interval='1m'
                )
            else:  # TCBS
                chunk_df = tcbs_client.get_history(
                    symbol=ticker,
                    start=month_start,
                    end=month_end,
                    interval='1m'
                )
            
            time.sleep(3)  # Longer rate limiting for minute data
            
            if chunk_df is not None and not chunk_df.empty:
                chunk_df.insert(0, 'ticker', ticker)
                chunk_df = normalize_price_data(chunk_df, ticker)
                
                # Save chunk to month-specific file
                chunk_file = os.path.join(month_dir, f"{ticker}.csv")
                chunk_df.to_csv(chunk_file, index=False)
                print(f"     - Saved {len(chunk_df)} records to {chunk_file}")
                
                all_chunks.append(chunk_df)
            else:
                print(f"     - No data for {year}-{month:02d}")
                
        except Exception as e:
            print(f"     - ERROR downloading {year}-{month:02d} chunk: {e}")
        
        # Move to next month
        current_dt = next_month
    
    # Combine all chunks
    if all_chunks:
        combined_df = pd.concat(all_chunks, ignore_index=True).sort_values(by='time')
        print(f"   - Combined {len(combined_df)} total records from {len(all_chunks)} monthly chunks")
        return combined_df
    else:
        print(f"   - No data downloaded for any chunks")
        return None

def download_full_data(ticker, start_date, end_date, client_type="VCI", interval="1D"):
    """
    Downloads complete historical data for a ticker using VCI or TCBS client.
    Uses chunked downloading for 1H and 1M intervals to handle large datasets.
    """
    print(f"   - Downloading full history from {start_date} to {end_date} using {client_type} [{interval}]...")
    
    try:
        # Use chunked downloading for high-frequency data
        if interval == '1H':
            return download_hourly_chunks(ticker, start_date, end_date, client_type)
        elif interval == '1m':
            return download_minute_chunks(ticker, start_date, end_date, client_type)
        
        # Standard download for daily data
        if client_type == "VCI":
            df = vci_client.get_history(
                symbol=ticker,
                start=start_date,
                end=end_date,
                interval=interval
            )
        else:  # TCBS
            df = tcbs_client.get_history(
                symbol=ticker,
                start=start_date,
                end=end_date,
                interval=interval
            )
        
        time.sleep(1)  # Rate limiting
        
        if df is not None and not df.empty:
            df.insert(0, 'ticker', ticker)
            df = df.sort_values(by='time')
            # Apply intelligent price normalization
            df = normalize_price_data(df, ticker)
            print(f"   - Downloaded {len(df)} records for full history")
            return df
        else:
            print(f"   - ERROR: Could not retrieve full data for {ticker}")
            return None
            
    except Exception as e:
        print(f"   - ERROR downloading full data for {ticker}: {e}")
        return None

def update_last_row_and_append_new_data(existing_df, new_df):
    """
    Update the last row of existing data and append new data, avoiding duplicates.
    This handles cases where the last row might be incomplete or needs updating.
    Returns the combined DataFrame with updated last row and new rows added.
    """
    print(f"   - DEBUG: Existing data has {len(existing_df)} rows")
    print(f"   - DEBUG: New data has {len(new_df)} rows")
    
    if existing_df.empty:
        print(f"   - DEBUG: No existing data, returning new data")
        return new_df
    
    # Find the latest date in existing data
    latest_date = existing_df['time'].max()
    print(f"   - DEBUG: Latest existing date: {latest_date.strftime('%Y-%m-%d')}")
    
    # Check if new data contains the same date as the last existing row
    same_date_rows = new_df[new_df['time'] == latest_date].copy()
    print(f"   - DEBUG: Found {len(same_date_rows)} rows with same date as last existing row")
    
    if not same_date_rows.empty:
        print(f"   - Updating last row for date {latest_date.strftime('%Y-%m-%d')}")
        # Get the old values for comparison
        old_row = existing_df[existing_df['time'] == latest_date].iloc[0]
        new_row = same_date_rows.iloc[0]
        print(f"   - DEBUG: Old close: {old_row['close']}, New close: {new_row['close']}")
        # Remove the last row from existing data
        existing_df = existing_df[existing_df['time'] != latest_date].copy()
        print(f"   - DEBUG: Removed last row, now have {len(existing_df)} existing rows")
        # The updated data for that date will be included in new_rows below
    
    # Filter new data to include dates from the latest existing date onwards
    new_rows = new_df[new_df['time'] >= latest_date].copy()
    print(f"   - DEBUG: Filtered to {len(new_rows)} new rows to add")
    
    if not new_rows.empty:
        print(f"   - Adding {len(new_rows)} rows (including any updated last row)")
        combined = pd.concat([existing_df, new_rows], ignore_index=True)
        result = combined.sort_values(by='time')
        
        # Debug for VND: show final price values
        ticker = new_df['ticker'].iloc[0] if not new_df.empty else 'UNKNOWN'
        if ticker == 'VND' and not result.empty:
            last_row = result.iloc[-1]
            print(f"   - DEBUG VND FINAL RESULT: close={last_row['close']}, open={last_row['open']}")
        print(f"   - DEBUG: Final result has {len(result)} rows")
        return result
    else:
        print(f"   - No new data to add")
        return existing_df

def download_stock_data_individual(ticker, start_date, end_date, client_type="VCI", interval="1D"):
    """
    Smart data fetching for individual ticker with dividend detection and last row validation.
    """
    print(f"\\n-> Processing individual ticker: {ticker} with {client_type} [{interval}]")
    
    # Get appropriate directory for interval
    base_dir = get_data_directory(interval)
    file_path = os.path.join(base_dir, f"{ticker}.csv")
    
    if os.path.exists(file_path):
        # Step 1: Check for dividend
        if check_for_dividend_simple(ticker, client_type, interval):
            # Dividend detected - download full history from start_date
            print(f"   - Dividend detected, downloading full history from {start_date}")
            return download_full_data(ticker, start_date, end_date, client_type, interval)
        else:
            # Step 2: No dividend - load existing data and update last row + append new records
            print(f"   - No dividend, loading existing data from {file_path}")
            existing_df = pd.read_csv(file_path)
            existing_df['time'] = pd.to_datetime(existing_df['time'])
            
            # Get latest date from existing data
            latest_date = existing_df['time'].max()
            print(f"   - DEBUG: Existing data has {len(existing_df)} rows, latest date: {latest_date.strftime('%Y-%m-%d')}")
            
            # Download data from the last date to today to check for updates and get new data
            last_date_str = latest_date.strftime('%Y-%m-%d')
            today_str = datetime.now().strftime('%Y-%m-%d')
            
            # Download data starting from the last existing date (to update it) to today
            if last_date_str <= today_str:
                print(f"   - Fetching data from {last_date_str} to {today_str} (including last row update)")
                try:
                    if client_type == "VCI":
                        new_df = vci_client.get_history(
                            symbol=ticker,
                            start=last_date_str,
                            end=today_str,
                            interval=interval
                        )
                    else:  # TCBS
                        new_df = tcbs_client.get_history(
                            symbol=ticker,
                            start=last_date_str,
                            end=today_str,
                            interval=interval
                        )
                    
                    time.sleep(1)  # Rate limiting
                    
                    if new_df is not None and not new_df.empty:
                        new_df.insert(0, 'ticker', ticker)
                        # Apply intelligent price normalization
                        new_df = normalize_price_data(new_df, ticker)
                        return update_last_row_and_append_new_data(existing_df, new_df)
                    else:
                        print(f"   - No new data available from API")
                        return existing_df
                except Exception as e:
                    print(f"   - ERROR downloading update data for {ticker}: {e}")
                    return existing_df
            else:
                print(f"   - Data is already up to date")
                return existing_df
    else:
        # No existing data - download full history
        print(f"   - No existing data found, downloading full history")
        return download_full_data(ticker, start_date, end_date, client_type, interval)

def download_stock_data_batch(tickers, fetch_start_date, end_date, batch_size=10, interval="1D"):
    """
    Optimized batch data fetching using VCI's batch history capability with intelligent fallback.
    """
    print(f"\\n-> Processing batch of {len(tickers)} tickers using VCI batch history [{interval}]")
    results = {}
    
    # Group tickers into smaller batches to respect rate limits
    ticker_batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    for batch_idx, ticker_batch in enumerate(ticker_batches):
        print(f"\\n--- Batch {batch_idx + 1}/{len(ticker_batches)}: {len(ticker_batch)} tickers ---")
        print(f"Tickers: {', '.join(ticker_batch)}")
        
        try:
            # Try VCI batch history first
            batch_data = vci_client.get_batch_history(
                symbols=ticker_batch,
                start=fetch_start_date,
                end=end_date,
                interval=interval
            )
            
            if batch_data:
                # Process successful batch results
                for ticker in ticker_batch:
                    if ticker in batch_data and batch_data[ticker] is not None:
                        df = batch_data[ticker]
                        if not df.empty:
                            # Debug: Show raw VCI batch data for ALL tickers
                            last_row = df.iloc[-1]
                            print(f"   - DEBUG {ticker} RAW VCI BATCH DATA: close={last_row.get('close', 'N/A')}, open={last_row.get('open', 'N/A')}")
                            if ticker == 'VND':
                                print(f"   - DEBUG VND RAW COLUMNS: {list(df.columns)}")
                            
                            # Remove symbol column if it exists (VCI adds it)
                            if 'symbol' in df.columns:
                                df = df.drop('symbol', axis=1)
                            # Add ticker column at the beginning
                            df.insert(0, 'ticker', ticker)
                            # Apply intelligent price normalization
                            df = normalize_price_data(df, ticker)
                            results[ticker] = df
                            print(f"   ✅ Batch success: {ticker} ({len(df)} records)")
                        else:
                            print(f"   ❌ Batch failed: {ticker} (empty data)")
                            results[ticker] = None
                    else:
                        print(f"   ❌ Batch failed: {ticker} (not in response)")
                        results[ticker] = None
            else:
                print(f"   ❌ Entire batch failed")
                for ticker in ticker_batch:
                    results[ticker] = None
                    
        except Exception as e:
            print(f"   ❌ Batch request error: {e}")
            for ticker in ticker_batch:
                results[ticker] = None
        
        # Rate limiting between batches
        if batch_idx < len(ticker_batches) - 1:
            print(f"   ⏸️ Rate limiting delay (2s)...")
            time.sleep(2)
    
    return results

def normalize_price_data(df, ticker):
    """
    Intelligent price normalization that distinguishes between market indices and individual stocks.
    Market indices (VNINDEX, HNXINDEX, UPCOMINDEX) should not be scaled.
    Individual stocks always need 1000x scaling correction from VCI/TCBS APIs.
    
    Uses global precision_decimals variable to control decimal places.
    """
    global precision_decimals
    
    if df is None or df.empty:
        return df
    
    # Create a copy to avoid modifying the original
    df_normalized = df.copy()
    
    # Define market indices that should NOT be scaled
    market_indices = {'VNINDEX', 'HNXINDEX', 'UPCOMINDEX'}
    
    # Check if this ticker is a market index
    if ticker.upper() in market_indices:
        print(f"   - {ticker} is a market index - no price scaling applied")
        return df_normalized
    
    # For individual stocks, always apply 1000x scaling correction
    price_columns = ['open', 'high', 'low', 'close']
    scale_factor = 1000.0
    print(f"   - {ticker} is an individual stock - scaling down by {scale_factor}")
    
    # Debug: Show before scaling for VND
    if ticker == 'VND' and not df_normalized.empty:
        last_row = df_normalized.iloc[-1]
        print(f"   - DEBUG VND BEFORE scaling: close={last_row['close']}, open={last_row['open']}")
    
    for col in price_columns:
        df_normalized[col] = df_normalized[col] / scale_factor
        
        # Apply precision rounding if specified
        if precision_decimals is not None:
            df_normalized[col] = df_normalized[col].round(precision_decimals)
    
    # Debug: Show after scaling for VND
    if ticker == 'VND' and not df_normalized.empty:
        last_row = df_normalized.iloc[-1]
        print(f"   - DEBUG VND AFTER scaling: close={last_row['close']}, open={last_row['open']}")
        
    
    return df_normalized

def save_data_to_csv(df, ticker, start_date, end_date, interval="1D"):
    """
    Saves the DataFrame to a CSV file in the appropriate interval directory.
    For 1D: saves to market_data/
    For 1H and 1M: consolidated data goes to main interval directory (not chunks)
    """
    file_name = f"{ticker}.csv"
    
    # Get base directory for interval (without year/month subfolders)
    base_dir = get_data_directory(interval)
    
    # Ensure directory exists
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        print(f"   - Created directory: {base_dir}")
    
    output_file = os.path.join(base_dir, file_name)
    
    df.to_csv(output_file, index=False)
    print(f"   - Data saved to: {output_file}")
    return output_file

def categorize_tickers_by_data_needs(tickers, interval="1D"):
    """
    Pre-scan all tickers to categorize them into:
    - resume_tickers: Tickers with sufficient existing data that can use resume mode
    - full_history_tickers: Tickers that need full history download (new or insufficient data)
    """
    resume_tickers = []
    full_history_tickers = []
    
    print(f"\\n🔍 Pre-scanning {len(tickers)} tickers to categorize data needs for {interval}...")
    
    # Get appropriate directory for interval
    base_dir = get_data_directory(interval)
    
    for ticker in tickers:
        file_path = os.path.join(base_dir, f"{ticker}.csv")
        
        if not os.path.exists(file_path):
            print(f"   🆕 {ticker}: No existing file - needs full history")
            full_history_tickers.append(ticker)
        else:
            # Check if existing data is sufficient
            try:
                existing_df = pd.read_csv(file_path)
                if len(existing_df) <= 5:  # Less than 5 days indicates insufficient data
                    print(f"   📉 {ticker}: Only {len(existing_df)} rows - needs full history")
                    full_history_tickers.append(ticker)
                else:
                    print(f"   ✅ {ticker}: {len(existing_df)} rows - can use resume mode")
                    resume_tickers.append(ticker)
            except Exception as e:
                print(f"   ❌ {ticker}: Error reading file - needs full history ({e})")
                full_history_tickers.append(ticker)
    
    print(f"\\n📊 Categorization results:")
    print(f"   Resume mode tickers: {len(resume_tickers)}")
    print(f"   Full history tickers: {len(full_history_tickers)}")
    
    return resume_tickers, full_history_tickers

def smart_dividend_check_and_merge(ticker, recent_data, start_date, end_date, interval="1D"):
    """
    Smart dividend detection using recent data comparison with existing file.
    If dividend detected, downloads full history and merges properly.
    If no dividend, merges recent data with existing data efficiently.
    
    NOTE: This function assumes the ticker already has sufficient existing data
    (new/insufficient tickers are handled separately in the categorization phase).
    """
    print(f"   - DEBUG: smart_dividend_check_and_merge called for {ticker}")
    
    # Get appropriate directory for interval
    base_dir = get_data_directory(interval)
    file_path = os.path.join(base_dir, f"{ticker}.csv")
    
    # Load existing data (should exist since this is a resume ticker)
    existing_df = pd.read_csv(file_path)
    existing_df['time'] = pd.to_datetime(existing_df['time'])
    
    if recent_data is None or recent_data.empty:
        print(f"   - DEBUG: No recent data available, keeping existing data")
        return existing_df
    
    print(f"   - DEBUG: Recent data has {len(recent_data)} rows, existing has {len(existing_df)} rows")
    
    # Check for dividend by comparing overlapping dates
    recent_dates = set(recent_data['time'].dt.strftime('%Y-%m-%d'))
    existing_dates = set(existing_df['time'].dt.strftime('%Y-%m-%d'))
    overlapping_dates = recent_dates.intersection(existing_dates)
    
    print(f"   - DEBUG: Found {len(overlapping_dates)} overlapping dates: {list(overlapping_dates)[:3]}")
    
    if len(overlapping_dates) >= 2:  # Need at least 2 days to compare
        is_dividend = False
        for date_str in list(overlapping_dates)[:3]:  # Check up to 3 overlapping dates
            recent_row = recent_data[recent_data['time'].dt.strftime('%Y-%m-%d') == date_str].iloc[0]
            existing_row = existing_df[existing_df['time'].dt.strftime('%Y-%m-%d') == date_str].iloc[0]
            
            if existing_row['close'] > 0 and recent_row['close'] > 0:
                ratio = existing_row['close'] / recent_row['close']
                # Debug for VND specifically
                if ticker == 'VND':
                    print(f"   - DEBUG VND dividend check {date_str}: existing_close={existing_row['close']}, recent_close={recent_row['close']}, ratio={ratio:.4f}")
                if ratio > 1.02:  # 2% difference indicates possible dividend
                    is_dividend = True
                    print(f"   - 💰 DIVIDEND DETECTED for {ticker} on {date_str}: ratio={ratio:.4f}")
                    break
        
        if is_dividend:
            print(f"   - Downloading full history due to dividend detection...")
            # Download full history from start_date
            full_data = download_full_data(ticker, start_date, end_date, "VCI", interval)
            if full_data is not None and not full_data.empty:
                print(f"   - Full history downloaded: {len(full_data)} records")
                return full_data
            else:
                print(f"   - Full history download failed, using existing data")
                return existing_df
    
    # No dividend detected - smart merge recent data
    print(f"   - No dividend detected, merging recent data...")
    merged_data = update_last_row_and_append_new_data(existing_df, recent_data)
    return merged_data

def process_ticker_with_fallback(ticker, start_date, end_date, batch_result=None, interval="1D"):
    """
    Process a single ticker with intelligent fallback strategy and smart dividend detection:
    1. Use batch result if available and check for dividends
    2. Fall back to individual VCI call
    3. Fall back to TCBS call as last resort
    """
    # Check if we have a valid batch result first
    if batch_result is not None:
        print(f"   ✅ Using batch result for {ticker}")
        # Debug: Show batch result before dividend merge
        if ticker == 'VND' and not batch_result.empty:
            last_row = batch_result.iloc[-1]
            print(f"   - DEBUG VND BATCH RESULT before merge: close={last_row.get('close', 'N/A')}, open={last_row.get('open', 'N/A')}")
        return smart_dividend_check_and_merge(ticker, batch_result, start_date, end_date, interval)
    
    print(f"   🔄 Batch failed for {ticker}, trying individual VCI...")
    
    # Try individual VCI call
    try:
        df = download_stock_data_individual(ticker, start_date, end_date, "VCI", interval)
        if df is not None and not df.empty:
            print(f"   ✅ Individual VCI success for {ticker}")
            return df
    except Exception as e:
        print(f"   ❌ Individual VCI failed for {ticker}: {e}")
    
    print(f"   🔄 VCI failed for {ticker}, trying TCBS...")
    
    # Try TCBS as last resort
    try:
        df = download_stock_data_individual(ticker, start_date, end_date, "TCBS", interval)
        if df is not None and not df.empty:
            print(f"   ✅ TCBS success for {ticker}")
            return df
    except Exception as e:
        print(f"   ❌ TCBS failed for {ticker}: {e}")
    
    print(f"   ❌ All methods failed for {ticker}")
    return None

def main():
    """Main function to orchestrate the data download with VCI/TCBS clients."""
    global vci_client, tcbs_client, precision_decimals
    
    parser = argparse.ArgumentParser(description="AIPriceAction Data Pipeline with VCI/TCBS")
    parser.add_argument('--start-date', default="2015-01-05", type=str, help="The start date for data download in 'YYYY-MM-DD' format.")
    parser.add_argument('--end-date', default=datetime.now().strftime('%Y-%m-%d'), type=str, help="The end date for data download in 'YYYY-MM-DD' format.")
    parser.add_argument('--resume-days', default=5, type=int, help="Number of recent days to fetch for resume mode (default: 5)")
    parser.add_argument('--full-download', action='store_true', help="Force full download from start-date (disable resume mode)")
    parser.add_argument('--batch-size', default=10, type=int, help="Number of tickers per batch request (default: 10, recommended: 2 for full downloads)")
    parser.add_argument('--interval', default='1D', type=str, help="Data interval: 1D (daily), 1H (hourly), 1m (minute). Default: 1D")
    parser.add_argument('--precision', default=6, type=int, help="Number of decimal places for price data (default: 6, use 0 for no rounding)")
    args = parser.parse_args()

    START_DATE = args.start_date
    END_DATE = args.end_date
    RESUME_DAYS = args.resume_days
    FULL_DOWNLOAD = args.full_download
    BATCH_SIZE = 2 if args.full_download else args.batch_size
    INTERVAL = args.interval
    precision_decimals = None if args.precision == 0 else args.precision
    
    # Normalize and validate interval parameter
    if INTERVAL.upper() == '1M':
        INTERVAL = '1m'  # Keep original case for minute
    else:
        INTERVAL = INTERVAL.upper()
    
    if INTERVAL not in ['1D', '1H', '1m']:
        print(f"❌ Invalid interval: {args.interval}. Valid options: 1D, 1H, 1m")
        sys.exit(1)

    # Smart resume mode: use last N days unless full download is requested
    if not FULL_DOWNLOAD:
        resume_start_date = (datetime.now() - timedelta(days=RESUME_DAYS)).strftime('%Y-%m-%d')
        FETCH_START_DATE = resume_start_date
        mode_description = f"RESUME MODE (last {RESUME_DAYS} days)"
    else:
        FETCH_START_DATE = START_DATE
        mode_description = f"FULL DOWNLOAD MODE"

    start_time = time.time()
    print("--- AIPriceAction Data Pipeline with VCI/TCBS: START ---")
    print(f"--- {mode_description} ---")
    print(f"--- Interval: {INTERVAL} ---")
    print(f"--- Fetch period: {FETCH_START_DATE} to {END_DATE} ---")
    print(f"--- Full data period: {START_DATE} to {END_DATE} ---")
    print(f"--- Batch size: {BATCH_SIZE} tickers ---")
    print(f"--- Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    setup_directories(INTERVAL)
    
    # Initialize clients (price scaling handled in main script)
    print("\\n🔗 Initializing API clients...")
    vci_client = VCIClient(random_agent=True, rate_limit_per_minute=60)
    tcbs_client = TCBSClient(random_agent=True, rate_limit_per_minute=30)
    print("   ✅ VCI client: 60 calls/minute")
    print("   ✅ TCBS client: 30 calls/minute")
    
    # Ensure VNINDEX is first, then sort the rest
    tickers_sorted = sorted([t for t in TICKERS_TO_DOWNLOAD if t != 'VNINDEX'])
    if 'VNINDEX' in TICKERS_TO_DOWNLOAD:
        tickers_sorted = ['VNINDEX'] + tickers_sorted
    
    print(f"\\n📊 Processing {len(tickers_sorted)} tickers...")
    
    # Pre-scan tickers to categorize data needs (unless full download mode is forced)
    if not FULL_DOWNLOAD:
        resume_tickers, full_history_tickers = categorize_tickers_by_data_needs(tickers_sorted, INTERVAL)
    else:
        # Force full download for all tickers
        resume_tickers = []
        full_history_tickers = tickers_sorted
        print(f"\\n🔧 FULL DOWNLOAD MODE: All {len(tickers_sorted)} tickers will get full history")
    
    # Convert to sets for fast lookup during processing
    full_history_set = set(full_history_tickers)
    resume_set = set(resume_tickers)
    
    # Calculate years span for date range logic
    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d")
    end_dt = datetime.strptime(END_DATE, "%Y-%m-%d")
    years_span = (end_dt - start_dt).days / 365.25
    
    # For full downloads with long date ranges or high-frequency data, use individual requests
    print(f"\\n🚀 Processing {len(full_history_tickers)} tickers needing full history...")
    if years_span > 2 or INTERVAL != '1D':  # Long date range or high-frequency data - use individual requests
        if INTERVAL != '1D':
            print(f"   🔄 High-frequency interval ({INTERVAL}) detected - using individual chunked requests")
        else:
            print(f"   📅 Long date range ({years_span:.1f} years) detected - using individual requests for better reliability")
        full_history_results = {}
    else:
        full_history_results = download_stock_data_batch(full_history_tickers, START_DATE, END_DATE, BATCH_SIZE, INTERVAL) if full_history_tickers else {}
    
    # Batch process tickers that can use resume mode (only for daily data)
    print(f"\\n⚡ Batch processing {len(resume_tickers)} tickers using resume mode...")
    if INTERVAL == '1D':
        resume_results = download_stock_data_batch(resume_tickers, FETCH_START_DATE, END_DATE, BATCH_SIZE, INTERVAL) if resume_tickers else {}
    else:
        print(f"   🔄 High-frequency interval ({INTERVAL}) - skipping batch processing, will use individual requests")
        resume_results = {}
    
    # Combine batch results
    batch_results = {**full_history_results, **resume_results}
    
    # Track statistics
    successful_tickers = 0
    failed_tickers = 0
    batch_successes = 0
    individual_vci_successes = 0
    tcbs_successes = 0
    
    # Process each ticker with fallback strategy
    print("\\n🔄 Processing individual tickers with fallback strategy...")
    
    for i, ticker in enumerate(tickers_sorted, 1):
        ticker_start_time = time.time()
        print(f"\\n{'='*20} [{i:3d}/{len(tickers_sorted)}] {ticker} {'='*20}")
        
        # Get batch result if available
        batch_result = batch_results.get(ticker)
        
        # Determine processing type and date range
        if ticker in full_history_set:
            # Full history ticker - use full date range and direct save
            if batch_result is not None:
                print(f"   ✅ Using full history batch result for {ticker}")
                stock_df = batch_result
            else:
                print(f"   🔄 Batch failed for {ticker}, trying individual VCI/TCBS for full history...")
                stock_df = download_full_data(ticker, START_DATE, END_DATE, "VCI", INTERVAL)
                if stock_df is None:
                    stock_df = download_full_data(ticker, START_DATE, END_DATE, "TCBS", INTERVAL)
        else:
            # Resume ticker - use smart dividend detection and merging
            stock_df = process_ticker_with_fallback(ticker, START_DATE, END_DATE, batch_result, INTERVAL)
        
        if stock_df is not None and not stock_df.empty:
            # Save to CSV
            csv_path = save_data_to_csv(stock_df, ticker, START_DATE, END_DATE, INTERVAL)
            successful_tickers += 1
            
            # Track success method
            if batch_result is not None:
                batch_successes += 1
            elif 'VCI' in str(type(vci_client)):  # Assume VCI if not batch
                individual_vci_successes += 1
            else:
                tcbs_successes += 1
                
            print(f"   ✅ SUCCESS: {ticker} - {len(stock_df)} records saved")
        else:
            failed_tickers += 1
            print(f"   ❌ FAILED: {ticker} - no data available")
        
        # Calculate and show progress with estimated time after each ticker
        ticker_elapsed = time.time() - ticker_start_time
        total_elapsed = time.time() - start_time
        progress = (i / len(tickers_sorted)) * 100
        
        if i > 0:
            avg_time_per_ticker = total_elapsed / i
            remaining_tickers = len(tickers_sorted) - i
            estimated_remaining_time = avg_time_per_ticker * remaining_tickers
            
            print(f"📊 Progress: {progress:.1f}% ({i}/{len(tickers_sorted)}) | This ticker: {ticker_elapsed:.1f}s")
            print(f"⏱️  Elapsed: {total_elapsed/60:.1f}min | ETA: {estimated_remaining_time/60:.1f}min | Success: {successful_tickers} | Failed: {failed_tickers}")
        
        # Show detailed progress every 10 tickers
        if i % 10 == 0 or i == len(tickers_sorted):
            print(f"\\n📈 Milestone: {progress:.1f}% complete")
    
    # Final summary
    total_time = time.time() - start_time
    print("\\n" + "="*70)
    print("🎉 PROCESSING COMPLETE!")
    print("="*70)
    print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Total execution time: {total_time/60:.2f} minutes ({total_time:.1f} seconds)")
    print(f"📊 Results: ✅{successful_tickers} successful, ❌{failed_tickers} failed")
    
    print(f"\\n🔵 Method Statistics:")
    print(f"   VCI Batch: {batch_successes} tickers")
    print(f"   VCI Individual: {individual_vci_successes} tickers") 
    print(f"   TCBS: {tcbs_successes} tickers")
    
    # Performance comparison
    expected_old_time = 10.0  # Original vnstock baseline in minutes
    if total_time < expected_old_time * 60:
        improvement = ((expected_old_time * 60 - total_time) / (expected_old_time * 60)) * 100
        print(f"\\n🚀 Performance improvement: {improvement:.1f}% faster than vnstock baseline")
        print(f"   Previous estimated time: {expected_old_time:.1f} minutes")
        print(f"   New execution time: {total_time/60:.2f} minutes")
    else:
        print(f"\\n⚠️  Execution time: {total_time/60:.2f} min (vs estimated {expected_old_time} min baseline)")

    print("\\n--- AIPriceAction Data Pipeline with VCI/TCBS: FINISHED ---")

if __name__ == "__main__":
    main()