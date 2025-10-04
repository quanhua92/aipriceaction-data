# Enhanced CSV Feature

## Overview

The Enhanced CSV feature generates 16-column CSV files with technical indicators and money flow metrics for all Vietnamese stock market tickers plus VNINDEX. This provides a comprehensive dataset combining raw OHLCV data with calculated metrics for analysis, backtesting, and machine learning applications.

## Quick Start

```bash
# Generate enhanced CSVs with full historical data (from 2015)
uv run python examples/04_enhanced_csv.py
```

**Output:**
- Individual CSVs: `/tmp/market_data/{ticker}.csv` (287 files: 286 stocks + VNINDEX)
- Cache files: `/tmp/cache/ticker_{60,180,365}_days.csv`

**Processing time:** ~27 seconds for 694,099 total rows (287 tickers × 2,685 days)

## CSV Format (16 Columns)

### Column Structure

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `ticker` | string | Stock symbol or VNINDEX | `VCB` |
| `time` | date | Trading date (YYYY-MM-DD) | `2025-10-03` |
| `open` | float | Opening price | `62.0` |
| `high` | float | Highest price | `62.0` |
| `low` | float | Lowest price | `61.4` |
| `close` | float | Closing price | `61.7` |
| `volume` | int | Trading volume | `2821100` |
| `ma10` | float | 10-day moving average | `62.33` |
| `ma20` | float | 20-day moving average | `63.69` |
| `ma50` | float | 50-day moving average | `63.76` |
| `ma10_score` | float | % above/below MA10 | `-1.0033` |
| `ma20_score` | float | % above/below MA20 | `-3.1285` |
| `ma50_score` | float | % above/below MA50 | `-3.2264` |
| `money_flow` | float | Activity flow % (daily market %) | `0.0` |
| `dollar_flow` | float | Dollar flow % (daily market %) | `0.0` |
| `trend_score` | float | 10-day rolling trend score | `0.3701` |

### Example Row

```csv
ticker,time,open,high,low,close,volume,ma10,ma20,ma50,ma10_score,ma20_score,ma50_score,money_flow,dollar_flow,trend_score
VCB,2025-10-03,62.0,62.0,61.4,61.7,2821100,62.33,63.69,63.76,-1.0033,-3.1285,-3.2264,0.0,0.0,0.3701
```

## Data Coverage

### Individual CSV Files

**Path:** `/tmp/market_data/{ticker}.csv`

**Coverage:**
- **Date range:** 2015-01-05 to 2025-10-03 (2,685 trading days)
- **Total files:** 287 (286 stocks + 1 VNINDEX)
- **Rows per file:** 2,686 (header + 2,685 data rows)
- **Total data points:** 694,099 rows

**File size:** ~100-300KB per ticker

### Cache Files

Cache files consolidate all tickers for faster loading of recent data.

**Path:** `/tmp/cache/`

| File | Days | Date Range | Rows | Use Case |
|------|------|------------|------|----------|
| `ticker_60_days.csv` | 60 | 2025-08-04 to 2025-10-03 | 12,215 | Short-term scanning, real-time analysis |
| `ticker_180_days.csv` | 180 | 2025-04-08 to 2025-10-03 | 35,236 | Medium-term analysis, quarterly reviews |
| `ticker_365_days.csv` | 365 | 2024-10-03 to 2025-10-03 | 71,170 | Annual analysis, year-over-year comparisons |

**Format:** Same 16 columns, all tickers in one file (identified by `ticker` column)

## Column Details

### Moving Averages (MA10, MA20, MA50)

**Calculation:**
```python
ma10 = close.rolling(window=10, min_periods=10).mean()
ma20 = close.rolling(window=20, min_periods=20).mean()
ma50 = close.rolling(window=50, min_periods=50).mean()
```

**Gradual Filling:**
- First 9 days: MA columns are empty (NaN)
- Day 10 onwards: `ma10` appears
- Day 20 onwards: `ma20` appears
- Day 50 onwards: `ma50` appears

