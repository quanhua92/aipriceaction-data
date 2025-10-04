"""Money Flow calculations"""

from typing import Dict, List
from ..data.types import StockDataPoint


def calculate_bulk_money_flow(
    ticker_data: Dict[str, List[StockDataPoint]],
    selected_tickers: List[str],
    config: Dict,
    vnindex_data: List[StockDataPoint] = None,
    most_recent_date = None
) -> Dict:
    """Placeholder for bulk money flow calculations"""
    # TODO: Implement for example 02 and 03
    return {"result": {}, "metrics": {}}
