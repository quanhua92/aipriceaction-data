# Python Package Setup Guide

## Prerequisites

- Python 3.13 or higher
- `uv` package manager (recommended) or `pip`

## Installation

### Option 1: Using uv (Recommended)

```bash
# Navigate to Python package directory
cd packages/python

# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt
```

### Option 2: Using pip + venv

```bash
# Navigate to Python package directory
cd packages/python

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# OR
.venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

## Running Examples

### Example 01: Basic Data (VNINDEX + MA values)

```bash
uv run python examples/01_basic_data.py
```

**Output:**
- VNINDEX OHLCV data
- Moving averages (MA10, MA20, MA50)
- Latest 10 trading days
- Validation against expected values

### Example 02: Multi-Ticker Analysis

```bash
uv run python examples/02_multi_data.py
```

**Output:**
- VNINDEX benchmark data
- 4 stock tickers (VIC, VCB, CTG, VIX)
- MA scores for each ticker
- Latest 10 trading days per ticker

### Example 03: Money Flow Analysis

```bash
uv run python examples/03_money_flow.py
```

**Output:**
- Vectorized money flow calculations
- Activity Flow and Dollar Flow
- Trend Score (10-day rolling average)
- 6 validation tickers (BID, CTG, TCB, VCB, VIC, VIX)

## Running All Tests

```bash
./test_all.sh
```

## Package Structure

```
packages/python/
├── aipriceaction/           # Main package
│   ├── data/                # Data loading
│   │   ├── types.py         # Data types
│   │   └── csv_service.py   # CSV loading service
│   ├── core/                # Core calculations
│   │   ├── matrix_utils.py  # Vectorized operations
│   │   ├── ma_score.py      # MA calculations
│   │   └── money_flow.py    # Money flow calculations
│   └── utils/               # Utilities
│       ├── formatters.py    # Number formatting
│       └── validators.py    # Validation helpers
├── examples/                # Example scripts
│   ├── 01_basic_data.py     # VNINDEX + MA
│   ├── 02_multi_data.py     # Multi-ticker
│   └── 03_money_flow.py     # Money flow
├── requirements.txt         # Dependencies
├── test_all.sh             # Test runner
└── README.md               # Documentation
```

## Key Features

### Vectorized Operations with NumPy

All calculations use NumPy arrays for maximum performance:

- **Matrix format**: `[tickers, dates, OHLCV fields]`
- **Vectorized MA**: Simple moving averages
- **Vectorized Money Flow**: Activity & Dollar flows
- **Trend Scores**: Rolling window calculations

### Exact TypeScript Match

The Python implementation produces identical results to the TypeScript version:

- Same formulas for all calculations
- Same data structures
- Same output format
- 5% tolerance validation

### Money Flow Formula

**Normal case:**
```
multiplier = (close - effective_low - (effective_high - close)) / effective_range
where:
  effective_high = max(high, open)
  effective_low = min(low, open)
  effective_range = effective_high - effective_low
```

**Limit move case (O=H=L=C):**
```
multiplier = +1 if price_change > 6.5%
            -1 if price_change < -6.5%
             0 otherwise
```

**Flows:**
```
Activity Flow = multiplier × volume
Dollar Flow = multiplier × close × volume
Flow % = (absolute_flow / daily_total) × 100
Trend Score = 10-day average of absolute flow %
```

## Troubleshooting

### Import Errors

If you get import errors, make sure you're running from the correct directory:

```bash
# Should be in packages/python/
pwd  # Should show: .../packages/python
```

### Missing Dependencies

```bash
# Reinstall dependencies
uv pip install -r requirements.txt --force-reinstall
```

### Data Not Found

The package expects market data in:
```
../../market_data/  # Relative to packages/python/
```

If data is missing, check the path in `CSVDataService.py`.

## Performance

Typical performance on M1 Mac:

- **Example 01**: VNINDEX (2146 points) - ~50ms
- **Example 02**: 4 tickers × 60 days - ~100ms
- **Example 03**: 6 tickers × 25 days with money flow - ~150ms

All calculations are vectorized using NumPy for optimal performance.