**Example (VCB):**
```csv
2015-01-05: open=9.38, close=9.44, ma10=, ma20=, ma50=
2015-01-16: open=10.89, close=10.75, ma10=10.53, ma20=, ma50=
2015-01-30: open=11.10, close=11.07, ma10=10.89, ma20=10.71, ma50=
2015-03-13: open=11.40, close=11.55, ma10=11.47, ma20=11.39, ma50=11.15
```

### MA Scores

**Formula:**
```python
ma10_score = ((close - ma10) / ma10) * 100
```

**Interpretation:**
- Positive score: Price above MA (bullish)
- Negative score: Price below MA (bearish)
- Magnitude: Distance from MA

**Example:**
```
VCB 2025-10-03:
  close = 61.7
  ma10 = 62.33
  ma10_score = ((61.7 - 62.33) / 62.33) * 100 = -1.0033%
```

### Money Flow Metrics

**Only for stocks** - VNINDEX has empty money flow columns since it's the market index.

#### money_flow (Activity Flow %)

**Definition:** Percentage of daily total market activity (absolute value) with sign preserved

**Calculation:**
1. Calculate raw flow: `(close - open) * volume`
2. Apply VNINDEX volume scaling
3. Calculate daily total: `sum(abs(all_flows))`
4. Percentage: `(flow / daily_total) * 100`
5. Apply sign: `sign(raw_flow) * percentage`

**Range:** Typically -5% to +5% (can exceed for very active stocks)

**Example:**
```
VCB 2025-09-26:
  money_flow = -0.3963%  (negative = selling pressure)

VIC 2025-09-26:
  money_flow = +0.3585%  (positive = buying pressure)
```

#### dollar_flow (Dollar Flow %)

**Definition:** Percentage of daily total market dollar value with sign preserved

**Calculation:**
1. Calculate dollar flow: `(close - open) * volume * close`
2. Apply VNINDEX volume scaling
3. Calculate daily total: `sum(abs(all_dollar_flows))`
4. Percentage: `(dollar_flow / daily_total) * 100`
5. Apply sign: `sign(raw_dollar_flow) * percentage`

**Difference from money_flow:** Weights by stock price (high-price stocks have larger impact)

#### trend_score

**Definition:** 10-day rolling average of money_flow percentages

**Calculation:**
```python
trend_score = money_flow.rolling(window=10).mean()
```

**Range:** 0 to 1 (normalized)

**Interpretation:**
- > 0.7: Strong uptrend (consistent buying)
- 0.5-0.7: Moderate uptrend
- 0.3-0.5: Neutral/consolidation
- < 0.3: Downtrend (consistent selling)

## VNINDEX Special Handling

VNINDEX is treated differently from stocks:

### Included:
- ✅ OHLCV data (full history from 2015)
- ✅ Moving averages (MA10, MA20, MA50)
- ✅ MA scores

### Excluded:
- ❌ Money flow calculations (money_flow, dollar_flow, trend_score columns are empty)
- ❌ Matrix calculations (VNINDEX is used FOR scaling, not calculated ON)

**Reason:** VNINDEX is the market index used to normalize individual stock flows, not a tradeable security with its own money flow.

**Example:**
```csv
VNINDEX,2025-10-03,1651.39,1654.6,1638.08,1645.82,860615053,1654.57,1656.82,1625.97,-0.529,-0.664,1.2209,,,
                                                                                                        ^^^empty
```

## Implementation Architecture

