#!/usr/bin/env python3
"""
Standalone MSN Stock Data Client

This client provides access to MSN Finance API for international stocks,
currencies, cryptocurrencies, and global indices.

Based on vnstock/explorer/msn/quote.py analysis.
"""

import requests
import json
import time
import random
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import pandas as pd


class MSNClient:
    """
    Standalone MSN client for fetching international financial data.
    
    This implementation provides direct access to MSN Finance API without dependencies.
    Core functionality: historical price data for stocks, currencies, crypto, indices.
    """
    
    def __init__(self, random_agent: bool = True, rate_limit_per_minute: int = 10):
        self.base_url = "https://assets.msn.com/service/Finance"
        self.random_agent = random_agent
        
        # Rate limiting
        self.rate_limit_per_minute = rate_limit_per_minute
        self.request_timestamps = []
        
        # Create persistent session
        self.session = requests.Session()
        
        # Browser profiles for user agent rotation
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15"
        ]
        
        # Supported intervals
        self.interval_map = {
            '1D': '1D',
            '1W': '1W', 
            '1M': '1M'
        }
        
        # Currency pairs mapping (sample from vnstock)
        self.currency_ids = {
            'USDVND': 'avyufr',
            'JPYVND': 'ave8sm',
            'AUDVND': 'auxrkr',
            'CNYVND': 'av55fr',
            'EURUSD': 'av932w',
            'GBPUSD': 'avyjhw',
            'USDJPY': 'avyomw'
        }
        
        # Cryptocurrency mapping
        self.crypto_ids = {
            'BTC': 'c2111',
            'ETH': 'c2112',
            'USDT': 'c2115',
            'USDC': 'c211a',
            'BNB': 'c2113',
            'XRP': 'c2117',
            'ADA': 'c2114',
            'SOL': 'c2116',
            'DOGE': 'c2119'
        }
        
        # Global indices mapping
        self.index_ids = {
            'SPX': 'a33k6h',  # S&P 500
            'DJI': 'a6qja2',  # Dow Jones
            'IXIC': 'a3oxnm', # Nasdaq
            'FTSE': 'aopnp2', # FTSE 100
            'DAX': 'afx2kr',  # DAX
            'N225': 'a9j7bh', # Nikkei 225
            'HSI': 'ah7etc',  # Hang Seng
            'VNI': 'aqk2nm'   # VN Index
        }
        
        # Initialize session and get API key
        self._setup_session()
        self.api_key = self._get_api_key(version='20240430', show_log=False)
        
    def _setup_session(self):
        """Initialize session with browser-like configuration."""
        user_agent = random.choice(self.user_agents) if self.random_agent else self.user_agents[0]
        
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'DNT': '1',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': user_agent,
            'Referer': 'https://www.msn.com/',
            'Origin': 'https://www.msn.com'
        })
    
    def _get_api_key(self, version='20240430', show_log=False) -> str:
        """Extract API key from MSN API using vnstock method."""
        scope = """{
            "audienceMode":"adult",
            "browser":{"browserType":"chrome","version":"0","ismobile":"false"},
            "deviceFormFactor":"desktop","domain":"www.msn.com",
            "locale":{"content":{"language":"vi","market":"vn"},"display":{"language":"vi","market":"vn"}},
            "ocid":"hpmsn","os":"macos","platform":"web",
            "pageType":"financestockdetails"
        }"""
        
        if version is None:
            from datetime import datetime, timedelta
            today = (datetime.now()-timedelta(hours=7)).strftime("%Y%m%d")
            version = today
        
        url = f"https://assets.msn.com/resolver/api/resolve/v3/config/?expType=AppConfig&expInstance=default&apptype=finance&v={version}.130&targetScope={scope}"
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                if show_log:
                    print(f"Failed to get API key: HTTP {response.status_code}")
                # Fallback API key
                return "okvJq6RrRQJaGKmj6M21Hq1CnJjCq49Ss1pdfxl0pJ9L3b0lmWIJp/lcdJaL7t8l7e9nOoC8O6KjE2h7cP9JWs"
            
            if not response.text.strip():
                if show_log:
                    print("Empty response from MSN API")
                return "okvJq6RrRQJaGKmj6M21Hq1CnJjCq49Ss1pdfxl0pJ9L3b0lmWIJp/lcdJaL7t8l7e9nOoC8O6KjE2h7cP9JWs"
            
            data = response.json()
            
            # Extract API key from the complex nested structure
            try:
                apikey = data['configs']["shared/msn-ns/HoroscopeAnswerCardWC/default"]["properties"]["horoscopeAnswerServiceClientSettings"]["apikey"]
                if show_log:
                    print(f"Successfully extracted API key: {apikey[:20]}...")
                return apikey
            except KeyError as e:
                if show_log:
                    print(f"API key structure not found: {e}")
                    print(f"Available keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                # Fallback API key
                return "okvJq6RrRQJaGKmj6M21Hq1CnJjCq49Ss1pdfxl0pJ9L3b0lmWIJp/lcdJaL7t8l7e9nOoC8O6KjE2h7cP9JWs"
                
        except Exception as e:
            if show_log:
                print(f"Error extracting API key: {e}")
            # Fallback API key
            return "okvJq6RrRQJaGKmj6M21Hq1CnJjCq49Ss1pdfxl0pJ9L3b0lmWIJp/lcdJaL7t8l7e9nOoC8O6KjE2h7cP9JWs"
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting by tracking request timestamps."""
        current_time = time.time()
        
        # Remove timestamps older than 1 minute
        self.request_timestamps = [ts for ts in self.request_timestamps if current_time - ts < 60]
        
        # If we're at the rate limit, wait until we can make another request
        if len(self.request_timestamps) >= self.rate_limit_per_minute:
            oldest_request = min(self.request_timestamps)
            wait_time = 60 - (current_time - oldest_request)
            if wait_time > 0:
                print(f"Rate limit reached ({self.rate_limit_per_minute}/min). Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time + 0.1)
        
        # Record this request timestamp
        self.request_timestamps.append(current_time)
    
    def _exponential_backoff(self, attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
        """Calculate exponential backoff delay."""
        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
        return min(delay, max_delay)
    
    def _make_request(self, url: str, params: Dict = None, max_retries: int = 5) -> Optional[Dict]:
        """Make HTTP request with retry logic."""
        self._enforce_rate_limit()
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = self._exponential_backoff(attempt - 1)
                    print(f"Retry {attempt}/{max_retries-1} after {delay:.1f}s delay...")
                    time.sleep(delay)
                    
                if attempt > 0 and self.random_agent:
                    self.session.headers['User-Agent'] = random.choice(self.user_agents)
                
                response = self.session.get(url=url, params=params, timeout=30)
                
                if response.status_code == 200:
                    try:
                        return response.json()
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {e}")
                        continue
                elif response.status_code == 403:
                    print(f"Access denied (403) on attempt {attempt + 1}")
                    continue
                elif response.status_code == 429:
                    print(f"Rate limited (429) on attempt {attempt + 1}")
                    continue
                elif response.status_code >= 500:
                    print(f"Server error ({response.status_code}) on attempt {attempt + 1}")
                    continue
                else:
                    print(f"HTTP Error {response.status_code} on attempt {attempt + 1}")
                    if response.status_code < 500:
                        break
                    continue
                    
            except requests.exceptions.RequestException as e:
                print(f"Request exception on attempt {attempt + 1}: {e}")
                continue
                    
        return None
    
    def _detect_asset_type(self, symbol_id: str) -> str:
        """Detect asset type based on symbol ID."""
        if symbol_id in self.crypto_ids.values():
            return "crypto"
        elif symbol_id in self.currency_ids.values():
            return "currency"
        elif symbol_id in self.index_ids.values():
            return "index"
        else:
            return "stock"
    
    def _resolve_symbol(self, symbol: str) -> str:
        """Resolve symbol to MSN symbol ID."""
        symbol_upper = symbol.upper()
        
        # Check if it's already a symbol ID (lowercase with numbers)
        if symbol.islower() and any(c.isdigit() for c in symbol):
            return symbol
            
        # Check currency pairs
        if symbol_upper in self.currency_ids:
            return self.currency_ids[symbol_upper]
            
        # Check cryptocurrencies  
        if symbol_upper in self.crypto_ids:
            return self.crypto_ids[symbol_upper]
            
        # Check indices
        if symbol_upper in self.index_ids:
            return self.index_ids[symbol_upper]
            
        # For stocks, return as-is (user needs to provide correct MSN ID)
        return symbol.lower()
    
    def get_history(self, 
                   symbol: str, 
                   start: str, 
                   end: Optional[str] = None, 
                   interval: str = "1D",
                   count_back: int = 365) -> Optional[pd.DataFrame]:
        """
        Fetch historical data from MSN Finance API.
        
        Args:
            symbol: Symbol or MSN symbol ID (e.g., "USDVND", "BTC", "SPX", or "a33k6h")
            start: Start date in "YYYY-MM-DD" format
            end: End date in "YYYY-MM-DD" format (optional)
            interval: Time interval - 1D, 1W, 1M only
            count_back: Maximum number of data points to return
            
        Returns:
            DataFrame with columns: time, open, high, low, close, volume (if applicable)
        """
        if interval not in self.interval_map:
            raise ValueError(f"Invalid interval: {interval}. Valid options: {list(self.interval_map.keys())}")
        
        # Resolve symbol to MSN ID
        symbol_id = self._resolve_symbol(symbol)
        asset_type = self._detect_asset_type(symbol_id)
        
        # Calculate date range
        if not end:
            end = datetime.now().strftime("%Y-%m-%d")
            
        # Determine endpoint based on asset type
        if asset_type == "crypto":
            url = f"{self.base_url}/Cryptocurrency/chart"
        else:
            url = f"{self.base_url}/Charts/TimeRange"
        
        # Prepare parameters (match vnstock exactly)
        params = {
            "apikey": self.api_key,
            'StartTime': f'{start}T17:00:00.000Z',
            'EndTime': f'{end}T16:59:00.858Z',
            'timeframe': 1,
            "ocid": "finance-utils-peregrine",
            "cm": "vi-vn",  # Changed to match vnstock
            "it": "web",
            "scn": "ANON",
            "ids": symbol_id,
            "type": "All",
            "wrapodata": "false",
            "disableSymbol": "false"
        }
        
        print(f"Fetching {symbol} ({symbol_id}) data: {start} to {end} [{interval}]")
        
        # Make the request
        response_data = self._make_request(url, params)
        
        if not response_data:
            print("No response from API")
            return None
            
        try:
            # Extract series data
            if isinstance(response_data, list) and len(response_data) > 0:
                series_data = response_data[0].get('series', [])
            else:
                print("Unexpected response format")
                return None
                
            if not series_data:
                print("No series data in response")
                return None
                
            # Convert to DataFrame
            df = pd.DataFrame(series_data)
            
            # Drop unnecessary columns
            columns_to_drop = ['priceHigh', 'priceLow', 'startTime', 'endTime']
            df = df.drop(columns=[col for col in columns_to_drop if col in df.columns])
            
            # Rename columns to standard format
            column_mapping = {
                'timeStamps': 'time',
                'openPrices': 'open',
                'pricesHigh': 'high',
                'pricesLow': 'low',
                'prices': 'close',
                'volumes': 'volume'
            }
            df = df.rename(columns=column_mapping)
            
            # Parse time column
            df["time"] = pd.to_datetime(df["time"], errors='coerce')
            
            # Add 7 hours to convert from UTC to Asia/Ho_Chi_Minh
            df['time'] = df['time'] + pd.Timedelta(hours=7)
            # Remove hours info from time  
            df['time'] = df['time'].dt.floor('D')
            
            # Round price columns to 2 decimal places
            price_cols = ["open", "high", "low", "close"]
            for col in price_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').round(2)
            
            # Handle volume column
            if 'volume' in df.columns:
                df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype('int64')
            
            # Set proper data types
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'])
                
            # Remove volume column for currencies
            if asset_type == "currency" and 'volume' in df.columns:
                df = df.drop(columns=['volume'])
            
            # Replace invalid values with NaN and drop invalid rows
            df = df.replace(-99999901.0, None)
            df = df.dropna(subset=['open', 'high', 'low'])
            
            # Filter by date range - ensure timezone compatibility
            start_dt = pd.to_datetime(start).tz_localize(None)
            end_dt = pd.to_datetime(end).tz_localize(None)
            
            # Convert df time to timezone-naive if it has timezone
            if df['time'].dt.tz is not None:
                df['time'] = df['time'].dt.tz_localize(None)
                
            df = df[(df['time'] >= start_dt) & (df['time'] <= end_dt)]
            
            # Apply count_back limit
            if count_back and len(df) > count_back:
                df = df.tail(count_back)
            
            # Define column order
            if asset_type == "currency":
                column_order = ['time', 'open', 'high', 'low', 'close']
            else:
                column_order = ['time', 'open', 'high', 'low', 'close', 'volume']
                
            # Reorder columns
            available_columns = [col for col in column_order if col in df.columns]
            df = df[available_columns]
            
            # Sort by time and reset index
            df = df.sort_values('time').reset_index(drop=True)
            
            print(f"Successfully fetched {len(df)} data points")
            return df
            
        except Exception as e:
            print(f"Error processing response data: {e}")
            return None


def main():
    """Test the MSN client with various asset types."""
    client = MSNClient(random_agent=True, rate_limit_per_minute=6)
    
    # Test different asset types
    test_cases = [
        ("SPX", "S&P 500 Index"),
        ("USDVND", "USD/VND Currency"),
        ("BTC", "Bitcoin"),
        ("EURUSD", "EUR/USD Currency")
    ]
    
    for symbol, description in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing {symbol} ({description})")
        print(f"Date range: 2025-08-01 to 2025-08-13")
        print("="*60)
        
        start_time = time.time()
        
        try:
            df = client.get_history(
                symbol=symbol,
                start="2025-08-01",
                end="2025-08-13",
                interval="1D"
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if df is not None:
                print(f"\n✅ Success! Retrieved {len(df)} data points in {duration:.1f}s")
                print(f"Data range: {df['time'].min()} to {df['time'].max()}")
                
                # Show first few rows
                print(f"\nFirst 3 rows:")
                print(df.head(3).to_string(index=False))
                
                # Basic statistics
                print(f"\nBasic Statistics:")
                if 'open' in df.columns:
                    print(f"Open: {df['open'].min():.2f} - {df['open'].max():.2f}")
                if 'high' in df.columns:
                    print(f"High: {df['high'].min():.2f} - {df['high'].max():.2f}")
                if 'low' in df.columns:
                    print(f"Low: {df['low'].min():.2f} - {df['low'].max():.2f}")
                if 'close' in df.columns:
                    print(f"Close: {df['close'].min():.2f} - {df['close'].max():.2f}")
                if 'volume' in df.columns:
                    print(f"Volume: {df['volume'].min():,} - {df['volume'].max():,}")
                    
            else:
                print(f"\n❌ Failed to retrieve data for {symbol}")
                
        except Exception as e:
            print(f"\n💥 Exception occurred for {symbol}: {e}")
            
        # Add delay between requests
        if symbol != test_cases[-1][0]:
            print(f"\nWaiting 3 seconds before next test...")
            time.sleep(3)


if __name__ == "__main__":
    main()