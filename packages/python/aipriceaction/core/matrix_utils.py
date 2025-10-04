"""Matrix utilities for vectorized calculations using numpy"""

import numpy as np
from typing import Dict, List, Tuple
from ..data.types import StockDataPoint


def vectorize_ticker_data(
    ticker_data: Dict[str, List[StockDataPoint]],
    tickers: List[str],
    date_range: List[str]
) -> Tuple[np.ndarray, List[str], Dict[str, int], Dict[str, int]]:
    """
    Convert ticker data to vectorized 3D matrix format
    Shape: [tickers, dates, OHLCV fields]
    Returns: (matrix, dates, ticker_index, date_index)
    """
    num_tickers = len(tickers)
    num_dates = len(date_range)
    num_fields = 5  # OHLCV

    # Pre-allocate matrix (float64 like TypeScript)
    data = np.zeros((num_tickers, num_dates, num_fields), dtype=np.float64)

    # Create index maps
    ticker_index = {ticker: i for i, ticker in enumerate(tickers)}
    date_index = {date: i for i, date in enumerate(date_range)}

    # Fill matrix with ticker data
    for t, ticker in enumerate(tickers):
        ticker_points = ticker_data.get(ticker, [])

        # Create date lookup
        date_map = {point.time: point for point in ticker_points}

        for d, date in enumerate(date_range):
            point = date_map.get(date)
            if point:
                data[t, d, 0] = point.open
                data[t, d, 1] = point.high
                data[t, d, 2] = point.low
                data[t, d, 3] = point.close
                data[t, d, 4] = point.volume

    return data, date_range, ticker_index, date_index


def calculate_ma_for_ticker(
    closes: np.ndarray,
    ticker_index: int,
    num_dates: int,
    period: int
) -> np.ndarray:
    """
    Calculate moving average for a single ticker
    Matches TypeScript implementation exactly
    """
    ma_values = np.zeros(num_dates, dtype=np.float64)
    start_offset = ticker_index * num_dates

    for d in range(num_dates):
        if d < period - 1:
            # Not enough data for this MA period
            ma_values[d] = 0
            continue

        # Calculate moving average for the specified period
        total = 0.0
        for p in range(period):
            total += closes[start_offset + d - p]

        ma_values[d] = total / period

    return ma_values


def calculate_money_flow_matrix(
    matrix: np.ndarray,
    tickers: List[str],
    dates: List[str],
    ticker_data: Dict[str, List[StockDataPoint]] = None
) -> Dict:
    """
    Vectorized money flow calculation
    Matches TypeScript implementation exactly
    """
    num_tickers, num_dates, num_fields = matrix.shape

    # Pre-allocate result arrays
    activity_flows = np.zeros(num_tickers * num_dates, dtype=np.float64)
    dollar_flows = np.zeros(num_tickers * num_dates, dtype=np.float64)
    absolute_activity_flows = np.zeros(num_tickers * num_dates, dtype=np.float64)
    absolute_dollar_flows = np.zeros(num_tickers * num_dates, dtype=np.float64)
    volumes = np.zeros(num_tickers * num_dates, dtype=np.float64)
    closes = np.zeros(num_tickers * num_dates, dtype=np.float64)

    # Vectorized calculation
    for t in range(num_tickers):
        for d in range(num_dates):
            result_index = t * num_dates + d

            # Extract OHLCV values
            open_price = matrix[t, d, 0]
            high = matrix[t, d, 1]
            low = matrix[t, d, 2]
            close = matrix[t, d, 3]
            volume = matrix[t, d, 4]

            # Calculate money flow multiplier
            multiplier = 0.0

            if volume > 0:
                # Use effective range that includes opening price
                effective_high = max(high, open_price)
                effective_low = min(low, open_price)
                effective_range = effective_high - effective_low

                if effective_range == 0:
                    # Limit move case: O=H=L=C
                    prev_close = None

                    if d > 0:
                        # Use previous date from matrix
                        prev_close = matrix[t, d - 1, 3]
                    elif ticker_data:
                        # Look up from original data
                        ticker = tickers[t]
                        current_date = dates[d]
                        ticker_points = ticker_data.get(ticker, [])

                        for point in reversed(ticker_points):
                            if point.time < current_date:
                                prev_close = point.close
                                break

                    if prev_close and prev_close > 0:
                        price_change = (close - prev_close) / prev_close
                        # Vietnamese market: 6.5% limit moves
                        multiplier = 1 if price_change > 0.065 else (-1 if price_change < -0.065 else 0)
                else:
                    # Normal case
                    multiplier = (close - effective_low - (effective_high - close)) / effective_range

            # Calculate flows
            activity_flow = multiplier * volume
            dollar_flow = multiplier * close * volume

            # Store results
            activity_flows[result_index] = activity_flow
            dollar_flows[result_index] = dollar_flow
            absolute_activity_flows[result_index] = abs(activity_flow)
            absolute_dollar_flows[result_index] = abs(dollar_flow)
            volumes[result_index] = volume
            closes[result_index] = close

    return {
        "activity_flows": activity_flows,
        "dollar_flows": dollar_flows,
        "absolute_activity_flows": absolute_activity_flows,
        "absolute_dollar_flows": absolute_dollar_flows,
        "volumes": volumes,
        "closes": closes,
        "num_tickers": num_tickers,
        "num_dates": num_dates,
    }


