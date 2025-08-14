# Vietnam Stock Market Clients (Rust)

Rust implementation of VCI and TCBS stock market data clients using reqwest. These clients provide direct access to Vietnamese stock market data without external dependencies.

## Features

### VCI Client (`vci.rs`)
- **Historical Data**: OHLCV data with multiple timeframes (1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M)
- **Batch Requests**: Get data for multiple symbols in a single API call
- **Company Information**: Comprehensive company data including shareholders and officers
- **GraphQL API**: Uses VCI's GraphQL endpoint for detailed company information
- **Rate Limiting**: Built-in rate limiting (configurable, default 10 requests/minute)
- **Anti-bot Measures**: Browser-like headers, user agent rotation, exponential backoff

### TCBS Client (`tcbs.rs`)
- **Historical Data**: OHLCV data with support for stocks and derivatives
- **Company Data**: Overview, profile, shareholders, and key officers
- **Financial Statements**: Balance sheet, income statement, cash flow, and ratios
- **Sequential Batch**: Processes multiple symbols with rate limiting
- **Market Cap Calculation**: Automatic market cap calculation with current prices
- **REST API**: Direct REST API calls to TCBS endpoints

## Quick Start

### Prerequisites

Add to your `Cargo.toml`:

```toml
[dependencies]
reqwest = { version = "0.11", features = ["json", "gzip"] }
tokio = { version = "1.0", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
chrono = { version = "0.4", features = ["serde"] }
rand = "0.8"
regex = "1.5"
```

### Usage Examples

#### VCI Client

```rust
use vietnam_stock_clients::{VciClient, VciError};

#[tokio::main]
async fn main() -> Result<(), VciError> {
    let mut client = VciClient::new(true, 6)?; // random_agent=true, rate_limit=6/min
    
    // Get historical data
    let data = client.get_history("VCI", "2025-08-01", Some("2025-08-13"), "1D").await?;
    println!("Retrieved {} data points", data.len());
    
    // Get batch historical data
    let symbols = vec!["VCI".to_string(), "TCB".to_string(), "FPT".to_string()];
    let batch_data = client.get_batch_history(&symbols, "2025-08-14", Some("2025-08-14"), "1D").await?;
    
    // Get company information
    let company_info = client.company_info("VCI").await?;
    println!("Company: {} - Industry: {:?}", company_info.symbol, company_info.industry);
    
    Ok(())
}
```

#### TCBS Client

```rust
use vietnam_stock_clients::{TcbsClient, TcbsError};

#[tokio::main]
async fn main() -> Result<(), TcbsError> {
    let mut client = TcbsClient::new(true, 6)?; // random_agent=true, rate_limit=6/min
    
    // Get historical data
    let data = client.get_history("VCI", "2025-08-01", Some("2025-08-13"), "1D", 365).await?;
    println!("Retrieved {} data points", data.len());
    
    // Get company information
    let company_info = client.company_info("VCI").await?;
    if let Some(ref overview) = company_info.overview {
        println!("Exchange: {:?}, Industry: {:?}", overview.exchange, overview.industry);
    }
    
    // Get financial information
    let financial_info = client.financial_info("VCI", "quarter").await?;
    println!("Financial data available: BS={}, IS={}, CF={}, Ratios={}", 
             financial_info.balance_sheet.is_some(),
             financial_info.income_statement.is_some(), 
             financial_info.cash_flow.is_some(),
             financial_info.ratios.is_some());
    
    Ok(())
}
```

### Running Examples

```bash
# Run VCI example
cargo run --example vci_example

# Run TCBS example  
cargo run --example tcbs_example

# Run tests
cargo test
```

## API Comparison

| Feature | VCI Client | TCBS Client |
|---------|------------|-------------|
| Historical Data | ✅ True batch requests | ✅ Sequential requests |
| Company Info | ✅ GraphQL comprehensive | ✅ REST API detailed |
| Financial Statements | ❌ Not available | ✅ Full statements |
| Market Indices | ✅ VNINDEX, etc. | ✅ VNINDEX, HNXINDEX, etc. |
| Rate Limiting | ✅ Built-in | ✅ Built-in |
| Anti-bot Measures | ✅ Sophisticated | ✅ Standard |

## Data Structures

### OHLCV Data
```rust
pub struct OhlcvData {
    pub time: DateTime<Utc>,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: u64,
    pub symbol: Option<String>,
}
```

### Company Information
```rust
// VCI
pub struct CompanyInfo {
    pub symbol: String,
    pub exchange: Option<String>,
    pub industry: Option<String>,
    pub market_cap: Option<f64>,
    pub current_price: Option<f64>,
    pub outstanding_shares: Option<u64>,
    pub shareholders: Vec<ShareholderInfo>,
    pub officers: Vec<OfficerInfo>,
    // ... more fields
}

// TCBS  
pub struct CompanyInfo {
    pub symbol: String,
    pub overview: Option<CompanyOverview>,
    pub profile: Option<CompanyProfile>,
    pub shareholders: Vec<ShareholderInfo>,
    pub officers: Vec<OfficerInfo>,
    pub market_cap: Option<f64>,
    pub current_price: Option<f64>,
}
```

## Configuration

### Rate Limiting
Both clients support configurable rate limiting:
- Default: 10 requests per minute
- Automatic enforcement with delays
- Request timestamp tracking

### User Agent Rotation
- 5 different browser user agents
- Random selection when `random_agent=true`
- Helps avoid detection

### Retry Logic
- Exponential backoff with jitter
- Maximum 5 retry attempts
- Handles HTTP errors (403, 429, 5xx)
- Connection error resilience

## Error Handling

Both clients provide comprehensive error types:

```rust
// VCI Errors
pub enum VciError {
    Http(ReqwestError),
    Serialization(serde_json::Error),
    InvalidInterval(String),
    InvalidResponse(String),
    RateLimit,
    NoData,
}

// TCBS Errors  
pub enum TcbsError {
    Http(ReqwestError),
    Serialization(serde_json::Error),
    InvalidInterval(String),
    InvalidResponse(String),
    RateLimit,
    NoData,
}
```

## Supported Intervals

| Interval | VCI Mapping | TCBS Mapping |
|----------|-------------|--------------|
| 1m | ONE_MINUTE | 1 |
| 5m | ONE_MINUTE | 5 |
| 15m | ONE_MINUTE | 15 |
| 30m | ONE_MINUTE | 30 |
| 1H | ONE_HOUR | 60 |
| 1D | ONE_DAY | D |
| 1W | ONE_DAY | W |
| 1M | ONE_DAY | M |

## Market Indices

### VCI
- VNINDEX
- All standard indices

### TCBS  
- VNINDEX → VNINDEX
- HNXINDEX → HNXIndex
- UPCOMINDEX → UPCOM

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## Disclaimer

These clients are for educational and research purposes. Please respect the APIs' terms of service and implement appropriate rate limiting in production use.