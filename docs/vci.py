#!/usr/bin/env python3
"""
Standalone VCI Stock Data Client

This client bypasses the vnai dependency by implementing sophisticated anti-bot measures
directly using the requests library. Based on reverse-engineering of the vnstock library
and VCI API research.
"""

import requests
import json
import time
import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import pandas as pd


class VCIClient:
    """
    Standalone VCI client for fetching Vietnamese stock market data.
    
    This implementation uses sophisticated anti-bot measures including:
    - Browser-like headers with proper referer/origin
    - Session persistence with cookies
    - User agent rotation
    - Request timing and retry strategies
    """
    
    def __init__(self, random_agent: bool = True, rate_limit_per_minute: int = 10):
        self.base_url = "https://trading.vietcap.com.vn/api/"
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
            '1m': 'ONE_MINUTE',
            '5m': 'ONE_MINUTE', 
            '15m': 'ONE_MINUTE',
            '30m': 'ONE_MINUTE',
            '1H': 'ONE_HOUR',
            '1D': 'ONE_DAY',
            '1W': 'ONE_DAY',
            '1M': 'ONE_DAY'
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
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'DNT': '1',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'User-Agent': user_agent,
            'Referer': 'https://trading.vietcap.com.vn/',
            'Origin': 'https://trading.vietcap.com.vn'
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
        
    def _make_request(self, url: str, payload: Dict, max_retries: int = 5) -> Optional[Dict]:
        """
        Make HTTP request with sophisticated retry and anti-bot measures.
        
        Args:
            url: API endpoint URL
            payload: Request payload
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
                
                response = self.session.post(
                    url=url,
                    json=payload,
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
        
    def _calculate_timestamp(self, date_str: Optional[str] = None) -> int:
        """Calculate Unix timestamp for the given date or current date."""
        if date_str:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            dt = datetime.now()
        
        # Add one day to get the 'to' timestamp (exclusive end)
        dt = dt + timedelta(days=1)
        return int(dt.timestamp())
        
    def _calculate_count_back(self, start_date: str, end_date: Optional[str], interval: str) -> int:
        """Calculate the number of data points to request based on date range."""
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_dt = datetime.now()
            
        # Calculate business days
        business_days = pd.bdate_range(start=start_dt, end=end_dt)
        
        interval_mapped = self.interval_map.get(interval, "ONE_DAY")
        
        if interval_mapped == "ONE_DAY":
            return len(business_days) + 10  # Add buffer
        elif interval_mapped == "ONE_HOUR":
            return int(len(business_days) * 6.5) + 10
        elif interval_mapped == "ONE_MINUTE":
            return int(len(business_days) * 6.5 * 60) + 10
        else:
            return 1000  # Default fallback
            
    def get_history(self, 
                   symbol: str, 
                   start: str, 
                   end: Optional[str] = None, 
                   interval: str = "1D") -> Optional[pd.DataFrame]:
        """
        Fetch historical stock data from VCI API.
        
        Args:
            symbol: Stock symbol (e.g., "VCI", "VN30F2312")
            start: Start date in "YYYY-MM-DD" format
            end: End date in "YYYY-MM-DD" format (optional)
            interval: Time interval - 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M
            
        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        if interval not in self.interval_map:
            raise ValueError(f"Invalid interval: {interval}. Valid options: {list(self.interval_map.keys())}")
            
        # Prepare request parameters
        end_timestamp = self._calculate_timestamp(end)
        count_back = self._calculate_count_back(start, end, interval)
        interval_value = self.interval_map[interval]
        
        url = f"{self.base_url}chart/OHLCChart/gap-chart"
        payload = {
            "timeFrame": interval_value,
            "symbols": [symbol],
            "to": end_timestamp,
            "countBack": count_back
        }
        
        print(f"Fetching {symbol} data: {start} to {end or 'now'} [{interval}] (count_back={count_back})")
        
        # Make the request
        response_data = self._make_request(url, payload)
        
        if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
            print("No data received from API")
            return None
            
        # Extract data from response
        data_item = response_data[0]
        
        # Check if we have the required OHLCV arrays
        required_keys = ['o', 'h', 'l', 'c', 'v', 't']
        if not all(key in data_item for key in required_keys):
            print(f"Missing required keys in response. Available: {list(data_item.keys())}")
            return None
            
        # Get the arrays
        opens = data_item['o']
        highs = data_item['h'] 
        lows = data_item['l']
        closes = data_item['c']
        volumes = data_item['v']
        times = data_item['t']
        
        # Check if all arrays have the same length
        lengths = [len(arr) for arr in [opens, highs, lows, closes, volumes, times]]
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
    """Test the VCI client with VNINDEX data across different intervals."""
    client = VCIClient(random_agent=True, rate_limit_per_minute=6)  # Conservative rate limit
    
    # Test intervals
    intervals = ["1D", "1H", "1m"]
    
    for interval in intervals:
        print(f"\n{'='*60}")
        print(f"Testing VNINDEX with {interval} interval...")
        print(f"Date range: 2025-08-01 to 2025-08-13")
        print("="*60)
        
        start_time = time.time()
        
        try:
            df = client.get_history(
                symbol="VNINDEX",
                start="2025-08-01",
                end="2025-08-13", 
                interval=interval
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if df is not None:
                print(f"\n✅ Success! Retrieved {len(df)} data points in {duration:.1f}s")
                print(f"Data range: {df['time'].min()} to {df['time'].max()}")
                
                # Show first few and last few rows
                if len(df) > 10:
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
                print(f"\n❌ Failed to retrieve {interval} data")
                
        except Exception as e:
            print(f"\n💥 Exception occurred for {interval}: {e}")
            
        # Add delay between different interval requests
        if interval != intervals[-1]:
            print(f"\nWaiting 3 seconds before next interval test...")
            time.sleep(3)


if __name__ == "__main__":
    main()