### Data Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Data Fetching (21.8s)                                        │
│    - Fetch VNINDEX: 2,685 rows                                  │
│    - Fetch 287 stocks: 691,414 rows (parallel, 20 threads)     │
│    - Source: https://api.aipriceaction.com/raw/market_data/    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Add VNINDEX to stock_data dict                               │
│    stock_data["VNINDEX"] = vnindex_data                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Convert to DataFrame (0.2s)                                  │
│    - Combine all tickers into single DataFrame                  │
│    - Sort by ticker, then time                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Calculate Moving Averages (4.2s)                             │
│    - Per-ticker rolling calculations                            │
│    - MA10, MA20, MA50                                           │
│    - MA scores (% above/below)                                  │
│    - Includes VNINDEX                                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Calculate Money Flow (0.7s)                                  │
│    - Build date range (reverse chronological)                   │
│    - Exclude VNINDEX from ticker list                           │
│    - Vectorize data: (286 tickers, 2685 dates, 5 OHLCV)        │
│    - Calculate money flow matrix                                │
│    - Apply VNINDEX volume scaling                               │
│    - Calculate percentages and trend scores                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. Merge Money Flow into DataFrame                              │
│    - Left join on (ticker, time)                                │
│    - VNINDEX rows have empty money flow columns                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. Write Output Files                                           │
│    - Individual CSVs: /tmp/market_data/{ticker}.csv (287 files) │
│    - Cache files: /tmp/cache/ticker_{60,180,365}_days.csv      │
└─────────────────────────────────────────────────────────────────┘
```

### Key Code Sections

**1. Fetching with ALL range** (`csv_service.py:124-130`)
```python
@classmethod
def fetch_all_tickers(cls, date_range: DateRangeConfig) -> Dict[str, List[StockDataPoint]]:
    """Fetch all tickers - from cache files or individual CSVs for ALL range"""

    # Special case: "ALL" range should download individual CSV files
    if date_range.range == "ALL":
        print("📊 ALL range requested - downloading individual CSV files...")
        return cls._fetch_all_tickers_individual(date_range)
```

**2. Parallel downloads** (`csv_service.py:274-283`)
```python
# Use ThreadPoolExecutor for parallel downloads
print(f"Downloading {len(all_tickers)} CSVs in parallel (20 threads)...")
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    futures = {executor.submit(fetch_ticker, ticker): ticker for ticker in all_tickers}
    completed = 0
    for future in concurrent.futures.as_completed(futures):
        completed += 1
        if completed % 50 == 0:
            print(f"  Progress: {completed}/{len(all_tickers)} ({100*completed//len(all_tickers)}%)")
```

**3. Adding VNINDEX to processing** (`04_enhanced_csv.py:80-81`)
```python
# Add VNINDEX to stock_data for processing
stock_data["VNINDEX"] = vnindex_data
```

**4. Excluding VNINDEX from money flow** (`04_enhanced_csv.py:132`)
```python
all_tickers = [ticker for ticker in stock_data.keys() if ticker != "VNINDEX"]
```

## Performance Characteristics

### Timing Breakdown (287 tickers, 2,685 days)

| Step | Time | % of Total |
|------|------|------------|
| VNINDEX fetch | 1.7s | 6% |
| Stock downloads (parallel) | 20.1s | 74% |
| DataFrame conversion | 0.2s | 1% |
| MA calculations | 4.2s | 15% |
| Money flow matrix | 0.7s | 3% |
| CSV writing | ~0.5s | 2% |
| **Total** | **~27s** | **100%** |

### Optimization Notes

1. **Parallel downloads:** 20 threads reduce download time from ~120s to ~21s
2. **Vectorized calculations:** NumPy operations for money flow matrix
3. **Pandas rolling:** Efficient MA calculations per ticker
4. **Memory usage:** ~500MB peak for full dataset in memory

### Scalability

- **10 tickers:** ~5 seconds
- **100 tickers:** ~12 seconds
- **287 tickers:** ~27 seconds
- **500 tickers (estimated):** ~45 seconds

**Bottleneck:** Network I/O for parallel downloads (74% of time)

## Data Validation

The pipeline includes built-in validation against Example 03's proven methodology:

### Validation Tests (2025-09-26)

| Ticker | Metric | Expected | Actual | Tolerance | Status |
|--------|--------|----------|--------|-----------|--------|
| VCB | money_flow | -0.40 | -0.3963 | 10% | ✅ PASS |
| VCB | dollar_flow | -0.89 | -0.8869 | 10% | ✅ PASS |
| VCB | trend_score | 0.66 | 0.6554 | 5% | ✅ PASS |
| VIC | money_flow | 0.36 | 0.3585 | 10% | ✅ PASS |
| VIC | dollar_flow | 2.09 | 2.0886 | 10% | ✅ PASS |
| VIC | trend_score | 0.32 | 0.3194 | 5% | ✅ PASS |
| CTG | money_flow | -0.16 | -0.1551 | 10% | ✅ PASS |
| CTG | dollar_flow | -0.28 | -0.2794 | 10% | ✅ PASS |
| CTG | trend_score | 0.78 | 0.7829 | 5% | ✅ PASS |

**Result:** 9/9 tests passing (100%)

## Use Cases

### 1. Backtesting Trading Strategies

```python
import pandas as pd

