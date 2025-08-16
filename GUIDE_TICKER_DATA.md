# AIPriceAction Ticker Data Download Guide

## Overview

The `main_get_ticker_data.py` script provides comprehensive Vietnamese stock market data downloading with support for multiple time intervals and intelligent data management strategies.

## Features

- **Multi-interval support**: 1D (daily), 1H (hourly), 1m (minute)
- **Intelligent chunked downloading** for large datasets
- **Smart resume functionality** with dividend detection
- **Organized directory structure** for efficient data management
- **Rate limiting and retry strategies** for reliable API access
- **Backward compatibility** with existing workflows

## Quick Start

### Basic Usage

```bash
# Download daily data (default behavior)
python main_get_ticker_data.py

# Download hourly data
python main_get_ticker_data.py --interval 1H

# Download minute data
python main_get_ticker_data.py --interval 1m
```

### Common Commands

```bash
# Resume mode - update recent data only
python main_get_ticker_data.py --resume-days 7

# Full download from specific date
python main_get_ticker_data.py --start-date 2020-01-01 --full-download

# Hourly data for last 30 days
python main_get_ticker_data.py --interval 1H --resume-days 30

# Minute data from specific date range
python main_get_ticker_data.py --interval 1m --start-date 2024-08-01 --end-date 2024-08-31
```

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--start-date` | `2015-01-05` | Start date in YYYY-MM-DD format |
| `--end-date` | Today | End date in YYYY-MM-DD format |
| `--interval` | `1D` | Data interval: 1D, 1H, 1m |
| `--resume-days` | `5` | Days to fetch in resume mode |
| `--full-download` | `false` | Force full download from start-date |
| `--batch-size` | `10` | Tickers per batch (2 for full downloads) |

## Interval Types

### Daily Data (1D)
- **Directory**: `market_data/`
- **File format**: `TICKER.csv`
- **Behavior**: Standard daily OHLCV data
- **Best for**: Long-term analysis, portfolio tracking

### Hourly Data (1H)
- **Directory**: `market_data_hour/`
- **Chunked storage**: `market_data_hour/YYYY/TICKER.csv`
- **Consolidated**: `market_data_hour/TICKER.csv`
- **Best for**: Intraday analysis, short-term trading

### Minute Data (1m)
- **Directory**: `market_data_minutes/`
- **Chunked storage**: `market_data_minutes/YYYY/MM/TICKER.csv`
- **Consolidated**: `market_data_minutes/TICKER.csv`
- **Best for**: High-frequency trading, detailed technical analysis

## Directory Structure

```
aipriceaction-data/
├── market_data/              # Daily data
│   ├── VNINDEX.csv
│   ├── FPT.csv
│   └── ...
├── market_data_hour/         # Hourly data
│   ├── 2023/                 # Yearly chunks
│   │   ├── VNINDEX.csv
│   │   └── FPT.csv
│   ├── 2024/
│   ├── 2025/
│   ├── VNINDEX.csv          # Consolidated file
│   └── FPT.csv
└── market_data_minutes/      # Minute data
    ├── 2024/                 # Yearly organization
    │   ├── 01/               # Monthly chunks
    │   │   ├── VNINDEX.csv
    │   │   └── FPT.csv
    │   ├── 02/
    │   └── ...
    ├── 2025/
    │   ├── 08/
    │   └── ...
    ├── VNINDEX.csv          # Consolidated file
    └── FPT.csv