def calculate_daily_totals(money_flow_matrix: Dict, flow_type: str = "activity") -> np.ndarray:
    """Calculate daily totals across all tickers"""
    num_tickers = money_flow_matrix["num_tickers"]
    num_dates = money_flow_matrix["num_dates"]

    absolute_flows = (
        money_flow_matrix["absolute_dollar_flows"] if flow_type == "dollar"
        else money_flow_matrix["absolute_activity_flows"]
    )

    daily_totals = np.zeros(num_dates, dtype=np.float64)

    for d in range(num_dates):
        total = 0.0
        for t in range(num_tickers):
            index = t * num_dates + d
            total += absolute_flows[index]
        daily_totals[d] = total

    return daily_totals


def calculate_flow_percentages(
    money_flow_matrix: Dict,
    daily_totals: np.ndarray,
    flow_type: str = "activity"
) -> np.ndarray:
    """Convert absolute flows to percentages"""
    num_tickers = money_flow_matrix["num_tickers"]
    num_dates = money_flow_matrix["num_dates"]

    absolute_flows = (
        money_flow_matrix["absolute_dollar_flows"] if flow_type == "dollar"
        else money_flow_matrix["absolute_activity_flows"]
    )

    percentages = np.zeros(num_tickers * num_dates, dtype=np.float64)

    for t in range(num_tickers):
        for d in range(num_dates):
            index = t * num_dates + d
            total = daily_totals[d]

            if total > 0:
                percentages[index] = (absolute_flows[index] / total) * 100

    return percentages


def calculate_rolling_trend_scores(
    signed_percentages: np.ndarray,
    num_tickers: int,
    num_dates: int,
    window_size: int = 10
) -> np.ndarray:
    """Calculate rolling trend scores (10-day moving average of absolute percentages)"""
    trend_scores = np.zeros(num_tickers * num_dates, dtype=np.float64)

    for t in range(num_tickers):
        for d in range(num_dates):
            # For reverse chronological order (newest first), look forward for history
            end_idx = min(num_dates - 1, d + window_size - 1)

            total = 0.0
            count = 0

            for i in range(d, end_idx + 1):
                index = t * num_dates + i
                total += abs(signed_percentages[index])
                count += 1

            trend_index = t * num_dates + d
            trend_scores[trend_index] = total / count if count > 0 else 0

    return trend_scores


def calculate_vnindex_volume_scaling(
    vnindex_data: List[StockDataPoint],
    date_range: List[str]
) -> Dict[str, float]:
    """
    Calculate VNINDEX volume scaling factors for each date
    Scaling ranges from 0.5 (min volume) to 1.0 (max volume)
    """
    vnindex_volumes = {}

    # Collect VNINDEX volumes for the date range
    for point in vnindex_data:
        if point.time in date_range:
            vnindex_volumes[point.time] = point.volume

    # If no volumes found, return 1.0 scaling for all dates
    if not vnindex_volumes:
        return {date: 1.0 for date in date_range}

    # Find min and max volumes
    volumes = list(vnindex_volumes.values())
    min_volume = min(volumes)
    max_volume = max(volumes)

    # Calculate scaling factors
    vnindex_volume_scaling = {}
    for date in date_range:
        if date in vnindex_volumes:
            if max_volume == min_volume:
                # All volumes are the same, no scaling needed
                vnindex_volume_scaling[date] = 1.0
            else:
                # Linear interpolation: 0.5 to 1.0 range
                normalized_volume = (vnindex_volumes[date] - min_volume) / (max_volume - min_volume)
                vnindex_volume_scaling[date] = 0.5 + normalized_volume * 0.5
        else:
            # No VNINDEX data for this date, use neutral scaling
            vnindex_volume_scaling[date] = 0.75  # Midpoint between 0.5 and 1.0

    return vnindex_volume_scaling


def apply_vnindex_volume_scaling(
    flows: np.ndarray,
    volume_scaling: Dict[str, float],
    dates: List[str],
    num_tickers: int
) -> np.ndarray:
    """
    Apply VNINDEX volume scaling to flows
    flows shape: [num_tickers * num_dates]
    """
    scaled_flows = np.zeros_like(flows)

    for t in range(num_tickers):
        for d, date in enumerate(dates):
            index = t * len(dates) + d
            scaling = volume_scaling.get(date, 1.0)
            scaled_flows[index] = flows[index] * scaling

    return scaled_flows
