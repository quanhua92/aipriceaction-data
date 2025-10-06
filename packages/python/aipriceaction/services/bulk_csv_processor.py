"""Bulk CSV Processor

Master processor that:
1. Downloads all original CSVs to market_data/
2. Loads everything into memory
3. Calculates money flow with full market context
4. Writes enhanced CSVs back to market_data/
5. Generates cache files (60d, 180d, 365d) from enhanced data
"""

import pandas as pd
import requests
from io import StringIO
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class BulkCSVProcessor:
    """Process all market CSVs in bulk with full market context"""

    API_BASE_URL = "https://api.aipriceaction.com/raw"
    MARKET_DATA_URL = f"{API_BASE_URL}/market_data"

    def __init__(self, output_dir: str = "/tmp/market_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.vnindex_df: Optional[pd.DataFrame] = None
        self.all_tickers_df: Optional[pd.DataFrame] = None
        self.enhanced_df: Optional[pd.DataFrame] = None

    def download_original_csv(self, ticker: str) -> Optional[pd.DataFrame]:
        """Download original CSV (7 columns)"""
        url = f"{self.MARKET_DATA_URL}/{ticker}.csv"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            df = pd.read_csv(StringIO(response.text))
            df['date'] = pd.to_datetime(df['time'])
            return df.sort_values('date')
        except Exception as e:
            print(f"  ⚠️  {ticker}: {e}")
            return None

    def download_all_originals(self, tickers: List[str]) -> pd.DataFrame:
        """Download all original CSVs and combine"""
        print(f"📥 Downloading {len(tickers)} original CSVs...")

        all_dfs = []
        for i, ticker in enumerate(tickers, 1):
            df = self.download_original_csv(ticker)
            if df is not None:
                all_dfs.append(df)

            if i % 25 == 0:
                print(f"  Progress: {i}/{len(tickers)}")

        combined = pd.concat(all_dfs, ignore_index=True)
        combined = combined.sort_values(['ticker', 'date'])

        print(f"✅ Downloaded {len(all_dfs)}/{len(tickers)} tickers")
        print(f"   Total rows: {len(combined):,}")
        print(f"   Date range: {combined['time'].min()} to {combined['time'].max()}")

        self.all_tickers_df = combined
        return combined

    def download_vnindex(self) -> pd.DataFrame:
        """Download VNINDEX for volume weighting"""
        print("📊 Downloading VNINDEX...")
        df = self.download_original_csv("VNINDEX")
        if df is None:
            raise RuntimeError("Failed to download VNINDEX")

        print(f"✅ VNINDEX: {len(df)} rows")
        self.vnindex_df = df
        return df

    def enhance_all_data(self):
        """Enhance all loaded data with money flow calculations"""
        from .csv_enhancement_engine import CSVEnhancementEngine

        if self.all_tickers_df is None or self.vnindex_df is None:
            raise RuntimeError("Must download data first")

        print("\n📈 Enhancing all data with calculated columns...")
        print(f"   Processing {len(self.all_tickers_df):,} rows...")

        self.enhanced_df = CSVEnhancementEngine.enhance_dataframe(
            df=self.all_tickers_df,
            vnindex_df=self.vnindex_df,
            all_tickers_df=self.all_tickers_df  # Full market context
        )

        print(f"✅ Enhanced {len(self.enhanced_df):,} rows")
        print(f"   Columns: {len(self.enhanced_df.columns)}")

    def write_individual_csvs(self):
        """Write enhanced CSVs to market_data/ folder"""
        from .csv_enhancement_engine import CSVEnhancementEngine

        if self.enhanced_df is None:
            raise RuntimeError("Must enhance data first")

        print(f"\n💾 Writing enhanced CSVs to {self.output_dir}...")

        tickers = self.enhanced_df['ticker'].unique()
        for i, ticker in enumerate(tickers, 1):
            ticker_df = self.enhanced_df[self.enhanced_df['ticker'] == ticker].copy()
            ticker_df = CSVEnhancementEngine.format_for_csv(ticker_df)

            output_path = self.output_dir / f"{ticker}.csv"
            ticker_df.to_csv(output_path, index=False)

            if i % 25 == 0:
                print(f"  Progress: {i}/{len(tickers)}")

        print(f"✅ Written {len(tickers)} enhanced CSVs")

    def generate_cache_file(self, days: int, output_path: str):
        """Generate cache file by downloading original cache and looking up enhanced values

        Flow:
        1. Download original cache file from server (has date ranges and tickers)
        2. For each row, look up enhanced values from market_data/{ticker}.csv
        3. Write combined cache file with enhanced columns
        """
        print(f"\n📦 Generating {days}-day cache file...")

        # Step 1: Download original cache file from server
        cache_url_map = {
            60: f"{self.API_BASE_URL}/cache/ticker_60_days.csv",
            180: f"{self.API_BASE_URL}/cache/ticker_180_days.csv",
            365: f"{self.API_BASE_URL}/cache/ticker_365_days.csv"
        }

        if days not in cache_url_map:
            raise ValueError(f"Unsupported cache duration: {days} days")

        cache_url = cache_url_map[days]

        print(f"   Downloading original cache from {cache_url}...")
        try:
            response = requests.get(cache_url, timeout=30)
            response.raise_for_status()
            original_cache_df = pd.read_csv(StringIO(response.text))
            print(f"   ✅ Downloaded {len(original_cache_df)} rows from server")
        except Exception as e:
            print(f"   ⚠️  Failed to download cache: {e}")
            print(f"   Falling back to filtering enhanced_df by last {days} days...")

            # Fallback: use enhanced_df
            if self.enhanced_df is None:
                raise RuntimeError("No enhanced data available")

            max_date = pd.to_datetime(self.enhanced_df['time'].max())
            cutoff_date = max_date - timedelta(days=days)
            original_cache_df = self.enhanced_df[
                pd.to_datetime(self.enhanced_df['time']) >= cutoff_date
            ].copy()

        # Step 2: Load all enhanced CSVs into a lookup dict
        print(f"   Loading enhanced values from {self.output_dir}...")
        enhanced_lookup = {}  # {ticker: {date: row_dict}}

        for ticker in original_cache_df['ticker'].unique():
            csv_path = self.output_dir / f"{ticker}.csv"
            if csv_path.exists():
                ticker_df = pd.read_csv(csv_path)
                enhanced_lookup[ticker] = {
                    row['time']: row.to_dict()
                    for _, row in ticker_df.iterrows()
                }

        print(f"   ✅ Loaded enhanced values for {len(enhanced_lookup)} tickers")

        # Step 3: Build enhanced cache by looking up values
        enhanced_rows = []
        for _, row in original_cache_df.iterrows():
            ticker = row['ticker']
            date = row['time']

            # Look up enhanced values
            if ticker in enhanced_lookup and date in enhanced_lookup[ticker]:
                enhanced_row = enhanced_lookup[ticker][date]
            else:
                # Fallback: use original row with NaN for enhanced columns
                enhanced_row = row.to_dict()
                enhanced_row.update({
                    'ma10': None, 'ma20': None, 'ma50': None,
                    'ma10_score': None, 'ma20_score': None, 'ma50_score': None,
                    'money_flow': None, 'dollar_flow': None, 'trend_score': None
                })

            enhanced_rows.append(enhanced_row)

        # Step 4: Create DataFrame and format
        cache_df = pd.DataFrame(enhanced_rows)

        from .csv_enhancement_engine import CSVEnhancementEngine
        cache_df = CSVEnhancementEngine.format_for_csv(cache_df)
        cache_df.to_csv(output_path, index=False)

        tickers = cache_df['ticker'].nunique()
        rows = len(cache_df)
        date_range = f"{cache_df['time'].min()} to {cache_df['time'].max()}"

        print(f"✅ Cache file: {output_path}")
        print(f"   Tickers: {tickers}, Rows: {rows:,}")
        print(f"   Date range: {date_range}")

    def generate_all_cache_files(self):
        """Generate all cache files (60d, 180d, 365d)"""
        cache_dir = self.output_dir.parent / "cache"
        cache_dir.mkdir(exist_ok=True)

        self.generate_cache_file(72, str(cache_dir / "ticker_60_days.csv"))   # 60 + 20% buffer
        self.generate_cache_file(216, str(cache_dir / "ticker_180_days.csv"))  # 180 + 20% buffer
        self.generate_cache_file(438, str(cache_dir / "ticker_365_days.csv"))  # 365 + 20% buffer

    def process_all(self, tickers: List[str]):
        """Complete pipeline: download → enhance → write"""
        print("=" * 70)
        print("🚀 Bulk CSV Processing Pipeline")
        print("=" * 70)

        # Step 1: Download
        self.download_vnindex()
        self.download_all_originals(tickers)

        # Step 2: Enhance with full market context
        self.enhance_all_data()

        # Step 3: Write enhanced individual CSVs
        self.write_individual_csvs()

        # Step 4: Generate cache files
        self.generate_all_cache_files()

        print("\n" + "=" * 70)
        print("✅ Bulk processing complete!")
        print(f"📁 Enhanced CSVs: {self.output_dir}")
        print(f"📁 Cache files: {self.output_dir.parent / 'cache'}")
        print("=" * 70)
