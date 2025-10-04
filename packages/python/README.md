# AI Price Action - Python Package

High-performance vectorized stock market analysis using NumPy/Pandas, matching the TypeScript implementation.

## Status

✅ **Example 01 (Basic Data)** - COMPLETE (40/40 tests passed)
- CSV data loading from API
- Vectorized moving average calculations (MA10, MA20, MA50)
- VNINDEX OHLCV validation
- Output format matches TypeScript exactly

✅ **Example 02 (Multi Data)** - COMPLETE (44/44 tests passed)
- Multi-ticker data fetching (VIC, VCB, CTG, VIX)
- MA score calculations
- VNINDEX benchmark data
- Date 2025-09-26 validation

✅ **Example 03 (Money Flow)** - COMPLETE (24/24 tests passed)
- Advanced money flow calculations with VNINDEX volume weighting
- Trend score analysis (10-day rolling average)
- Date order fix (reverse chronological)
- Validation tickers (BID, CTG, TCB, VCB, VIC, VIX)

✅ **Example 04 (Enhanced CSV)** - COMPLETE (9/9 tests passed)
- Bulk CSV enhancement with 16-column format (7 OHLCV + 9 calculated)
- Full market context money flow (287 tickers)
- Generates enhanced individual CSVs to market_data/
- 100% validation against Example 03 values

🎉 **All 117 tests passing (100%)** - Fully synchronized with TypeScript implementation!

## Setup

```bash
# Create virtual environment with uv
uv venv

# Install dependencies
uv pip install -r requirements.txt
```

## Running Examples

```bash
# Run all examples with validation
uv run python examples/01_basic_data.py  # VNINDEX OHLCV + MA (40 tests)
uv run python examples/02_multi_data.py  # Multi-ticker + MA Scores (44 tests)
uv run python examples/03_money_flow.py  # Money Flow + Trend Scores (24 tests)
uv run python examples/04_enhanced_csv.py  # Enhanced CSV Generation (9 tests)

# Each example validates against TypeScript output
# Example 04 generates 287 enhanced CSV files to /tmp/market_data/
```

## Structure

```
packages/python/
├── aipriceaction/
│   ├── services/
│   │   ├── csv_data_service.py         # Data loading with intelligent caching
│   │   ├── csv_enhancement_engine.py   # Technical indicator calculations
│   │   ├── csv_data_loader.py          # Smart cache/individual file selection
│   │   └── bulk_csv_processor.py       # Bulk enhancement pipeline
│   ├── core/
│   │   ├── matrix_utils.py             # Vectorized MA & Money Flow calculations
│   │   └── ma_score.py                 # MA score percentage calculations
│   └── utils/
│       ├── formatters.py               # Number formatting (K, M, %)
│       └── validators.py               # Validation with tolerance
├── examples/
│   ├── 01_basic_data.py                # ✅ VNINDEX OHLCV + MA (40 tests)
│   ├── 02_multi_data.py                # ✅ Multi-ticker + MA Scores (44 tests)
│   ├── 03_money_flow.py                # ✅ Money Flow + Trend Scores (24 tests)
│   ├── 04_enhanced_csv.py              # ✅ Enhanced CSV Generation (9 tests)
│   ├── 01_expected_output.txt          # Reference output for Example 01
│   ├── 02_expected_output.txt          # Reference output for Example 02
│   └── 03_expected_output.txt          # Reference output for Example 03
├── README.md                            # This file
├── README_ENHANCED_CSV.md               # Enhanced CSV architecture docs
└── requirements.txt
```

## Key Features

### Intelligent Data Caching
- 60-day cache for recent market data
- 180-day cache for medium-term analysis
- Individual CSV files for all-time data
- Automatic cache selection based on date ranges

### Vectorized Performance
All calculations use NumPy vectorization:
- Single date: ~30ms for 286 tickers
- Bulk calculation: ~25ms for 59 dates × 286 tickers
- Average per calculation: ~0.0003ms

### TypeScript Compatibility
Exact match with TypeScript implementation:
- Same algorithms for MA, MA Score, Money Flow, Trend Score
- Same validation test cases
- 100% test pass rate (108/108 tests)
- Cross-platform verified

## Critical: Date Order for Trend Scores

**Trend score calculations require reverse chronological order (newest first):**
- Dates must be sorted: `sorted(dates, reverse=True)`
- Window looks forward in array (backward in time)
- 10-day rolling average of absolute money flow percentages

This was a critical bug fix - TypeScript Example 03 initially had wrong trend scores due to incorrect date ordering.
