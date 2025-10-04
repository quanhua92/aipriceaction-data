"""CSV Enhancement Engine

Modular system for enhancing CSV files with calculated columns.
Handles both cached multi-ticker files (60d, 180d, 365d) and individual CSV files.

Uses Example 03's matrix_utils for accurate money flow calculations.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from aipriceaction.core.matrix_utils import (
    vectorize_ticker_data,
    calculate_money_flow_matrix,
    calculate_daily_totals,
    calculate_flow_percentages,
    calculate_rolling_trend_scores,
    calculate_vnindex_volume_scaling,
    apply_vnindex_volume_scaling
)
from aipriceaction.data.types import StockDataPoint


class CSVEnhancementEngine:
    """Engine for calculating and adding technical indicators to CSV data"""

    @staticmethod
    def calculate_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MA10, MA20, MA50 using pandas rolling windows"""
        df = df.copy()
        df['ma10'] = df['close'].rolling(window=10, min_periods=10).mean()
        df['ma20'] = df['close'].rolling(window=20, min_periods=20).mean()
        df['ma50'] = df['close'].rolling(window=50, min_periods=50).mean()
        return df

    @staticmethod
    def calculate_ma_scores(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MA scores as percentage from moving average"""
        df = df.copy()
        df['ma10_score'] = ((df['close'] - df['ma10']) / df['ma10'] * 100).where(df['ma10'].notna())
        df['ma20_score'] = ((df['close'] - df['ma20']) / df['ma20'] * 100).where(df['ma20'].notna())
        df['ma50_score'] = ((df['close'] - df['ma50']) / df['ma50'] * 100).where(df['ma50'].notna())
        return df

    @staticmethod
    def calculate_money_flow_with_matrix(
        stock_data: Dict[str, List[StockDataPoint]],
        vnindex_data: List[StockDataPoint]
    ) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
        """Calculate money flow using Example 03's matrix approach

        Args:
            stock_data: Dict of ticker -> list of StockDataPoints
            vnindex_data: List of VNINDEX StockDataPoints

        Returns:
            Tuple of (money_flow_dict, trend_score_dict)
            Each dict maps ticker -> {date -> value}
        """
        # Build date range from ticker data (reverse chronological like Example 03)
        all_dates = set()
        for ticker_points in stock_data.values():
            for point in ticker_points:
                all_dates.add(point.time)

        date_range = sorted(list(all_dates), reverse=True)

        # Get all tickers (exclude VNINDEX)
        all_tickers = [ticker for ticker in stock_data.keys() if ticker != "VNINDEX"]

        # Vectorize ticker data into matrices (Example 03 approach)
        matrix, dates, ticker_index, date_index = vectorize_ticker_data(
            stock_data, all_tickers, date_range
        )

        # Calculate VNINDEX volume scaling
        vnindex_scaling = calculate_vnindex_volume_scaling(vnindex_data, dates)

        # Calculate money flow matrix
        money_flow_matrix = calculate_money_flow_matrix(
            matrix, len(date_range), len(all_tickers)
        )

        # Apply VNINDEX volume scaling
        scaled_money_flow = apply_vnindex_volume_scaling(
            money_flow_matrix, vnindex_scaling, len(all_tickers)
        )

        # Calculate daily totals and flow percentages
        daily_totals = calculate_daily_totals(scaled_money_flow, len(date_range), len(all_tickers))
        flow_percentages = calculate_flow_percentages(scaled_money_flow, daily_totals, len(all_tickers))

        # Calculate trend scores (10-day rolling average)
        trend_scores = calculate_rolling_trend_scores(flow_percentages, 10, len(all_tickers))

        # Convert matrices to dicts for DataFrame merging
        money_flow_dict = {}
        trend_score_dict = {}

        for t_idx, ticker in enumerate(all_tickers):
            money_flow_dict[ticker] = {}
            trend_score_dict[ticker] = {}

            for d_idx, date in enumerate(date_range):
                mf_value = flow_percentages['money_flow'][d_idx, t_idx]
                df_value = flow_percentages['dollar_flow'][d_idx, t_idx]
                ts_value = trend_scores[d_idx, t_idx]

                money_flow_dict[ticker][date] = {
                    'money_flow': mf_value if not np.isnan(mf_value) else None,
                    'dollar_flow': df_value if not np.isnan(df_value) else None
                }
                trend_score_dict[ticker][date] = ts_value if not np.isnan(ts_value) else None

        return money_flow_dict, trend_score_dict

    @staticmethod
    def calculate_trend_score(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate trend score as 10-day rolling average of absolute money flow

        Note: Requires money_flow column to exist. Operates per ticker.
        """
        df = df.copy()

        # Process each ticker separately
        trend_scores = []
        for ticker in df['ticker'].unique():
            ticker_df = df[df['ticker'] == ticker].copy()

            # Sort by date in reverse chronological order (newest first) for trend score
            ticker_df = ticker_df.sort_values('time', ascending=False)

            # Calculate 10-day rolling average of absolute money flow
            ticker_df['trend_score'] = ticker_df['money_flow'].abs().rolling(
                window=10, min_periods=10
            ).mean()

            trend_scores.append(ticker_df)

        # Combine and sort back to chronological order
        df = pd.concat(trend_scores).sort_values(['ticker', 'time'])

        return df

    @staticmethod
    def enhance_dataframe(
        df: pd.DataFrame,
        stock_data: Optional[Dict[str, List[StockDataPoint]]] = None,
        vnindex_data: Optional[List[StockDataPoint]] = None
    ) -> pd.DataFrame:
        """Complete enhancement pipeline for a DataFrame

        Args:
            df: Input DataFrame (single ticker or multi-ticker)
            stock_data: Dict of ticker -> list of StockDataPoints (for money flow)
            vnindex_data: List of VNINDEX StockDataPoints (for money flow)

        Returns:
            Enhanced DataFrame with all calculated columns
        """
        # Ensure proper column order per ticker
        df = df.sort_values(['ticker', 'time'])

        # Always calculate MA and MA Scores per ticker
        enhanced_dfs = []
        for ticker in df['ticker'].unique():
            ticker_df = df[df['ticker'] == ticker].copy()
            ticker_df = CSVEnhancementEngine.calculate_moving_averages(ticker_df)
            ticker_df = CSVEnhancementEngine.calculate_ma_scores(ticker_df)
            enhanced_dfs.append(ticker_df)

        df = pd.concat(enhanced_dfs, ignore_index=True)

        # Calculate money flow if we have market context
        if stock_data is not None and vnindex_data is not None:
            money_flow_dict, trend_score_dict = CSVEnhancementEngine.calculate_money_flow_with_matrix(
                stock_data, vnindex_data
            )

            # Merge money flow values into DataFrame
            df['money_flow'] = df.apply(
                lambda row: money_flow_dict.get(row['ticker'], {}).get(row['time'], {}).get('money_flow'),
                axis=1
            )
            df['dollar_flow'] = df.apply(
                lambda row: money_flow_dict.get(row['ticker'], {}).get(row['time'], {}).get('dollar_flow'),
                axis=1
            )
            df['trend_score'] = df.apply(
                lambda row: trend_score_dict.get(row['ticker'], {}).get(row['time']),
                axis=1
            )
        else:
            # Placeholder columns
            df['money_flow'] = np.nan
            df['dollar_flow'] = np.nan
            df['trend_score'] = np.nan

        return df

    @staticmethod
    def get_enhanced_columns() -> List[str]:
        """Get list of columns in enhanced CSV format"""
        return [
            'ticker', 'time', 'open', 'high', 'low', 'close', 'volume',
            'ma10', 'ma20', 'ma50',
            'ma10_score', 'ma20_score', 'ma50_score',
            'money_flow', 'dollar_flow', 'trend_score'
        ]

    @staticmethod
    def format_for_csv(df: pd.DataFrame) -> pd.DataFrame:
        """Format DataFrame for CSV output with proper column order and rounding"""
        # Ensure all enhanced columns exist
        for col in CSVEnhancementEngine.get_enhanced_columns():
            if col not in df.columns:
                df[col] = np.nan

        # Select columns in correct order
        df = df[CSVEnhancementEngine.get_enhanced_columns()].copy()

        # Round numeric values
        round_2 = ['open', 'high', 'low', 'close', 'ma10', 'ma20', 'ma50']
        round_4 = ['ma10_score', 'ma20_score', 'ma50_score', 'money_flow', 'dollar_flow', 'trend_score']

        for col in round_2:
            if col in df.columns:
                df[col] = df[col].round(2)

        for col in round_4:
            if col in df.columns:
                df[col] = df[col].round(4)

        # Volume as integer
        if 'volume' in df.columns:
            df['volume'] = df['volume'].round(0).astype('Int64')

        return df