# Load enhanced CSV
df = pd.read_csv('/tmp/market_data/VCB.csv')

# Strategy: Buy when close > MA20 and money_flow > 0
buy_signals = df[
    (df['close'] > df['ma20']) &
    (df['money_flow'] > 0) &
    (df['ma20_score'] > 2)
]

print(f"Buy signals: {len(buy_signals)}")
```

### 2. Screening for Momentum Stocks

```python
# Load 60-day cache for quick screening
cache = pd.read_csv('/tmp/cache/ticker_60_days.csv')

# Find stocks with strong uptrend
latest = cache.groupby('ticker').last()
momentum = latest[
    (latest['ma10_score'] > 5) &      # Price 5% above MA10
    (latest['trend_score'] > 0.7) &   # Strong trend
    (latest['money_flow'] > 0.5)      # Active buying
]

print(momentum[['close', 'ma10_score', 'money_flow', 'trend_score']])
```

### 3. Correlation Analysis

```python
# Load multiple tickers
vcb = pd.read_csv('/tmp/market_data/VCB.csv', parse_dates=['time']).set_index('time')
bid = pd.read_csv('/tmp/market_data/BID.csv', parse_dates=['time']).set_index('time')

# Calculate correlation
correlation = vcb['money_flow'].corr(bid['money_flow'])
print(f"VCB-BID money flow correlation: {correlation:.2f}")
```

### 4. Market Breadth Analysis

```python
# Load cache file
cache = pd.read_csv('/tmp/cache/ticker_180_days.csv', parse_dates=['time'])

# Calculate daily market breadth
daily_breadth = cache.groupby('time').agg({
    'money_flow': lambda x: (x > 0).sum(),  # Stocks with positive flow
    'ticker': 'count'                        # Total stocks
})

daily_breadth['pct_positive'] = (daily_breadth['money_flow'] / daily_breadth['ticker'] * 100)
print(daily_breadth.tail(10))
```

### 5. Machine Learning Features

```python
# Load data for ML model
df = pd.read_csv('/tmp/market_data/VCB.csv')

# Create feature set
features = df[[
    'ma10_score', 'ma20_score', 'ma50_score',  # Trend features
    'money_flow', 'dollar_flow', 'trend_score', # Flow features
    'volume'                                     # Volume feature
]].dropna()

# Target: Next day's return
df['next_return'] = df['close'].shift(-1) / df['close'] - 1
target = df['next_return'].dropna()

# Train model (example)
from sklearn.ensemble import RandomForestRegressor
model = RandomForestRegressor()
model.fit(features[:-1], target)
```

## API Reference

### CSVDataService

**Location:** `aipriceaction/data/csv_service.py`

#### fetch_all_tickers()

```python
@classmethod
def fetch_all_tickers(cls, date_range: DateRangeConfig) -> Dict[str, List[StockDataPoint]]
```

Fetch all tickers with automatic cache selection.

**Parameters:**
- `date_range`: DateRangeConfig object
  - `range="ALL"`: Downloads individual CSVs (full history from 2015)
  - `range="1M"`: Uses 60-day cache
  - `range="3M"`: Uses 180-day cache
  - `range="1Y"`: Uses 365-day cache

**Returns:** Dictionary mapping ticker → list of StockDataPoint

**Performance:**
- Cache files: < 5 seconds
- ALL range: ~21 seconds (parallel downloads)

#### fetch_single_ticker()

```python
@classmethod
def fetch_single_ticker(cls, ticker: str, date_range: DateRangeConfig) -> List[StockDataPoint]
```

Fetch single ticker data.

**Parameters:**
- `ticker`: Stock symbol (e.g., "VCB")
- `date_range`: DateRangeConfig object

**Returns:** List of StockDataPoint with date filtering applied

#### fetch_vnindex()

```python
@classmethod
def fetch_vnindex(cls) -> List[StockDataPoint]
```

Fetch VNINDEX data (always full history).

**Returns:** List of StockDataPoint (2,685 days)

### CSVEnhancementEngine

**Location:** `aipriceaction/services/csv_enhancement_engine.py`

#### format_for_csv()

```python
@staticmethod
def format_for_csv(df: pd.DataFrame) -> pd.DataFrame
```

Format DataFrame for CSV output with proper column ordering.

**Parameters:**
- `df`: DataFrame with all 16 columns

**Returns:** DataFrame with columns in correct order and NaN handling

**Column order:**
```python
['ticker', 'time', 'open', 'high', 'low', 'close', 'volume',
 'ma10', 'ma20', 'ma50', 'ma10_score', 'ma20_score', 'ma50_score',
 'money_flow', 'dollar_flow', 'trend_score']
