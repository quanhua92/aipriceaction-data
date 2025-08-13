#!/usr/bin/env python3
"""
Standalone TCBS Stock Data Client

This client bypasses the vnai dependency by implementing direct API calls
to TCBS (Techcom Securities) using reverse-engineering insights from vnstock library.

Based on vnstock/explorer/tcbs/quote.py analysis.
"""

import requests
import json
import time
import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import pandas as pd


class TCBSClient:
    """
    Standalone TCBS client for fetching Vietnamese stock market data.
    
    This implementation provides direct access to TCBS API without dependencies.
    Core functionality: historical price data (OHLCV) with sophisticated request handling.
    """
    
    def __init__(self, random_agent: bool = True, rate_limit_per_minute: int = 10):
        self.base_url = "https://apipubaws.tcbs.com.vn"
        self.random_agent = random_agent
        
        # Rate limiting
        self.rate_limit_per_minute = rate_limit_per_minute
        self.request_timestamps = []  # Track request timestamps for rate limiting
        
        # Create persistent session for cookie management
        self.session = requests.Session()
        
        # Browser profiles for user agent rotation
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        ]
        
        # Interval mapping from vnstock
        self.interval_map = {
            '1m': '1',
            '5m': '5',
            '15m': '15',
            '30m': '30',
            '1H': '60',
            '1D': 'D',
            '1W': 'W',
            '1M': 'M'
        }
        
        # Index mapping for Vietnamese market indices
        self.index_mapping = {
            'VNINDEX': 'VNINDEX',
            'HNXINDEX': 'HNXIndex', 
            'UPCOMINDEX': 'UPCOM'
        }
        
        # Initialize session with realistic browser behavior
        self._setup_session()
        
    def _setup_session(self):
        """Initialize session with browser-like configuration."""
        # Set up default headers that mimic browser behavior
        user_agent = random.choice(self.user_agents) if self.random_agent else self.user_agents[0]
        
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'DNT': '1',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'User-Agent': user_agent,
            'Referer': 'https://www.tcbs.com.vn/',
            'Origin': 'https://www.tcbs.com.vn'
        })
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for the request, optionally rotating user agent."""
        headers = self.session.headers.copy()
        
        if self.random_agent:
            headers['User-Agent'] = random.choice(self.user_agents)
            
        return headers
    
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
                time.sleep(wait_time + 0.1)  # Add small buffer
        
        # Record this request timestamp
        self.request_timestamps.append(current_time)
    
    def _exponential_backoff(self, attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
        """Calculate exponential backoff delay."""
        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
        return min(delay, max_delay)
        
    def _make_request(self, url: str, params: Dict = None, max_retries: int = 5) -> Optional[Dict]:
        """
        Make HTTP request with sophisticated retry and anti-bot measures.
        
        Args:
            url: API endpoint URL
            params: URL parameters
            max_retries: Maximum number of retry attempts
            
        Returns:
            JSON response data or None if failed
        """
        # Enforce rate limiting before making any request
        self._enforce_rate_limit()
        
        for attempt in range(max_retries):
            try:
                # Apply exponential backoff on retries
                if attempt > 0:
                    delay = self._exponential_backoff(attempt - 1)
                    print(f"Retry {attempt}/{max_retries-1} after {delay:.1f}s delay...")
                    time.sleep(delay)
                    
                # Rotate user agent on retry
                if attempt > 0 and self.random_agent:
                    self.session.headers['User-Agent'] = random.choice(self.user_agents)
                
                response = self.session.get(
                    url=url,
                    params=params,
                    timeout=30,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        return data
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {e}")
                        print(f"Response text: {response.text[:500]}")
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
                        # Client errors (4xx) - don't retry
                        break
                    continue
                    
            except requests.exceptions.Timeout as e:
                print(f"Timeout on attempt {attempt + 1}: {e}")
                continue
                
            except requests.exceptions.ConnectionError as e:
                print(f"Connection error on attempt {attempt + 1}: {e}")
                continue
                
            except requests.exceptions.RequestException as e:
                print(f"Request exception on attempt {attempt + 1}: {e}")
                continue
                    
        return None
        
    def get_history(self, 
                   symbol: str, 
                   start: str, 
                   end: Optional[str] = None, 
                   interval: str = "1D",
                   count_back: int = 365) -> Optional[pd.DataFrame]:
        """
        Fetch historical stock data from TCBS API.
        
        Args:
            symbol: Stock symbol (e.g., "VCI", "VNINDEX")
            start: Start date in "YYYY-MM-DD" format
            end: End date in "YYYY-MM-DD" format (optional)
            interval: Time interval - 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M
            count_back: Number of data points to return
            
        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        if interval not in self.interval_map:
            raise ValueError(f"Invalid interval: {interval}. Valid options: {list(self.interval_map.keys())}")
            
        # Handle index symbols
        if symbol in self.index_mapping:
            symbol = self.index_mapping[symbol]
            
        # Calculate timestamps
        start_time = datetime.strptime(start, "%Y-%m-%d")
        if end:
            end_time = datetime.strptime(end, "%Y-%m-%d")
        else:
            end_time = datetime.now()
            
        # Validate date range
        if end_time < start_time:
            raise ValueError("End date cannot be earlier than start date.")
            
        end_stamp = int(end_time.timestamp())
        interval_value = self.interval_map[interval]
        
        # Determine asset type and endpoint
        if symbol in ['VN30F2312', 'VN30F2403', 'VN30F2406', 'VN30F2409']:  # Futures
            asset_type = "derivative"
            base_path = "futures-insight"
        else:
            asset_type = "stock"
            base_path = "stock-insight"
        
        # Determine endpoint based on interval
        if interval in ["1D", "1W", "1M"]:
            endpoint = "bars-long-term"
        else:
            endpoint = "bars"
            
        # Construct URL
        url = f"{self.base_url}/{base_path}/v2/stock/{endpoint}"
        
        params = {
            'resolution': interval_value,
            'ticker': symbol,
            'type': asset_type,
            'to': end_stamp,
            'countBack': count_back
        }
        
        print(f"Fetching {symbol} data: {start} to {end or 'now'} [{interval}] (count_back={count_back})")
        
        # Make the request
        response_data = self._make_request(url, params)
        
        if not response_data or 'data' not in response_data:
            print("No data received from API")
            return None
            
        # Extract data from response
        data = response_data['data']
        
        # TCBS returns data in a different format than VCI
        # Check if data is a list (TCBS format) or dict (VCI format)
        if isinstance(data, list):
            # TCBS format: list of objects with tradingDate, open, high, low, close, volume
            if not data:
                print("Empty data array in response")
                return None
                
            # Convert TCBS format to arrays
            times = []
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []
            
            for item in data:
                if 'tradingDate' in item:
                    # Handle different date formats from TCBS
                    trading_date = item['tradingDate']
                    try:
                        # Try with just date first
                        if 'T' in trading_date:
                            # Remove timezone info if present
                            date_part = trading_date.split('T')[0]
                            date_obj = datetime.strptime(date_part, '%Y-%m-%d')
                        else:
                            date_obj = datetime.strptime(trading_date, '%Y-%m-%d')
                    except ValueError as e:
                        print(f"Date parsing error for {trading_date}: {e}")
                        continue
                        
                    times.append(int(date_obj.timestamp()))
                    opens.append(item.get('open', 0))
                    highs.append(item.get('high', 0))
                    lows.append(item.get('low', 0))
                    closes.append(item.get('close', 0))
                    volumes.append(item.get('volume', 0))
                else:
                    print(f"Unexpected item format: {item}")
                    
        else:
            # VCI-style format with parallel arrays
            required_keys = ['t', 'o', 'h', 'l', 'c', 'v']
            if not all(key in data for key in required_keys):
                print(f"Missing required keys in response. Available: {list(data.keys())}")
                return None
                
            # Get the arrays
            times = data['t']
            opens = data['o']
            highs = data['h'] 
            lows = data['l']
            closes = data['c']
            volumes = data['v']
        
        # Check if all arrays have the same length
        lengths = [len(arr) for arr in [times, opens, highs, lows, closes, volumes]]
        if not all(length == lengths[0] for length in lengths):
            print(f"Inconsistent array lengths: {lengths}")
            return None
            
        if lengths[0] == 0:
            print("Empty data arrays in response")
            return None
            
        # Convert to DataFrame
        df_data = []
        for i in range(len(times)):
            df_data.append({
                'time': pd.to_datetime(int(times[i]), unit='s'),
                'open': float(opens[i]),
                'high': float(highs[i]),
                'low': float(lows[i]),
                'close': float(closes[i]),
                'volume': int(volumes[i]) if volumes[i] is not None else 0
            })
            
        df = pd.DataFrame(df_data)
        
        # Filter by start date
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        df = df[df['time'] >= start_dt].reset_index(drop=True)
        
        # Sort by time
        df = df.sort_values('time').reset_index(drop=True)
        
        print(f"Successfully fetched {len(df)} data points")
        return df


