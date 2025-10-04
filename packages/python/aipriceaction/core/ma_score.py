"""MA Score calculations"""

import numpy as np
from typing import Dict, List
from ..data.types import StockDataPoint
from .matrix_utils import vectorize_ticker_data, calculate_ma_for_ticker


def extract_ma_values(
    ticker_data: Dict[str, List[StockDataPoint]],
    selected_tickers: List[str],
    date_range: List[str]
) -> Dict[str, List[Dict]]:
    """
    Extract MA values (ma10, ma20, ma50) for updating stock data
    Returns dict mapping ticker to list of {date, ma10, ma20, ma50}
    """
    # Vectorize ticker data into matrix format
    matrix, dates, ticker_index, date_index = vectorize_ticker_data(ticker_data, selected_tickers, date_range)
    num_tickers, num_dates, _ = matrix.shape

    # Extract close prices (index 3 in OHLCV)
    closes = matrix[:, :, 3].flatten()  # Flatten to 1D array

    # Pre-allocate MA arrays
    ma10_values = np.zeros(num_tickers * num_dates, dtype=np.float64)
    ma20_values = np.zeros(num_tickers * num_dates, dtype=np.float64)
    ma50_values = np.zeros(num_tickers * num_dates, dtype=np.float64)

    # Calculate MA for each ticker
    for t in range(num_tickers):
        ma10 = calculate_ma_for_ticker(closes, t, num_dates, 10)
        ma20 = calculate_ma_for_ticker(closes, t, num_dates, 20)
        ma50 = calculate_ma_for_ticker(closes, t, num_dates, 50)

        # Store in flattened arrays
        start_idx = t * num_dates
        end_idx = start_idx + num_dates
        ma10_values[start_idx:end_idx] = ma10
        ma20_values[start_idx:end_idx] = ma20
        ma50_values[start_idx:end_idx] = ma50

    # Convert to result format
    results = {}
    for t, ticker in enumerate(selected_tickers):
        ticker_ma_values = []
        for d in range(num_dates):
            idx = t * num_dates + d
            ma_dict = {"date": dates[d]}

            # Only include valid MA values (> 0 and finite)
            if ma10_values[idx] > 0 and np.isfinite(ma10_values[idx]):
                ma_dict["ma10"] = float(ma10_values[idx])
            if ma20_values[idx] > 0 and np.isfinite(ma20_values[idx]):
                ma_dict["ma20"] = float(ma20_values[idx])
            if ma50_values[idx] > 0 and np.isfinite(ma50_values[idx]):
                ma_dict["ma50"] = float(ma50_values[idx])

            ticker_ma_values.append(ma_dict)

        results[ticker] = ticker_ma_values

    return results


def calculate_bulk_ma_scores(
    ticker_data: Dict[str, List[StockDataPoint]],
    selected_tickers: List[str],
    config: Dict
) -> Dict:
    """Placeholder for bulk MA score calculations"""
    # TODO: Implement for example 02
    return {"result": {}, "metrics": {}}