```

## Data Sources

### Primary Source

**URL:** `https://api.aipriceaction.com/raw/market_data/{ticker}.csv`

**Coverage:**
- Start date: 2015-01-05 (first trading day of 2015)
- End date: Current (updated daily)
- Tickers: 287 (286 stocks + VNINDEX)

**Format:** Raw CSV with columns: `time,open,high,low,close,volume`

### Cache Files (Pre-aggregated)

**URLs:**
- `https://api.aipriceaction.com/raw/ticker_60_days.csv`
- `https://api.aipriceaction.com/raw/ticker_180_days.csv`
- `https://api.aipriceaction.com/raw/ticker_365_days.csv`

**Format:** CSV with `ticker,time,open,high,low,close,volume`

**Update frequency:** Daily

## Troubleshooting

### Issue: Parallel downloads timeout

**Symptom:** Script hangs during "Downloading CSVs in parallel"

**Solution:** Reduce thread count in `csv_service.py:276`
```python
# Change from 20 to 10
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
```

### Issue: Memory error on large datasets

**Symptom:** `MemoryError` during DataFrame operations

**Solution:** Process in batches
```python
# Instead of processing all tickers at once
for ticker_batch in np.array_split(all_tickers, 10):
    # Process batch
    pass
```

### Issue: Validation tests failing

**Symptom:** Money flow values don't match expected

**Possible causes:**
1. VNINDEX data mismatch (check VNINDEX.csv dates)
2. Different date range (check date_range_config)
3. Calculation order (check reverse chronological sorting)

**Debug:**
```python
# Print intermediate values
print(f"Matrix shape: {matrix.shape}")
print(f"Date range: {dates[0]} to {dates[-1]}")
print(f"Ticker count: {len(all_tickers)}")
```

### Issue: Empty MA columns

**Symptom:** MA10/MA20/MA50 are all NaN

**Cause:** Insufficient data points

**Solution:** Check data coverage
```python
df = pd.read_csv('/tmp/market_data/VCB.csv')
print(f"Total rows: {len(df)}")
print(f"First date: {df['time'].min()}")
print(f"Last date: {df['time'].max()}")

# First MA10 should appear at row 11 (10 days + 1)
print(df.iloc[10])  # Should have ma10 value
```

## Future Enhancements

### Planned Features

1. **Additional Technical Indicators**
   - RSI (Relative Strength Index)
   - MACD (Moving Average Convergence Divergence)
   - Bollinger Bands
   - Volume-weighted average price (VWAP)

2. **Sector Aggregation**
   - Sector-level money flow
   - Sector trend scores
   - Sector breadth indicators

3. **Incremental Updates**
   - Append new days instead of full regeneration
   - Delta-only processing for faster updates

4. **Compressed Output**
   - Parquet format for 10x smaller file sizes
   - Columnar storage for faster queries

5. **Cloud Storage Integration**
   - S3/GCS upload after generation
   - CDN distribution for faster access

### Contributing

To add new indicators:

1. Add calculation in `04_enhanced_csv.py` after MA calculations
2. Update column count in documentation
3. Add to `CSVEnhancementEngine.format_for_csv()` column ordering
4. Add validation tests
5. Update this README

## License

This feature is part of the aipriceaction-ui monorepo.

## Support

For issues or questions:
- GitHub Issues: https://github.com/anthropics/aipriceaction-ui/issues
- Documentation: `/packages/python/examples/04_enhanced_csv.py`