def main():
    """Test the TCBS client with Vietnamese stock data."""
    client = TCBSClient(random_agent=True, rate_limit_per_minute=6)  # Conservative rate limit
    
    # Test symbols - use proper TCBS symbol names
    symbols = ["VCI", "FPT", "VCB"]  # Skip VNINDEX for now, test with actual stocks
    
    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"Testing {symbol} with 1D interval...")
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
                
                # Show first few and last few rows
                if len(df) > 6:
                    print(f"\nFirst 3 rows:")
                    print(df.head(3).to_string(index=False))
                    print(f"\nLast 3 rows:")
                    print(df.tail(3).to_string(index=False))
                else:
                    print(f"\nAll data:")
                    print(df.to_string(index=False))
                
                # Basic statistics
                print(f"\nBasic Statistics:")
                print(f"Open: {df['open'].min():.2f} - {df['open'].max():.2f}")
                print(f"High: {df['high'].min():.2f} - {df['high'].max():.2f}")
                print(f"Low: {df['low'].min():.2f} - {df['low'].max():.2f}")
                print(f"Close: {df['close'].min():.2f} - {df['close'].max():.2f}")
                print(f"Volume: {df['volume'].min():,} - {df['volume'].max():,}")
                
            else:
                print(f"\n❌ Failed to retrieve data for {symbol}")
                
        except Exception as e:
            print(f"\n💥 Exception occurred for {symbol}: {e}")
            
        # Add delay between different symbol requests
        if symbol != symbols[-1]:
            print(f"\nWaiting 3 seconds before next symbol test...")
            time.sleep(3)


if __name__ == "__main__":
    main()