```

## Download Strategies

### Daily Data (1D)
- **Short ranges**: Batch processing for efficiency
- **Long ranges (>2 years)**: Individual ticker processing
- **Resume mode**: Updates last few days only

### Hourly Data (1H)
- **Chunking**: Year-by-year downloads
- **Storage**: Each year saved separately, then consolidated
- **Resume mode**: Updates current year only
- **Rate limiting**: 2 seconds between chunks

### Minute Data (1m)
- **Chunking**: Month-by-month downloads
- **Storage**: Each month saved separately, then consolidated
- **Resume mode**: Updates current month only
- **Rate limiting**: 3 seconds between chunks

## Resume vs Full Download

### Resume Mode (Default)
- Downloads only recent data (last N days)
- Preserves existing historical data
- Fast execution for regular updates
- Automatic dividend detection

### Full Download Mode
- Downloads complete history from start-date
- Overwrites existing data
- Slower but ensures complete dataset
- Use for initial setup or data recovery

## Dividend Detection

The system automatically detects dividend adjustments by:

1. **Comparing recent API data** with existing file data
2. **Price ratio analysis** for overlapping dates
3. **Automatic full re-download** when dividend detected
4. **Works across all intervals** (1D, 1H, 1m)

When dividend detected:
- Full historical data is re-downloaded
- All chunks are rebuilt with adjusted prices
- Ensures data consistency across time periods

## Data Sources

### Primary: VCI (Vietnam Capital Investment)
- Fast batch processing capability
- Comprehensive data coverage
- Rate limit: 30 calls/minute

### Fallback: TCBS (Techcom Securities)
- Individual ticker requests
- Reliable data source
- Used when VCI fails

## Performance Optimization

### Batch Processing
- Groups multiple tickers in single API call
- 3-5x faster than individual requests
- Used for daily data and resume mode

### Intelligent Fallback
1. **VCI Batch** → fastest method
2. **VCI Individual** → reliable backup
3. **TCBS Individual** → final fallback

### Rate Limiting
- **Daily**: 1 second between requests
- **Hourly**: 2 seconds between chunks
- **Minute**: 3 seconds between chunks
- Configurable retry with exponential backoff

## Use Cases

### Daily Portfolio Updates
```bash
# Update daily data for all tickers
python main_get_ticker_data.py --resume-days 5
```

### Intraday Analysis Setup
```bash
# Download hourly data for current year
python main_get_ticker_data.py --interval 1H --start-date 2025-01-01 --full-download
```

### High-Frequency Trading Data
```bash
# Get minute data for last month
python main_get_ticker_data.py --interval 1m --resume-days 30
```

### Historical Research
```bash
# Download complete 10-year daily dataset
python main_get_ticker_data.py --start-date 2015-01-01 --full-download
```

## Data Format

All CSV files contain the following columns:

| Column | Description |
|--------|-------------|
| `ticker` | Stock symbol (e.g., "FPT", "VNINDEX") |
| `time` | Timestamp (YYYY-MM-DD HH:MM:SS) |
| `open` | Opening price |
| `high` | Highest price |
| `low` | Lowest price |
| `close` | Closing price |
| `volume` | Trading volume |

### Price Scaling
- **Individual stocks**: Automatically scaled down by 1000x
- **Market indices**: No scaling applied
- **Consistent across intervals**: Same scaling rules apply

## Troubleshooting

### Common Issues

**No data for recent dates**
- Market may be closed
- Try different date range
- Check if ticker is actively traded

**High memory usage with minute data**
- Use chunked storage (automatic)
- Process smaller date ranges
- Monitor system resources

**API rate limiting**
- Automatic retry with backoff
- Increase delays between requests
- Use resume mode for regular updates

### Error Recovery

**Failed downloads**
- Automatically retries with TCBS
- Logs detailed error information
- Preserves partial data

**Network interruptions**
- Resume from last successful ticker
- Chunked downloads minimize data loss
- Full error reporting for debugging

## Configuration

### Ticker Sources
- **Primary**: `ticker_group.json` - organized by sectors
- **Fallback**: Default list (VNINDEX, TCB, FPT)
- **Automatic**: VNINDEX always included

### Rate Limiting
- **VCI**: 30 calls/minute
- **TCBS**: 30 calls/minute
- **Configurable**: Adjust in client initialization

## Best Practices

### For Regular Updates
1. Use **resume mode** with appropriate `--resume-days`
2. Run **daily** for 1D data, **hourly** for 1H data
3. Monitor for **dividend announcements**
4. Keep **reasonable batch sizes** (default: 10)

### For Initial Setup
1. Use **full download mode** for complete history
2. Start with **daily data** for broad coverage
3. Add **hourly/minute data** as needed
4. Allow **sufficient time** for large downloads

### For High-Frequency Data
1. Use **smaller date ranges** for minute data
2. Monitor **disk space** for large datasets
3. Consider **data retention policies**
4. Use **resume mode** for efficiency

### Performance Optimization
1. Use **batch processing** when possible
2. Avoid **overlapping downloads**
3. Monitor **API rate limits**
4. Schedule **downloads during off-hours**

## Advanced Usage

### Custom Date Ranges
```bash
# Specific month of hourly data
python main_get_ticker_data.py --interval 1H --start-date 2024-08-01 --end-date 2024-08-31

# Quarter of minute data
python main_get_ticker_data.py --interval 1m --start-date 2024-07-01 --end-date 2024-09-30
```

### Targeted Updates
```bash
# Last trading week
python main_get_ticker_data.py --resume-days 7

# Current month
python main_get_ticker_data.py --interval 1H --resume-days 30
```

### Data Validation
```bash
# Force dividend re-check
python main_get_ticker_data.py --full-download

# Rebuild complete dataset
python main_get_ticker_data.py --start-date 2015-01-01 --full-download
```

## Integration with Analysis Pipeline

The downloaded data integrates seamlessly with:

- **VPA Analysis**: Technical analysis with volume-price methodology
- **Report Generation**: Automated markdown reports
- **Portfolio Tracking**: Performance monitoring
- **Risk Management**: Historical volatility analysis

## Monitoring and Maintenance

### Regular Tasks
- **Weekly**: Review download logs for errors
- **Monthly**: Check disk space usage
- **Quarterly**: Validate data completeness
- **Annually**: Archive old chunked data

### Performance Metrics
- **Success rate**: Percentage of successful downloads
- **Execution time**: Monitor for performance degradation
- **Data quality**: Check for missing dates or anomalies
- **API usage**: Track rate limit compliance

## Support and Updates

### Logging
- Detailed progress reporting
- Error tracking with context
- Performance statistics
- Dividend detection alerts

### Maintenance
- Regular client updates
- API endpoint monitoring
- Data validation checks
- Performance optimization

For technical support or feature requests, refer to the project documentation or submit an issue to the repository.