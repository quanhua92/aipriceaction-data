"""Number formatting utilities"""


def format_k(value: float) -> str:
    """Format number as thousands (k)"""
    if value >= 1000:
        return f"{value / 1000:.1f}k"
    return str(value)


def format_m(value: float) -> str:
    """Format volume as millions (M)"""
    if value >= 1000000:
        return f"{value / 1000000:.1f}M"
    return str(value)


def format_percent(value: float) -> str:
    """Format percentage"""
    return f"{value:.2f}%"


def format_decimal(value: float) -> str:
    """Format decimal with 2 places"""
    return f"{value:.2f}"
