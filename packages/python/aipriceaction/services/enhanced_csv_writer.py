"""Enhanced CSV Writer Service

Downloads CSV files and enhances them with calculated columns:
- Moving Averages: ma10, ma20, ma50
- MA Scores: ma10_score, ma20_score, ma50_score
- Money Flow: money_flow, dollar_flow
- Trend Score: trend_score (10-day rolling average)
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from io import StringIO
import requests

from ..data.types import StockDataPoint


class EnhancedCSVWriter:
    """Service for enhancing CSV files with calculated metrics"""

    API_BASE_URL = "https://api.aipriceaction.com/raw"
    MARKET_DATA_URL = f"{API_BASE_URL}/market_data"

    @classmethod
    def download_csv(cls, ticker: str) -> Optional[pd.DataFrame]:
        """Download CSV data for a ticker"""
        url = f"{cls.MARKET_DATA_URL}/{ticker}.csv"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            df = pd.read_csv(StringIO(response.text))
            df['date'] = pd.to_datetime(df['time'])
            return df.sort_values('date')  # Ensure chronological order for processing
        except Exception as e:
            print(f"⚠️  Failed to download {ticker}: {e}")
            return None

    @classmethod
    def calculate_moving_averages(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MA10, MA20, MA50 using rolling windows"""
        df = df.copy()

        # Calculate moving averages
        df['ma10'] = df['close'].rolling(window=10, min_periods=10).mean()
        df['ma20'] = df['close'].rolling(window=20, min_periods=20).mean()
        df['ma50'] = df['close'].rolling(window=50, min_periods=50).mean()

        return df

    @classmethod
    def calculate_ma_scores(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MA scores as percentage above/below MA"""
        df = df.copy()

        # MA Score = ((Close - MA) / MA) * 100
        df['ma10_score'] = ((df['close'] - df['ma10']) / df['ma10'] * 100).where(df['ma10'].notna())
        df['ma20_score'] = ((df['close'] - df['ma20']) / df['ma20'] * 100).where(df['ma20'].notna())
        df['ma50_score'] = ((df['close'] - df['ma50']) / df['ma50'] * 100).where(df['ma50'].notna())

        return df

    @classmethod
    def calculate_money_flow(
        cls,
        df: pd.DataFrame,
        vnindex_df: pd.DataFrame,
        all_tickers_data: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """Calculate money flow and dollar flow with VNINDEX volume weighting

        NOTE: This is a simplified placeholder. For accurate money flow calculations,
        use the vectorized approach from Example 03 with full market context.
        """
        df = df.copy()

        # Placeholder columns (NaN for now - complex calculation requires full market context)
        # Full implementation would use vectorized matrix calculations like Example 03
        df['money_flow'] = np.nan
        df['dollar_flow'] = np.nan

        return df

    @classmethod
    def calculate_trend_score(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate trend score as 10-day rolling average of absolute money flow"""
        df = df.copy()

        # Reverse for reverse chronological (newest first) - trend score requirement
        df_reversed = df.sort_values('date', ascending=False).copy()

        # Calculate 10-day rolling average of absolute money flow
        df_reversed['trend_score'] = df_reversed['money_flow'].abs().rolling(
            window=10, min_periods=10
        ).mean()

        # Reverse back to chronological order
        df = df_reversed.sort_values('date').copy()

        return df

    @classmethod
    def enhance_csv(
        cls,
        ticker: str,
        vnindex_df: pd.DataFrame,
        all_tickers_data: Dict[str, pd.DataFrame]
    ) -> Optional[pd.DataFrame]:
        """Download and enhance a single CSV file with all calculated columns"""
        # Download original CSV
        df = cls.download_csv(ticker)
        if df is None:
            return None

        print(f"📊 Enhancing {ticker}: {len(df)} rows")

        # Calculate all metrics
        df = cls.calculate_moving_averages(df)
        df = cls.calculate_ma_scores(df)
        df = cls.calculate_money_flow(df, vnindex_df, all_tickers_data)
        df = cls.calculate_trend_score(df)

        return df

    @classmethod
    def write_enhanced_csv(cls, df: pd.DataFrame, ticker: str, output_dir: str) -> str:
        """Write enhanced DataFrame to CSV file"""
        output_path = Path(output_dir) / f"{ticker}.csv"

        # Column order: original columns first, then enhancements
        columns = [
            'ticker', 'time', 'open', 'high', 'low', 'close', 'volume',
            'ma10', 'ma20', 'ma50',
            'ma10_score', 'ma20_score', 'ma50_score',
            'money_flow', 'dollar_flow', 'trend_score'
        ]

        # Select only columns that exist (some may be missing for early dates)
        available_columns = [col for col in columns if col in df.columns]
        df_output = df[available_columns].copy()

        # Round numeric columns for readability
        numeric_cols = ['open', 'high', 'low', 'close', 'volume',
                       'ma10', 'ma20', 'ma50',
                       'ma10_score', 'ma20_score', 'ma50_score',
                       'money_flow', 'dollar_flow', 'trend_score']

        for col in numeric_cols:
            if col in df_output.columns:
                if col in ['ma10_score', 'ma20_score', 'ma50_score', 'money_flow', 'dollar_flow', 'trend_score']:
                    df_output[col] = df_output[col].round(4)  # 4 decimals for percentages
                elif col == 'volume':
                    df_output[col] = df_output[col].round(0).astype('Int64')  # Integer for volume
                else:
                    df_output[col] = df_output[col].round(2)  # 2 decimals for prices

        # Write to CSV
        df_output.to_csv(output_path, index=False)
        print(f"✅ Written: {output_path}")

        return str(output_path)
