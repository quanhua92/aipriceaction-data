# VCI & TCBS Stock Market Clients

Comprehensive guide to the Vietnamese stock market data clients for VCI Securities and TCBS (Techcom Securities).

## Overview

This repository contains standalone clients for accessing Vietnamese stock market data from two major brokers:

- **VCI Securities** - Vietnam's leading securities company
- **TCBS (Techcom Securities)** - Major Vietnamese brokerage firm

Each client is implemented in both **Python** and **JavaScript**, providing cross-platform compatibility and consistent APIs for financial data retrieval.

## Client Files

| Client | Python | JavaScript | Guide |
|--------|--------|------------|-------|
| VCI Securities | `vci.py` | `vci.js` | `vci.md` |
| TCBS (Techcom) | `tcbs.py` | `tcbs.js` | `tcbs.md` |

## Standardized Testing

All 4 implementations feature identical main() functions that run a comprehensive 4-step testing sequence:

### Test Sequence

1. **🏢 Company Information**
   - Company overview and profile
   - Market capitalization calculation
   - Major shareholders and key officers
   - Exchange and industry classification

2. **💹 Financial Information**
   - Balance sheet, income statement, cash flow
   - Financial ratios (PE, PB, ROE, ROA, D/E)
   - Quarterly and yearly reporting periods
   - Key financial metrics normalization

3. **📈 Historical Data (Single Symbol)**
   - OHLCV price data with customizable date ranges
   - Multiple timeframes (1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M)
   - Volume analysis and price change calculations
   - Sophisticated retry mechanisms with rate limiting

4. **📊 Batch Historical Data**
   - **NEW**: Fetch multiple symbols in parallel/batch requests
   - Efficient handling of 10+ ticker symbols simultaneously
   - Individual error handling per symbol
   - Real-time progress tracking and success rates

## Quick Start

### Python Usage

```bash
# Test VCI client
python3 vci.py

# Test TCBS client  
python3 tcbs.py
```

### JavaScript Usage

```bash
# Test VCI client
node vci.js

# Test TCBS client
node tcbs.js
```

Each test runs automatically with the symbol "VCI" and displays comprehensive results including:
- Company metrics and market data
- Financial ratios and performance indicators
- Recent price history with analytics

## Core Features

### 🚀 Performance & Reliability
- **Rate Limiting**: Configurable requests per minute (default: 6-10/min)
- **Retry Logic**: Exponential backoff with up to 5 retry attempts
- **Anti-Bot Measures**: User agent rotation and realistic request patterns
- **Error Handling**: Graceful degradation and detailed error reporting

### 📊 Data Coverage
- **Real-time Prices**: Current trading prices and market status
- **Historical Data**: Multi-timeframe OHLCV data with volume
- **Company Fundamentals**: Comprehensive company information
- **Financial Statements**: Balance sheet, income, cash flow data
- **Market Indices**: VN-Index, HNX-Index, UPCOM support

### 🔄 Cross-Platform Consistency
- **Unified APIs**: Identical method signatures across Python/JavaScript
- **Data Normalization**: Standardized field mapping between providers
- **Format Compatibility**: Consistent data structures and naming

## API Methods

### Company Data

```python
# Get comprehensive company information
company_data = client.company_info("VCI")

# Individual components
overview = client.overview("VCI")           # Company overview
profile = client.profile("VCI")             # Detailed profile  
shareholders = client.shareholders("VCI")   # Major shareholders
officers = client.officers("VCI")           # Key management
```

### Financial Data

```python
# Get comprehensive financial information
financial_data = client.financial_info("VCI", period="quarter")

# Individual statements (TCBS only)
balance_sheet = client.balance_sheet("VCI", period="quarter")
income_statement = client.income_statement("VCI", period="quarter") 
cash_flow = client.cash_flow("VCI", period="quarter")
ratios = client.ratios("VCI", period="quarter")
```

### Historical Data

```python
# Get historical price data
history = client.get_history(
    symbol="VCI",
    start="2025-08-01", 
    end="2025-08-13",
    interval="1D",
    count_back=365
)
```

## Configuration Options

### Rate Limiting
```python
# Python
client = VCIClient(random_agent=True, rate_limit_per_minute=6)
client = TCBSClient(random_agent=True, rate_limit_per_minute=10)
```

```javascript
// JavaScript  
const client = new VCIClient(true, 6);  // randomAgent, rateLimitPerMinute
const client = new TCBSClient(true, 10);
```

