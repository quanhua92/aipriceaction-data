"""CSV Data Loader

Handles loading data from different sources:
1. Cached multi-ticker files (ticker_60_days.csv, ticker_180_days.csv, ticker_365_days.csv)
2. Individual ticker files (market_data/{ticker}.csv)
3. VNINDEX data
"""

import pandas as pd
import requests
from io import StringIO
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class CSVDataLoader:
    """Loader for CSV data from various sources"""

    API_BASE_URL = "https://api.aipriceaction.com/raw"
    CACHE_60D_URL = f"{API_BASE_URL}/ticker_60_days.csv"
    CACHE_180D_URL = f"{API_BASE_URL}/ticker_180_days.csv"
    CACHE_365D_URL = f"{API_BASE_URL}/ticker_365_days.csv"
    MARKET_DATA_URL = f"{API_BASE_URL}/market_data"

    @classmethod
    def load_vnindex(cls) -> pd.DataFrame:
        """Load VNINDEX data"""
        url = f"{cls.MARKET_DATA_URL}/VNINDEX.csv"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            df = pd.read_csv(StringIO(response.text))
            df['date'] = pd.to_datetime(df['time'])
            return df.sort_values('date')
        except Exception as e:
            raise RuntimeError(f"Failed to load VNINDEX: {e}")

    @classmethod
    def load_cache_file(cls, cache_type: str = "60d") -> pd.DataFrame:
        """Load cached multi-ticker CSV file

        Args:
            cache_type: One of "60d", "180d", "365d"

        Returns:
            DataFrame with all tickers from cache file
        """
        cache_urls = {
            "60d": cls.CACHE_60D_URL,
            "180d": cls.CACHE_180D_URL,
            "365d": cls.CACHE_365D_URL
        }

        if cache_type not in cache_urls:
            raise ValueError(f"Invalid cache_type: {cache_type}. Must be one of: {list(cache_urls.keys())}")

        url = cache_urls[cache_type]

        try:
            print(f"📥 Loading {cache_type} cache file from {url}...")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            df = pd.read_csv(StringIO(response.text))
            df['date'] = pd.to_datetime(df['time'])
            df = df.sort_values(['ticker', 'date'])

            tickers = df['ticker'].unique()
            print(f"✅ Loaded {cache_type} cache: {len(tickers)} tickers, {len(df)} total rows")

            return df

        except Exception as e:
            raise RuntimeError(f"Failed to load {cache_type} cache: {e}")

    @classmethod
    def load_individual_csv(cls, ticker: str) -> pd.DataFrame:
        """Load individual ticker CSV from market_data folder

        Args:
            ticker: Ticker symbol

        Returns:
            DataFrame for single ticker
        """
        url = f"{cls.MARKET_DATA_URL}/{ticker}.csv"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            df = pd.read_csv(StringIO(response.text))
            df['date'] = pd.to_datetime(df['time'])
            df = df.sort_values('date')

            return df

        except Exception as e:
            raise RuntimeError(f"Failed to load {ticker}: {e}")

    @classmethod
    def load_all_individual_csvs(cls, tickers: List[str]) -> pd.DataFrame:
        """Load all individual ticker CSVs and combine

        Args:
            tickers: List of ticker symbols

        Returns:
            Combined DataFrame with all tickers
        """
        print(f"📥 Loading {len(tickers)} individual CSV files...")

        all_dfs = []
        failed = []

        for i, ticker in enumerate(tickers, 1):
            try:
                df = cls.load_individual_csv(ticker)
                all_dfs.append(df)
                if i % 10 == 0:
                    print(f"  Progress: {i}/{len(tickers)} tickers loaded...")
            except Exception as e:
                print(f"  ⚠️  {ticker}: {e}")
                failed.append(ticker)

        if not all_dfs:
            raise RuntimeError("Failed to load any ticker data")

        combined_df = pd.concat(all_dfs, ignore_index=True)
        combined_df = combined_df.sort_values(['ticker', 'date'])

        print(f"✅ Loaded {len(all_dfs)}/{len(tickers)} tickers successfully")
        if failed:
            print(f"⚠️  Failed tickers: {', '.join(failed)}")

        return combined_df

    @classmethod
    def determine_data_source(cls, days_back: int = 60) -> str:
        """Determine which data source to use based on date range

        Args:
            days_back: Number of days of historical data needed

        Returns:
            Data source type: "60d", "180d", "365d", or "individual"
        """
        if days_back <= 60:
            return "60d"
        elif days_back <= 180:
            return "180d"
        elif days_back <= 365:
            return "365d"
        else:
            return "individual"

    @classmethod
    def load_market_data(
        cls,
        tickers: Optional[List[str]] = None,
        days_back: int = 60,
        force_individual: bool = False
    ) -> Tuple[pd.DataFrame, str]:
        """Load market data from optimal source

        Args:
            tickers: List of tickers (None = all tickers from cache)
            days_back: Number of days of historical data needed
            force_individual: Force loading from individual CSV files

        Returns:
            Tuple of (DataFrame, source_type)
        """
        if force_individual:
            if not tickers:
                raise ValueError("Must specify tickers when using individual CSV files")
            df = cls.load_all_individual_csvs(tickers)
            return df, "individual"

        # Determine best source
        source = cls.determine_data_source(days_back)

        if source == "individual":
            if not tickers:
                raise ValueError("Must specify tickers for >365 days of data")
            df = cls.load_all_individual_csvs(tickers)
        else:
            df = cls.load_cache_file(source)

            # Filter to requested tickers if specified
            if tickers:
                df = df[df['ticker'].isin(tickers)]

        return df, source
