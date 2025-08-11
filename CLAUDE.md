# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIPriceAction is a Vietnamese stock market data analysis tool that downloads financial data and creates comprehensive markdown reports. It integrates VPA (Volume Price Analysis) methodology for technical analysis of Vietnamese stock tickers.

## Core Architecture

### Main Script: main.py
- **Data Pipeline**: Downloads stock data using vnstock API, caches locally as CSV
- **Report Generation**: Creates markdown reports with VPA analysis integration
- **Group Management**: Organizes stocks by sectors using ticker_group.json

### Key Components
- **Stock Data Handler**: `download_stock_data()` with smart caching mechanism
- **Report Builder**: `generate_master_report()` with TOC and deep links
- **VPA Parser**: `parse_vpa_analysis()` and `get_latest_vpa_signal()` for technical analysis

### Data Structure
- `market_data/`: CSV files for daily stock data (format: `TICKER.csv`)
- `ticker_group.json`: Stock categorization by Vietnamese sectors (used as ticker source)
- `ticker_group_full.json`: More comprehensive ticker data (TODO: integrate)

## Commands

### Run Analysis (uses all tickers from ticker_group.json)
```bash
python main.py --start-date 2017-01-03 --end-date 2025-01-10
```

### Default start date: 2017-01-03
The system defaults to starting from 2017-01-03 for comprehensive historical data

### Default Behavior (if ticker_group.json missing)
Falls back to analyzing: VNINDEX, TCB, FPT

## Dependencies

Core libraries used:
- `vnstock`: Vietnamese stock data API
- `pandas`: Data manipulation

## Data Flow

1. Load all tickers from ticker_group.json (flattened from all sectors)
2. Parse existing VPA analysis from VPA.md
3. Download/cache stock data with smart caching (saves as TICKER.csv)
4. Create master report (REPORT.md) with:
   - VPA signal summary table
   - Sector-based groupings
   - Individual ticker analysis
   - Deep-linked navigation

## VPA Analysis Integration

The system expects VPA.md with entries formatted as:
```
# TICKER_NAME
- **Ngày YYYY-MM-DD:** [Analysis text with signals like "Sign of Strength", "Effort to Rise", etc.]
```

Recognized VPA signals (in order of importance):
- Test for Supply, No Demand, No Supply
- Effort to Rise, Effort to Fall  
- Stopping Volume, Buying Climax, Selling Climax
- Shakeout, Sign of Weakness, Sign of Strength