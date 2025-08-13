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
    
    # Normalized field mapping for cross-platform consistency
    FIELD_MAPPING = {
        # Company Overview
        'symbol': 'symbol',
        'exchange': 'exchange',
        'industry': 'industry',
        'company_type': 'company_type',
        'established_year': 'established_year',
        'employees': 'employees',
        'market_cap': 'market_cap',
        'current_price': 'current_price',
        'outstanding_shares': 'outstanding_shares',
        'company_profile': 'company_profile',
        'website': 'website',
        
        # TCBS-specific mappings
        'no_employees': 'employees',
        'outstanding_share': 'outstanding_shares',
        'short_name': 'company_name',
        'company_type': 'company_type',
        
        # Shareholders (TCBS format)
        'share_holder': 'shareholder_name',
        'share_own_percent': 'shareholder_percent',
        
        # Officers (TCBS format)
        'officer_name': 'officer_name',
        'officer_position': 'officer_position',
        'officer_own_percent': 'officer_percent',
        
        # Financial Statements (normalized keys)
        'total_assets': 'total_assets',
        'total_liabilities': 'total_liabilities',
        'shareholders_equity': 'shareholders_equity',
        'total_revenue': 'total_revenue',
        'gross_profit': 'gross_profit',
        'operating_profit': 'operating_profit',
        'net_income': 'net_income',
        'cash_from_operations': 'cash_from_operations',
        'cash_from_investing': 'cash_from_investing',
        'cash_from_financing': 'cash_from_financing',
        'free_cash_flow': 'free_cash_flow'
    }
    
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
    
    def overview(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get company overview data from TCBS API (same as vnstock approach).
        
        Args:
            symbol: Stock symbol (e.g., "VCI", "FPT")
            
        Returns:
            DataFrame with basic company information
        """
        # Use TCBS analysis API
        url = f"{self.base_url}/tcanalysis/v1/ticker/{symbol.upper()}/overview"
        
        print(f"Fetching company overview for {symbol}...")
        
        response_data = self._make_request(url)
        
        if not response_data:
            print("No company overview data received from API")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(response_data, index=[0])
        
        # Select relevant columns (same as vnstock)
        try:
            df = df[['ticker', 'exchange', 'industry', 'companyType',
                    'noShareholders', 'foreignPercent', 'outstandingShare', 'issueShare',
                    'establishedYear', 'noEmployees',  
                    'stockRating', 'deltaInWeek', 'deltaInMonth', 'deltaInYear', 
                    'shortName', 'website', 'industryID', 'industryIDv2']]
        except KeyError as e:
            print(f"Some overview columns missing: {e}")
            # Use available columns
            available_cols = [col for col in ['ticker', 'exchange', 'industry', 'companyType',
                             'noShareholders', 'foreignPercent', 'outstandingShare', 'issueShare',
                             'establishedYear', 'noEmployees', 'stockRating', 'deltaInWeek', 
                             'deltaInMonth', 'deltaInYear', 'shortName', 'website', 'industryID', 
                             'industryIDv2'] if col in df.columns]
            df = df[available_cols]
                    
        # Convert column names to snake_case (same as vnstock)
        df.columns = [self._camel_to_snake(col) for col in df.columns]
        
        # Rename specific columns
        df.rename(columns={
            'industry_i_dv2': 'industry_id_v2', 
            'ticker': 'symbol'
        }, inplace=True)
        
        print(f"Successfully fetched company overview for {symbol}")
        return df
    
    def profile(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get detailed company profile from TCBS API (same as vnstock approach).
        
        Args:
            symbol: Stock symbol (e.g., "VCI", "FPT")
            
        Returns:
            DataFrame with detailed company profile
        """
        url = f"{self.base_url}/tcanalysis/v1/company/{symbol.upper()}/overview"
        
        print(f"Fetching company profile for {symbol}...")
        
        response_data = self._make_request(url)
        
        if not response_data:
            print("No company profile data received from API")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame([response_data])
        
        # Clean HTML content in text fields (same as vnstock)
        try:
            from bs4 import BeautifulSoup
            for col in df.columns:
                try:
                    if df[col].dtype == 'object':
                        df[col] = df[col].apply(lambda x: BeautifulSoup(str(x), 'html.parser').get_text() if x else x)
                        df[col] = df[col].str.replace('\n', ' ')
                except:
                    pass
        except ImportError:
            # BeautifulSoup not available, skip HTML cleaning
            print("  Note: BeautifulSoup not available, skipping HTML cleaning")
            pass
                    
        # Add symbol column
        df['symbol'] = symbol.upper()
        
        # Drop unnecessary columns
        try:
            df.drop(columns=['id', 'ticker'], inplace=True, errors='ignore')
        except:
            pass
        
        # Convert column names to snake_case
        df.columns = [self._camel_to_snake(col) for col in df.columns]
        
        # Reorder columns to put symbol first
        cols = df.columns.tolist()
        if 'symbol' in cols:
            cols.remove('symbol')
            cols = ['symbol'] + cols
            df = df[cols]
        
        print(f"Successfully fetched company profile for {symbol}")
        return df
    
    def shareholders(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get major shareholders information from TCBS API (same as vnstock approach).
        
        Args:
            symbol: Stock symbol (e.g., "VCI", "FPT")
            
        Returns:
            DataFrame with major shareholders data
        """
        url = f"{self.base_url}/tcanalysis/v1/company/{symbol.upper()}/large-share-holders"
        
        print(f"Fetching shareholders for {symbol}...")
        
        response_data = self._make_request(url)
        
        if not response_data or 'listShareHolder' not in response_data:
            print("No shareholders data received from API")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(response_data['listShareHolder'])
        
        if df.empty:
            print("No shareholders data available")
            return None
        
        # Rename columns for clarity (same as vnstock)
        df.rename(columns={
            'name': 'shareHolder', 
            'ownPercent': 'shareOwnPercent'
        }, inplace=True)
        
        # Drop unnecessary columns
        df.drop(columns=['no', 'ticker'], inplace=True, errors='ignore')
        
        # Convert column names to snake_case
        df.columns = [self._camel_to_snake(col) for col in df.columns]
        
        print(f"Successfully fetched {len(df)} shareholders for {symbol}")
        return df
    
    def officers(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get key officers information from TCBS API (same as vnstock approach).
        
        Args:
            symbol: Stock symbol (e.g., "VCI", "FPT")
            
        Returns:
            DataFrame with key officers data
        """
        url = f"{self.base_url}/tcanalysis/v1/company/{symbol.upper()}/key-officers"
        
        print(f"Fetching officers for {symbol}...")
        
        response_data = self._make_request(url)
        
        if not response_data or 'listKeyOfficer' not in response_data:
            print("No officers data received from API")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(response_data['listKeyOfficer'])
        
        if df.empty:
            print("No officers data available")
            return None
        
        # Rename columns for clarity (same as vnstock)
        df.rename(columns={
            'name': 'officerName', 
            'position': 'officerPosition', 
            'ownPercent': 'officerOwnPercent'
        }, inplace=True)
        
        # Drop unnecessary columns
        df.drop(columns=['no', 'ticker'], inplace=True, errors='ignore')
        
        # Convert column names to snake_case
        df.columns = [self._camel_to_snake(col) for col in df.columns]
        
        # Sort by ownership percentage (same as vnstock)
        if 'officer_own_percent' in df.columns:
            df.sort_values(by='officer_own_percent', ascending=False, inplace=True)
        
        print(f"Successfully fetched {len(df)} officers for {symbol}")
        return df
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current trading price for market cap calculation.
        
        Args:
            symbol: Stock symbol (e.g., "VCI", "FPT")
            
        Returns:
            Current price or None if failed
        """
        url = f"{self.base_url}/stock-insight/v1/stock/second-tc-price"
        
        params = {"tickers": symbol.upper()}
        
        response_data = self._make_request(url, params)
        
        if not response_data or 'data' not in response_data:
            return None
            
        data = response_data['data']
        if not data or len(data) == 0:
            return None
            
        # Get current price (cp field)
        current_price = data[0].get('cp')
        return float(current_price) if current_price is not None else None

    def _apply_field_mapping(self, data: Dict, mapping_type: str = 'company') -> Dict:
        """Apply normalized field mapping to company data."""
        if not isinstance(data, dict):
            return data
            
        mapped_data = {}
        for key, value in data.items():
            # Use direct key mapping if available, otherwise keep original
            if key in self.FIELD_MAPPING:
                normalized_key = self.FIELD_MAPPING[key]
            else:
                normalized_key = key
            mapped_data[normalized_key] = value
            
        return mapped_data
    
    def _normalize_tcbs_data(self, company_data: Dict) -> Dict:
        """Normalize TCBS-specific data structure to standard format."""
        normalized = {
            'symbol': company_data.get('symbol'),
            'exchange': None,
            'industry': None,
            'company_type': None,
            'established_year': None,
            'employees': None,
            'market_cap': company_data.get('market_cap'),
            'current_price': company_data.get('current_price'),
            'outstanding_shares': None,
            'company_profile': None,
            'website': None
        }
        
        # Extract from overview
        if company_data.get('overview'):
            overview = company_data['overview']
            normalized.update({
                'exchange': overview.get('exchange'),
                'industry': overview.get('industry'),
                'company_type': overview.get('company_type'),
                'established_year': overview.get('established_year'),
                'employees': overview.get('no_employees'),
                'outstanding_shares': overview.get('outstanding_share'),
                'website': overview.get('website')
            })
            
        # Extract from profile
        if company_data.get('profile'):
            profile = company_data['profile']
            # Find a profile field that contains company description
            for key, value in profile.items():
                if isinstance(value, str) and len(str(value)) > 100:  # Assume longer text is profile
                    normalized['company_profile'] = value
                    break
            
        # Normalize shareholders
        if company_data.get('shareholders'):
            normalized_shareholders = []
            for shareholder in company_data['shareholders']:
                normalized_shareholders.append({
                    'shareholder_name': shareholder.get('share_holder'),
                    'shareholder_percent': shareholder.get('share_own_percent')
                })
            normalized['shareholders'] = normalized_shareholders
        
        # Normalize officers
        if company_data.get('officers'):
            normalized_officers = []
            for officer in company_data['officers']:
                normalized_officers.append({
                    'officer_name': officer.get('officer_name'),
                    'officer_position': officer.get('officer_position'),
                    'officer_percent': officer.get('officer_own_percent')
                })
            normalized['officers'] = normalized_officers
            
        return normalized

    def company_info(self, symbol: str, mapping: bool = True) -> Optional[Dict]:
        """
        Get comprehensive company information in a single object (TCBS comprehensive approach).
        
        Args:
            symbol: Stock symbol (e.g., "VCI", "FPT")
            mapping: Whether to apply normalized field mapping for cross-platform consistency
            
        Returns:
            Dictionary containing all company data: overview, profile, shareholders, officers
        """
        print(f"Fetching comprehensive company information for {symbol}...")
        
        company_data = {
            "symbol": symbol.upper()
        }
        
        # Get company overview
        overview_df = self.overview(symbol)
        if overview_df is not None and not overview_df.empty:
            company_data["overview"] = overview_df.to_dict('records')[0]
        else:
            company_data["overview"] = None
            
        # Small delay between requests
        time.sleep(0.5)
        
        # Get company profile
        profile_df = self.profile(symbol)
        if profile_df is not None and not profile_df.empty:
            company_data["profile"] = profile_df.to_dict('records')[0]
        else:
            company_data["profile"] = None
            
        # Small delay between requests  
        time.sleep(0.5)
        
        # Get shareholders
        shareholders_df = self.shareholders(symbol)
        if shareholders_df is not None and not shareholders_df.empty:
            company_data["shareholders"] = shareholders_df.to_dict('records')
        else:
            company_data["shareholders"] = []
            
        # Small delay between requests
        time.sleep(0.5)
        
        # Get officers
        officers_df = self.officers(symbol)
        if officers_df is not None and not officers_df.empty:
            company_data["officers"] = officers_df.to_dict('records')
        else:
            company_data["officers"] = []
            
        # Calculate market cap if we have the data
        if company_data["overview"] and "outstanding_share" in company_data["overview"]:
            try:
                # Get current price
                current_price = self.get_current_price(symbol)
                outstanding_shares = company_data["overview"]["outstanding_share"]
                
                if current_price is not None and outstanding_shares is not None:
                    # TCBS might return outstanding shares in millions, let's check
                    # VCI should have around 1.3 billion shares, but we got 723
                    # This suggests shares are in millions (723 million = 723,000,000)
                    shares_in_units = outstanding_shares * 1_000_000  # Convert millions to actual shares
                    market_cap = shares_in_units * current_price
                    
                    company_data["market_cap"] = market_cap
                    company_data["current_price"] = current_price
                    company_data["outstanding_shares_millions"] = outstanding_shares
                    company_data["outstanding_shares_actual"] = shares_in_units
                    
                    print(f"Outstanding shares (millions): {outstanding_shares:,.1f}")
                    print(f"Outstanding shares (actual): {shares_in_units:,.0f}")
                    print(f"Current price: {current_price:,.0f} VND")
                    print(f"Calculated market cap: {market_cap:,.0f} VND")
                else:
                    company_data["market_cap"] = None
                    company_data["current_price"] = current_price
            except Exception as e:
                print(f"Could not calculate market cap: {e}")
                company_data["market_cap"] = None
                company_data["current_price"] = None
        else:
            company_data["market_cap"] = None  
            company_data["current_price"] = None
            
        print(f"Successfully fetched comprehensive company information for {symbol}")
        
        # Apply field mapping if requested
        if mapping:
            return self._normalize_tcbs_data(company_data)
        else:
            return company_data

    def financial_balance_sheet(self, symbol: str, period: str = "quarter") -> Optional[pd.DataFrame]:
        """Get balance sheet data using direct TCBS REST API call."""
        period_map = {"quarter": 1, "year": 0}
        tcbs_period = period_map.get(period, 1)
        
        url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/{symbol.upper()}/balance_sheet"
        params = {'yearly': tcbs_period, 'isAll': True}
        
        try:
            response = self.session.get(url, params=params, timeout=30, headers=self._get_headers())
            if response.status_code == 200:
                data = response.json()
                if data:
                    df = pd.DataFrame(data)
                    # Convert year and quarter to string and process like TCBS does
                    if not df.empty:
                        df['year'] = df['year'].astype(str)
                        df['quarter'] = df['quarter'].astype(str)
                        if period == 'quarter':
                            df['period'] = df['year'] + '-Q' + df['quarter']
                        else:
                            df = df.drop(columns='quarter', errors='ignore')
                            df = df.rename(columns={'year': 'period'})
                        df = df.set_index('period')
                        # Convert camelCase to snake_case
                        df.columns = [self._camel_to_snake(col) for col in df.columns]
                        return df
            return None
        except Exception as e:
            print(f"Error fetching TCBS balance sheet: {e}")
            return None
    
    def financial_income_statement(self, symbol: str, period: str = "quarter") -> Optional[pd.DataFrame]:
        """Get income statement data using direct TCBS REST API call."""
        period_map = {"quarter": 1, "year": 0}
        tcbs_period = period_map.get(period, 1)
        
        url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/{symbol.upper()}/income_statement"
        params = {'yearly': tcbs_period, 'isAll': True}
        
        try:
            response = self.session.get(url, params=params, timeout=30, headers=self._get_headers())
            if response.status_code == 200:
                data = response.json()
                if data:
                    df = pd.DataFrame(data)
                    if not df.empty:
                        df['year'] = df['year'].astype(str)
                        df['quarter'] = df['quarter'].astype(str)
                        if period == 'quarter':
                            df['period'] = df['year'] + '-Q' + df['quarter']
                        else:
                            df = df.drop(columns='quarter', errors='ignore')
                            df = df.rename(columns={'year': 'period'})
                        df = df.set_index('period')
                        df.columns = [self._camel_to_snake(col) for col in df.columns]
                        return df
            return None
        except Exception as e:
            print(f"Error fetching TCBS income statement: {e}")
            return None
    
    def financial_cash_flow(self, symbol: str, period: str = "quarter") -> Optional[pd.DataFrame]:
        """Get cash flow data using direct TCBS REST API call."""
        period_map = {"quarter": 1, "year": 0}
        tcbs_period = period_map.get(period, 1)
        
        url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/{symbol.upper()}/cash_flow"
        params = {'yearly': tcbs_period, 'isAll': True}
        
        try:
            response = self.session.get(url, params=params, timeout=30, headers=self._get_headers())
            if response.status_code == 200:
                data = response.json()
                if data:
                    df = pd.DataFrame(data)
                    if not df.empty:
                        df['year'] = df['year'].astype(str)
                        df['quarter'] = df['quarter'].astype(str)
                        # Cash flow might not have the same period processing
                        df.columns = [self._camel_to_snake(col) for col in df.columns]
                        return df
            return None
        except Exception as e:
            print(f"Error fetching TCBS cash flow: {e}")
            return None
    
    def financial_ratios(self, symbol: str, period: str = "quarter") -> Optional[pd.DataFrame]:
        """Get financial ratios data using direct TCBS REST API call."""
        period_map = {"quarter": 1, "year": 0}
        tcbs_period = period_map.get(period, 1)
        
        url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/{symbol.upper()}/financialratio"
        params = {'yearly': tcbs_period, 'isAll': True}
        
        try:
            response = self.session.get(url, params=params, timeout=30, headers=self._get_headers())
            if response.status_code == 200:
                data = response.json()
                if data:
                    df = pd.DataFrame(data)
                    if not df.empty:
                        df['year'] = df['year'].astype(str)
                        df['quarter'] = df['quarter'].astype(str) if 'quarter' in df.columns else ''
                        if period == 'quarter' and 'quarter' in df.columns:
                            df['period'] = df['year'] + '-Q' + df['quarter']
                        else:
                            df = df.drop(columns='quarter', errors='ignore')
                            df = df.rename(columns={'year': 'period'})
                        df = df.set_index('period')
                        df.columns = [self._camel_to_snake(col) for col in df.columns]
                        return df
            return None
        except Exception as e:
            print(f"Error fetching TCBS financial ratios: {e}")
            return None
    
    def _camel_to_snake(self, name: str) -> str:
        """Convert camelCase to snake_case."""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def financial_info(self, symbol: str, period: str = "quarter", mapping: bool = True) -> Optional[Dict]:
        """
        Get comprehensive financial information in a single object using direct TCBS API calls.
        
        Args:
            symbol: Stock symbol (e.g., "VCI", "FPT")
            period: Financial reporting period - "quarter" or "year"
            mapping: Whether to apply normalized field mapping for cross-platform consistency
            
        Returns:
            Dictionary containing all financial data: balance sheet, income statement, cash flow, ratios
        """
        print(f"Fetching comprehensive financial information for {symbol} (period: {period})...")
        
        financial_data = {
            "symbol": symbol.upper(),
            "period": period
        }
        
        # Get balance sheet data
        print(f"Fetching balance sheet for {symbol}...")
        try:
            balance_sheet_df = self.financial_balance_sheet(symbol, period)
            if balance_sheet_df is not None and not balance_sheet_df.empty:
                financial_data["balance_sheet"] = balance_sheet_df.to_dict('index')
            else:
                financial_data["balance_sheet"] = None
        except Exception as e:
            print(f"Could not fetch balance sheet: {e}")
            financial_data["balance_sheet"] = None
        
        # Small delay between requests
        time.sleep(0.5)
        
        # Get income statement data
        print(f"Fetching income statement for {symbol}...")
        try:
            income_statement_df = self.financial_income_statement(symbol, period)
            if income_statement_df is not None and not income_statement_df.empty:
                financial_data["income_statement"] = income_statement_df.to_dict('index')
            else:
                financial_data["income_statement"] = None
        except Exception as e:
            print(f"Could not fetch income statement: {e}")
            financial_data["income_statement"] = None
        
        # Small delay between requests
        time.sleep(0.5)
        
        # Get cash flow data
        print(f"Fetching cash flow for {symbol}...")
        try:
            cash_flow_df = self.financial_cash_flow(symbol, period)
            if cash_flow_df is not None and not cash_flow_df.empty:
                financial_data["cash_flow"] = cash_flow_df.to_dict('index')
            else:
                financial_data["cash_flow"] = None
        except Exception as e:
            print(f"Could not fetch cash flow: {e}")
            financial_data["cash_flow"] = None
        
        # Small delay between requests  
        time.sleep(0.5)
        
        # Get financial ratios data
        print(f"Fetching financial ratios for {symbol}...")
        try:
            ratios_df = self.financial_ratios(symbol, period)
            if ratios_df is not None and not ratios_df.empty:
                financial_data["ratios"] = ratios_df.to_dict('index')
            else:
                financial_data["ratios"] = None
        except Exception as e:
            print(f"Could not fetch financial ratios: {e}")
            financial_data["ratios"] = None
            
        print(f"Successfully fetched comprehensive financial information for {symbol}")
        
        # Apply field mapping if requested
        if mapping:
            return self._normalize_tcbs_financial_data(financial_data)
        else:
            return financial_data
    
    def _normalize_tcbs_financial_data(self, financial_data: Dict) -> Dict:
        """Normalize TCBS-specific financial data structure to standard format."""
        normalized = {
            'symbol': financial_data.get('symbol'),
            'period': financial_data.get('period'),
            'balance_sheet': None,
            'income_statement': None,
            'cash_flow': None,
            'ratios': None,
            
            # Key financial metrics (extracted from statements)
            'total_assets': None,
            'total_liabilities': None,
            'shareholders_equity': None,
            'total_revenue': None,
            'gross_profit': None,
            'operating_profit': None,
            'net_income': None,
            'cash_from_operations': None,
            'cash_from_investing': None,
            'cash_from_financing': None,
            'free_cash_flow': None,
            
            # Key ratios
            'pe': None,
            'pb': None,
            'roe': None,
            'roa': None,
            'debt_to_equity': None,
            'current_ratio': None,
            'quick_ratio': None,
            'gross_margin': None,
            'net_margin': None,
            'asset_turnover': None
        }
        
        # Normalize raw financial statement data while preserving structure
        if financial_data.get('balance_sheet'):
            normalized['balance_sheet'] = financial_data['balance_sheet']
            # Extract key balance sheet metrics from most recent period
            periods = list(financial_data['balance_sheet'].keys())
            if periods:
                latest_period = periods[0]  # Most recent period
                latest_bs = financial_data['balance_sheet'][latest_period]
                # Map common balance sheet fields (TCBS specific field names)
                normalized['total_assets'] = latest_bs.get('total_asset') or latest_bs.get('totalAsset')
                normalized['total_liabilities'] = latest_bs.get('total_liability') or latest_bs.get('totalLiability') 
                normalized['shareholders_equity'] = latest_bs.get('total_equity') or latest_bs.get('totalEquity')
        
        if financial_data.get('income_statement'):
            normalized['income_statement'] = financial_data['income_statement']
            # Extract key income statement metrics from most recent period
            periods = list(financial_data['income_statement'].keys())
            if periods:
                latest_period = periods[0]  # Most recent period
                latest_is = financial_data['income_statement'][latest_period]
                # Map common income statement fields (TCBS specific field names)
                normalized['total_revenue'] = latest_is.get('net_sale') or latest_is.get('revenue')
                normalized['gross_profit'] = latest_is.get('gross_profit')
                normalized['operating_profit'] = latest_is.get('profit_from_business_activities') or latest_is.get('operating_profit')
                normalized['net_income'] = latest_is.get('profit_after_tax') or latest_is.get('net_income')
        
        if financial_data.get('cash_flow'):
            normalized['cash_flow'] = financial_data['cash_flow']
            # Extract key cash flow metrics from most recent period
            periods = list(financial_data['cash_flow'].keys())
            if periods:
                latest_period = periods[0]  # Most recent period
                latest_cf = financial_data['cash_flow'][latest_period]
                # Map common cash flow fields (TCBS specific field names)
                normalized['cash_from_operations'] = latest_cf.get('net_cash_flow_from_operating_activities')
                normalized['cash_from_investing'] = latest_cf.get('net_cash_flow_from_investing_activities')
                normalized['cash_from_financing'] = latest_cf.get('net_cash_flow_from_financing_activities')
                # Calculate free cash flow if possible
                if normalized['cash_from_operations'] and normalized['cash_from_investing']:
                    normalized['free_cash_flow'] = normalized['cash_from_operations'] + normalized['cash_from_investing']
        
        if financial_data.get('ratios'):
            normalized['ratios'] = financial_data['ratios']
            # Extract key ratios from most recent period
            periods = list(financial_data['ratios'].keys())
            if periods:
                latest_period = periods[0]  # Most recent period
                latest_ratios = financial_data['ratios'][latest_period]
                # Map common ratio fields (TCBS specific field names)
                normalized['pe'] = latest_ratios.get('price_to_earning') or latest_ratios.get('pe')
                normalized['pb'] = latest_ratios.get('price_to_book') or latest_ratios.get('pb')
                normalized['roe'] = latest_ratios.get('roe')
                normalized['roa'] = latest_ratios.get('roa')
                normalized['debt_to_equity'] = latest_ratios.get('debt_on_equity') or latest_ratios.get('debt_to_equity')
                normalized['current_ratio'] = latest_ratios.get('current_ratio')
                normalized['quick_ratio'] = latest_ratios.get('quick_ratio')
                normalized['gross_margin'] = latest_ratios.get('gross_profit_margin') or latest_ratios.get('gross_margin')
                normalized['net_margin'] = latest_ratios.get('net_profit_margin') or latest_ratios.get('net_margin')
        
        return normalized
    
    def _camel_to_snake(self, name: str) -> str:
        """Convert camelCase to snake_case."""
        import re
        # Handle special cases first
        name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
        return name.lower()


def main():
    """Test TCBS client: 1. Company Info, 2. Financial Info, 3. History."""
    print("\n" + "="*60)
    print("TCBS CLIENT - COMPREHENSIVE TESTING")
    print("="*60)
    
    client = TCBSClient(random_agent=True, rate_limit_per_minute=6)
    test_symbol = "VCI"
    
    # 1. COMPANY INFO
    print(f"\n🏢 Step 1: Company Information for {test_symbol}")
    print("-" * 40)
    try:
        company_data = client.company_info(test_symbol)
        if company_data:
            print(f"✅ Success! Company data retrieved")
            print(f"📊 Exchange: {company_data.get('exchange', 'N/A')}")
            print(f"🏭 Industry: {company_data.get('industry', 'N/A')}")
            if company_data.get('market_cap'):
                market_cap_b = company_data['market_cap'] / 1_000_000_000
                print(f"💰 Market Cap: {market_cap_b:,.1f}B VND")
            if company_data.get('outstanding_shares'):
                print(f"📈 Outstanding Shares: {company_data['outstanding_shares']:,.0f}")
            print(f"👥 Shareholders: {len(company_data.get('shareholders', []))} major")
            print(f"👔 Officers: {len(company_data.get('officers', []))} management")
        else:
            print("❌ Failed to retrieve company data")
    except Exception as e:
        print(f"💥 Error in company info: {e}")
    
    time.sleep(2)
    
    # 2. FINANCIAL INFO
    print(f"\n💹 Step 2: Financial Information for {test_symbol}")
    print("-" * 40)
    try:
        financial_data = client.financial_info(test_symbol, period="quarter")
        if financial_data:
            print(f"✅ Success! Financial data retrieved")
            
            # Key metrics (TCBS may not have revenue/income in ratios)
            if financial_data.get('total_revenue'):
                print(f"💵 Revenue: {financial_data['total_revenue']:,.0f} VND")
            if financial_data.get('net_income'):
                print(f"💰 Net Income: {financial_data['net_income']:,.0f} VND")
            if financial_data.get('total_assets'):
                print(f"🏦 Total Assets: {financial_data['total_assets']:,.0f} VND")
            
            # Key ratios
            ratios = []
            if financial_data.get('pe'): ratios.append(f"PE: {financial_data['pe']:.1f}")
            if financial_data.get('pb'): ratios.append(f"PB: {financial_data['pb']:.1f}")
            if financial_data.get('roe'): ratios.append(f"ROE: {financial_data['roe']:.1%}")
            if financial_data.get('roa'): ratios.append(f"ROA: {financial_data['roa']:.1%}")
            if financial_data.get('debt_to_equity'): ratios.append(f"D/E: {financial_data['debt_to_equity']:.1f}")
            
            if ratios:
                print(f"📊 Ratios: {' | '.join(ratios)}")
        else:
            print("❌ Failed to retrieve financial data")
    except Exception as e:
        print(f"💥 Error in financial info: {e}")
    
    time.sleep(2)
    
    # 3. HISTORICAL DATA
    print(f"\n📈 Step 3: Historical Data for {test_symbol}")
    print("-" * 40)
    try:
        df = client.get_history(
            symbol=test_symbol,
            start="2025-08-01",
            end="2025-08-13", 
            interval="1D",
            count_back=365
        )
        
        if df is not None and not df.empty:
            data_count = len(df)
            print(f"✅ Success! Retrieved {data_count} data points")
            print(f"📅 Range: {df.index[0]} to {df.index[-1]}")
            
            # Latest data
            latest = df.iloc[-1]
            print(f"💹 Latest: {latest['Close']:.0f} VND (Vol: {latest['Volume']:,})")
            
            # Price change
            if len(df) > 1:
                first_price = df['Open'].iloc[0]
                last_price = df['Close'].iloc[-1]
                change_pct = ((last_price - first_price) / first_price) * 100
                print(f"📊 Change: {change_pct:+.2f}% | Range: {df['Low'].min():.0f}-{df['High'].max():.0f}")
        else:
            print("❌ Failed to retrieve historical data")
    except Exception as e:
        print(f"💥 Error in historical data: {e}")
    
    print(f"\n{'='*60}")
    print("✅ TCBS CLIENT TESTING COMPLETED")
    print("="*60)

if __name__ == "__main__":
    main()