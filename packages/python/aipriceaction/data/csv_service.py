"""CSV data fetching service"""

import os
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path
from io import StringIO

from .types import StockDataPoint, DateRangeConfig


class CSVDataService:
    """Service for loading stock data from CSV files via API"""

    # API endpoints
    API_BASE_URL = "https://api.aipriceaction.com/raw"
    MARKET_DATA_URL = f"{API_BASE_URL}/market_data"
    TICKER_60_DAYS_URL = f"{API_BASE_URL}/ticker_60_days.csv"
    TICKER_180_DAYS_URL = f"{API_BASE_URL}/ticker_180_days.csv"
    TICKER_365_DAYS_URL = f"{API_BASE_URL}/ticker_365_days.csv"

    # Fallback: local market_data folder
    MARKET_DATA_PATH = Path(__file__).parents[4] / "market_data"

    @classmethod
    def fetch_vnindex(cls) -> List[StockDataPoint]:
        """Fetch VNINDEX data (ALL range for trading days)"""
        url = f"{cls.MARKET_DATA_URL}/VNINDEX.csv"

        try:
            # Fetch from API
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            csv_data = response.text

            # Parse CSV
            df = pd.read_csv(StringIO(csv_data))

        except Exception as e:
            # Fallback to local file
            print(f"Warning: API fetch failed ({e}), falling back to local file")
            csv_path = cls.MARKET_DATA_PATH / "VNINDEX.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"VNINDEX.csv not found at {csv_path} and API failed")
            df = pd.read_csv(csv_path)

        # Convert to StockDataPoint list
        data_points = []
        for _, row in df.iterrows():
            date = pd.to_datetime(row['time'])
            data_points.append(StockDataPoint(
                date=date,
                time=date.strftime('%Y-%m-%d'),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume'])
            ))

        return data_points

    @classmethod
    def fetch_tickers(cls, tickers: List[str], date_range: DateRangeConfig) -> Dict[str, List[StockDataPoint]]:
        """Fetch multiple tickers with date range filtering"""
        result = {}

        for ticker in tickers:
            try:
                data = cls.fetch_single_ticker(ticker, date_range)
                if data:
                    result[ticker] = data
            except Exception as e:
                print(f"Warning: Failed to fetch {ticker}: {e}")
                continue

        return result

    @classmethod
    def fetch_single_ticker(cls, ticker: str, date_range: DateRangeConfig) -> List[StockDataPoint]:
        """Fetch single ticker data with date range filtering"""
        url = f"{cls.MARKET_DATA_URL}/{ticker}.csv"

        try:
            # Fetch from API
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            csv_data = response.text

            # Parse CSV
            df = pd.read_csv(StringIO(csv_data))

        except Exception as e:
            # Fallback to local file
            csv_path = cls.MARKET_DATA_PATH / f"{ticker}.csv"
            if not csv_path.exists():
                return []
            df = pd.read_csv(csv_path)

        df['date'] = pd.to_datetime(df['time'])

        # Apply date range filter
        df = cls._filter_by_date_range(df, date_range)

        # Convert to StockDataPoint list
        data_points = []
        for _, row in df.iterrows():
            date = row['date']
            data_points.append(StockDataPoint(
                date=date,
                time=date.strftime('%Y-%m-%d'),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume'])
            ))

        return data_points

    @classmethod
    def fetch_all_tickers(cls, date_range: DateRangeConfig) -> Dict[str, List[StockDataPoint]]:
        """Fetch all tickers - from cache files or individual CSVs for ALL range"""

        # Special case: "ALL" range should download individual CSV files
        if date_range.range == "ALL":
            print("📊 ALL range requested - downloading individual CSV files from raw/market_data/...")
            return cls._fetch_all_tickers_individual(date_range)

        # Select appropriate cache file based on date range
        days_map = {
            "1W": 7, "2W": 14, "1M": 30, "2M": 60, "3M": 90,
            "4M": 120, "6M": 180, "1Y": 365, "2Y": 730
        }
        days = days_map.get(date_range.range, 90)

        # Choose cache file: 60d, 180d, or 365d
        if days <= 60:
            cache_url = cls.TICKER_60_DAYS_URL
        elif days <= 180:
            cache_url = cls.TICKER_180_DAYS_URL
        else:
            cache_url = cls.TICKER_365_DAYS_URL

        try:
            # Fetch from API
            response = requests.get(cache_url, timeout=30)
            response.raise_for_status()
            csv_data = response.text
            df = pd.read_csv(StringIO(csv_data))
        except Exception as e:
            print(f"Warning: Failed to fetch consolidated ticker data from {cache_url}: {e}")
            return {}

        # Convert 'date' column to datetime
        df['date'] = pd.to_datetime(df['time'])

        # Apply date range filter
        df = cls._filter_by_date_range(df, date_range)

        # Group by ticker
        result = {}
        for ticker in df['ticker'].unique():
            ticker_df = df[df['ticker'] == ticker].sort_values('date')

            data_points = []
            for _, row in ticker_df.iterrows():
                date = row['date']
                data_points.append(StockDataPoint(
                    date=date,
                    time=date.strftime('%Y-%m-%d'),
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume'])
                ))

            if data_points:
                result[ticker] = data_points

        return result

    @classmethod
    def _filter_by_date_range(cls, df: pd.DataFrame, date_range: DateRangeConfig) -> pd.DataFrame:
        """Filter DataFrame by date range"""
        if date_range.range == "CUSTOM":
            if date_range.startDate and date_range.endDate:
                df = df[(df['date'] >= date_range.startDate) & (df['date'] <= date_range.endDate)]
        elif date_range.range == "ALL":
            pass  # No filtering
        else:
            # Calculate days from range string
            days_map = {
                "1W": 7,
                "2W": 14,
                "1M": 30,
                "2M": 60,
                "3M": 90,
                "4M": 120,
                "6M": 180,
                "1Y": 365,
                "2Y": 730
            }
            days = days_map.get(date_range.range, 90)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

        return df

    @classmethod
    def _fetch_all_tickers_individual(cls, date_range: DateRangeConfig) -> Dict[str, List[StockDataPoint]]:
        """Fetch all tickers from individual CSV files (for ALL range) - ASYNC with ThreadPool"""
        import concurrent.futures
        from threading import Lock

        # Get list of all tickers
        all_tickers = []
        try:
            response = requests.get(cls.TICKER_60_DAYS_URL, timeout=10)
            response.raise_for_status()
            df = pd.read_csv(StringIO(response.text))
            all_tickers = df['ticker'].unique().tolist()
            print(f"Found {len(all_tickers)} tickers from cache")
        except Exception as e:
            print(f"Failed to get ticker list: {e}")
            return {}

        result = {}
        result_lock = Lock()
        failed_count = 0
        failed_lock = Lock()

        def fetch_ticker(ticker: str):
            nonlocal failed_count
            try:
                # Download individual CSV
                url = f"{cls.MARKET_DATA_URL}/{ticker}.csv"
                response = requests.get(url, timeout=15)
                response.raise_for_status()

                # Parse CSV
                df = pd.read_csv(StringIO(response.text))
                df['date'] = pd.to_datetime(df['time'])

                # Filter by date range (should be ALL, so no filtering)
                df = cls._filter_by_date_range(df, date_range)

                # Convert to StockDataPoint list
                data_points = []
                for _, row in df.iterrows():
                    data_points.append(StockDataPoint(
                        date=row['date'],
                        time=row['time'],
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=float(row['volume'])
                        ))

                if data_points:
                    with result_lock:
                        result[ticker] = data_points
                return True
            except Exception as e:
                with failed_lock:
                    failed_count += 1
                return False

        # Use ThreadPoolExecutor for parallel downloads
        print(f"Downloading {len(all_tickers)} CSVs in parallel (20 threads)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(fetch_ticker, ticker): ticker for ticker in all_tickers}
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                completed += 1
                if completed % 50 == 0:
                    print(f"  Progress: {completed}/{len(all_tickers)} ({100*completed//len(all_tickers)}%)")

        print(f"✅ Fetched {len(result)} tickers individually ({failed_count} failed)")
        return result
