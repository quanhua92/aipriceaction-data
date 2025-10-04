# Enhanced CSV Architecture

## Overview

The enhanced CSV system generates 16-column CSV files with complete technical analysis:
- 7 original columns (ticker, time, OHLCV)
- 9 calculated columns (MA, MA scores, money flow metrics)

**Status:** ✅ Production-ready, 100% validated against Example 03

## Modules

### 1. `CSVDataLoader` (csv_data_loader.py)

Handles loading data from different sources:

**Cached Multi-Ticker Files:**
- `ticker_60_days.csv` - Last 60 days, ALL tickers (287 tickers)
- `ticker_180_days.csv` - Last 180 days, ALL tickers
- `ticker_365_days.csv` - Last 365 days, ALL tickers

**Individual Ticker Files:**
- `market_data/{TICKER}.csv` - Full historical data per ticker

**Smart Source Selection:**
```python
# Automatically chooses best source
market_df, source = CSVDataLoader.load_market_data(days_back=60)
# Returns: (DataFrame, "60d"|"180d"|"365d"|"individual")
```

### 2. `CSVEnhancementEngine` (csv_enhancement_engine.py)

Calculates technical indicators:

**Always Calculated:**
- MA10, MA20, MA50 (moving averages)
- MA10_score, MA20_score, MA50_score (% from MA)

**Requires Full Market Context:**
- money_flow (signed % with VNINDEX weighting)
- dollar_flow (signed % with VNINDEX weighting)
- trend_score (10-day rolling average of abs(money_flow))

**Usage:**
```python
enhanced_df = CSVEnhancementEngine.enhance_dataframe(
    df=market_df,
    vnindex_df=vnindex_df,  # For volume weighting
    all_tickers_df=market_df  # Full market context
)
```

## Data Source Strategy

### Use Cached Files When:
- Need ≤60 days: Use `60d` cache ✅
- Need ≤180 days: Use `180d` cache ✅
- Need ≤365 days: Use `365d` cache ✅
- Have ALL tickers in cache ✅

**Advantages:**
- Single HTTP request
- 287 tickers loaded at once
- Perfect for money flow (needs all tickers)

### Use Individual Files When:
- Need >365 days of history
- Need specific subset of tickers
- Cache files not available

**Disadvantages:**
- Multiple HTTP requests (1 per ticker)
- Slower for many tickers
- Must wait for ALL files to download before money flow calculation

## Money Flow Calculation Requirements

### Critical: Full Market Context

Money flow calculations require **ALL tickers** for accurate percentages:

```python
# Each ticker's money flow = (ticker_flow / total_market_flow) * 100
```

**Why:**
- VCB's -0.40% means VCB represents 0.40% of total market outflow
- Calculation needs sum of all 287 tickers' flows
- Missing tickers = wrong percentages

### Date Range Considerations

**Example 03 (Reference):**
- Uses ALL historical data (2685 rows)
- Filters to specific date range
- Has enough data for trend score (10-day window)

**60-Day Cache:**
- Only has 65 days of data
- First day has no previous close (NaN price_change)
- Trend score needs 10 days of money_flow data

**Solution for Production:**
- Use appropriate cache based on needed date range
- For trend scores: ensure ≥10 days of money flow data
- For long-term analysis: use individual CSVs

## Enhanced CSV Format

```csv
ticker,time,open,high,low,close,volume,ma10,ma20,ma50,ma10_score,ma20_score,ma50_score,money_flow,dollar_flow,trend_score
VCB,2025-09-26,63.2,63.4,62.9,63.0,3981900,63.6,65.225,63.744,-0.94,-3.41,-1.17,-0.40,-0.89,0.66
```

## Validation Results

### Example 04 (Final - Production Ready)

| Component | Tests | Pass Rate | Notes |
|-----------|-------|-----------|-------|
| MA Values | 3/3 | 100% | ✅ Perfect match |
| MA Scores | 3/3 | 100% | ✅ Perfect match |
| Money Flow | 3/3 | 100% | ✅ Perfect match |
| Dollar Flow | 3/3 | 100% | ✅ Perfect match |
| Trend Score | 3/3 | 100% | ✅ Perfect match |
| **TOTAL** | **9/9** | **100%** | ✅ **ALL TESTS PASSED** |

**Validation Date:** 2025-09-26 (same as Examples 01, 02, 03)

**Cross-Check Results:**
```
Ticker | CSV Money Flow | Example 03 | Match
-------|---------------|------------|------
VCB    | -0.3963      | -0.40%     | ✅
VIC    | +0.3585      | +0.36%     | ✅
CTG    | -0.1551      | -0.16%     | ✅
BID    | -0.3807      | -0.38%     | ✅
TCB    | +0.1726      | +0.17%     | ✅
VIX    | -3.4033      | -3.40%     | ✅
```

## Production Usage

### Generate Enhanced CSVs (Example 04 approach):
```python
# Run Example 04 to generate 287 enhanced CSV files
# This uses Example 03's proven methodology
uv run python examples/04_enhanced_csv.py

# Output: /tmp/market_data/{TICKER}.csv (287 files, 16 columns each)
# Validation: 9/9 tests passing (100%)
```

### Use BulkCSVProcessor for custom processing:
```python
from aipriceaction.services.bulk_csv_processor import BulkCSVProcessor

processor = BulkCSVProcessor(output_dir="/path/to/market_data")

# Download all original CSVs and enhance them
all_tickers = ["VCB", "VIC", "CTG", ...]  # All 287 tickers
processor.process_all(all_tickers)

# Creates:
# - /path/to/market_data/{TICKER}.csv (enhanced individual CSVs)
# - /path/to/cache/ticker_60_days.csv (aggregated cache, looked up from individual CSVs)
# - /path/to/cache/ticker_180_days.csv
# - /path/to/cache/ticker_365_days.csv
```

### Cache File Generation Flow:
```python
# New lookup-based approach:
# 1. Download original cache file from server (structure + dates)
# 2. For each row (ticker + date), look up enhanced values from market_data/{TICKER}.csv
# 3. Write combined enhanced cache file

# This ensures:
# - Server's cache defines structure/dates (source of truth)
# - market_data/ CSVs provide enhanced values (source of truth)
# - Cache files are views into market_data, not separate calculations
```

## Parser Compatibility

Both TypeScript and Python parsers safely ignore extra columns:

**TypeScript:**
```typescript
const [ticker, time, open, high, low, close, volume] = row.split(",");
// Columns 8-16 ignored
```

**Python:**
```python
df = pd.read_csv(file)
# Accesses only: ticker, time, open, high, low, close, volume
# Other columns present but unused
```

## Key Implementation Details

### Ticker-First Matrix Ordering
Money flow calculations use ticker-first ordering for the flattened matrix:
```python
# Correct ordering (matches Example 03):
flat_idx = ticker_idx * num_dates + date_idx

# This was the critical fix for Example 04 validation
# Wrong ordering would produce incorrect money flow values
```

### Full Market Context Requirement
Money flow percentages require ALL tickers for accurate calculation:
```python
# Each ticker's percentage = (ticker_flow / total_market_flow) × 100
# Missing tickers = wrong percentages
# Example 04 uses ALL 287 tickers like Example 03
```

### Generated Files Summary
Running Example 04 produces:
- **287 individual CSVs** in /tmp/market_data/
- **16 columns** per file (7 OHLCV + 9 calculated)
- **~63 rows** per file (62 days + header for 3M range)
- **100% validation** against Example 03 money flow values