### Time Intervals
- **Intraday**: 1m, 5m, 15m, 30m, 1H
- **Daily+**: 1D, 1W, 1M

### Supported Symbols
- **Stocks**: VCI, FPT, VNM, TCB, etc.
- **Indices**: VNINDEX, HNXINDEX, UPCOMINDEX
- **Futures**: VN30F contracts (TCBS only)

## Sample Output

```
============================================================
VCI CLIENT - COMPREHENSIVE TESTING
============================================================

🏢 Step 1: Company Information for VCI
----------------------------------------
✅ Success! Company data retrieved
📊 Exchange: HOSE
🏭 Industry: Financial Services
💰 Market Cap: 33,962.2B VND
📈 Outstanding Shares: 723M
👥 Shareholders: 9 major
👔 Officers: 10 management

💹 Step 2: Financial Information for VCI
----------------------------------------
✅ Success! Financial data retrieved  
📊 Ratios: PE: 26.2 | PB: 1.8 | ROE: 9.0% | ROA: 4.2% | D/E: 1.0

📈 Step 3: Historical Data for VCI
----------------------------------------
✅ Success! Retrieved 9 data points
📅 Range: 2025-08-01 to 2025-08-13
💹 Latest: 47,000 VND (Vol: 19,406,611)
📊 Change: +8.80% | Range: 42,000-48,100

============================================================
✅ VCI CLIENT TESTING COMPLETED
============================================================
```

## Data Structure Examples

### Company Information
```json
{
  "symbol": "VCI",
  "exchange": "HOSE", 
  "industry": "Financial Services",
  "market_cap": 33962200000000,
  "current_price": 47000,
  "outstanding_shares": 722600000,
  "shareholders": [...],
  "officers": [...]
}
```

### Historical Data
```json
[
  {
    "time": "2025-08-01T00:00:00.000Z",
    "open": 43200,
    "high": 44000, 
    "low": 42000,
    "close": 43500,
    "volume": 15230000
  }
]
```

### Financial Ratios
```json
{
  "pe": 26.2,
  "pb": 1.8,
  "roe": 0.09,
  "roa": 0.042,
  "debt_to_equity": 1.0,
  "current_ratio": 2.1
}
```

## Error Handling

Both clients implement robust error handling:

```python
try:
    data = client.get_history("VCI", "2025-08-01", "2025-08-13")
    if data:
        print(f"Retrieved {len(data)} data points")
    else:
        print("No data available")
except Exception as e:
    print(f"Error: {e}")
```

Common error scenarios:
- **Rate Limiting**: Automatic backoff and retry
- **Invalid Symbols**: Clear error messages
- **Network Issues**: Connection retry with exponential backoff
- **API Changes**: Graceful degradation

## Best Practices

### Performance Optimization
1. **Use appropriate rate limits** to avoid being blocked
2. **Cache results** when possible to reduce API calls
3. **Batch requests** efficiently with proper delays
4. **Monitor response times** and adjust intervals accordingly

### Data Quality
1. **Validate data ranges** before processing
2. **Handle missing values** gracefully
3. **Cross-reference** data between providers when available
4. **Implement data consistency checks**

### Production Usage
1. **Add comprehensive logging** for monitoring
2. **Implement health checks** for API availability
3. **Set up alerting** for critical failures
4. **Use environment variables** for configuration

## Dependencies

### Python
- `requests` - HTTP client
- `json` - JSON processing (built-in)
- `time` - Rate limiting (built-in)
- `datetime` - Date handling (built-in)

### JavaScript (Node.js)
- `fetch` - HTTP client (built-in Node.js 18+)
- No external dependencies required

### Browser Compatibility
Both JavaScript clients work in modern browsers with fetch API support.

## Contributing

When modifying the clients:

1. **Maintain API consistency** between Python and JavaScript versions
2. **Follow existing error handling patterns**
3. **Update tests** to verify functionality
4. **Document any breaking changes**
5. **Test with multiple symbols** and date ranges

## License

These clients are provided for educational and research purposes. Please respect the terms of service of VCI Securities and TCBS when using their APIs.

## Support

For issues or questions:
1. Check the individual client guides (`vci.md`, `tcbs.md`)
2. Review the source code for implementation details
3. Test with the provided main() functions
4. Ensure your network allows HTTPS requests to broker APIs

---

*Last updated: August 2025*