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
        'issue_shares': 'issue_shares',
        'company_profile': 'company_profile',
        'website': 'website',
        
        # Price Info
        'match_price': 'current_price',
        'price_change': 'price_change',
        'percent_price_change': 'percent_price_change',
        'total_volume': 'volume',
        'high_52w': 'high_52w',
        'low_52w': 'low_52w',
        
        # Financial Ratios
        'pe_ratio': 'pe',
        'pb_ratio': 'pb',
        'roe': 'roe',
        'roa': 'roa',
        'eps': 'eps',
        'revenue': 'revenue',
        'net_profit': 'net_profit',
        'dividend': 'dividend',
        
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
        'free_cash_flow': 'free_cash_flow',
        
        # Shareholders (VCI format)
        'shareholder_name': 'name',
        'shareholder_percent': 'percentage',
        
        # Officers (VCI format)
        'officer_name': 'fullName',
        'officer_position': 'positionName',
        'officer_percent': 'percentage'
    }
    
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
        
        # Resample mapping for client-side aggregation (cloned from vnstock)
        self.resample_map = {
            '5m': '5min',
            '15m': '15min',
            '30m': '30min',
            '1H': '1H',
            '1W': '1W',
            '1M': 'M'
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
        
        # Apply resampling if needed (cloned from vnstock logic)
        if interval in self.resample_map and interval not in ["1m", "1H", "1D"]:
            print(f"Applying {interval} resampling using pandas resample...")
            df = df.set_index('time').resample(self.resample_map[interval]).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min', 
                'close': 'last',
                'volume': 'sum'
            }).reset_index()
            
            # Remove rows with NaN values (weekends, holidays)
            df = df.dropna().reset_index(drop=True)
        
        print(f"Successfully fetched {len(df)} data points")
        return df

    def get_batch_history(self, 
                         symbols: List[str], 
                         start: str, 
                         end: Optional[str] = None, 
                         interval: str = "1D") -> Optional[Dict[str, pd.DataFrame]]:
        """
        Fetch historical stock data for multiple symbols in a single request.
        
        Args:
            symbols: List of stock symbols (e.g., ["VCI", "AAA", "ACB"])
            start: Start date in "YYYY-MM-DD" format
            end: End date in "YYYY-MM-DD" format (optional)
            interval: Time interval - 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M
            
        Returns:
            Dictionary mapping symbol -> DataFrame with columns: time, open, high, low, close, volume
        """
        if interval not in self.interval_map:
            raise ValueError(f"Invalid interval: {interval}. Valid options: {list(self.interval_map.keys())}")
        
        if not symbols or len(symbols) == 0:
            raise ValueError("Symbols list cannot be empty")
            
        # Prepare request parameters
        end_timestamp = self._calculate_timestamp(end)
        count_back = self._calculate_count_back(start, end, interval)
        interval_value = self.interval_map[interval]
        
        url = f"{self.base_url}chart/OHLCChart/gap-chart"
        payload = {
            "timeFrame": interval_value,
            "symbols": symbols,  # Pass all symbols at once
            "to": end_timestamp,
            "countBack": count_back
        }
        
        print(f"Fetching batch data for {len(symbols)} symbols: {', '.join(symbols)}")
        print(f"Date range: {start} to {end or 'now'} [{interval}] (count_back={count_back})")
        
        # Make the request
        response_data = self._make_request(url, payload)
        
        if not response_data or not isinstance(response_data, list):
            print("No data received from API")
            return None
            
        if len(response_data) != len(symbols):
            print(f"Warning: Expected {len(symbols)} responses, got {len(response_data)}")
        
        # Debug: Show VCI batch response structure
        print(f"🔍 VCI BATCH DEBUG:")
        print(f"  Requested symbols: {symbols}")
        print(f"  Response array length: {len(response_data)}")
        
        # Debug: Check if response includes symbol identifiers
        for i, item in enumerate(response_data):
            if isinstance(item, dict):
                # Check for symbol field or any identifier
                symbol_fields = ['symbol', 'ticker', 'Symbol', 'Ticker', 's']
                found_symbol = None
                for field in symbol_fields:
                    if field in item:
                        found_symbol = item[field]
                        break
                print(f"    response[{i}] symbol field: {found_symbol}")
                if 'c' in item and len(item['c']) > 0:
                    print(f"    response[{i}] last close: {item['c'][-1]}")
        
        results = {}
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        
        # Create a mapping from response data using symbol field
        response_map = {}
        for i, data_item in enumerate(response_data):
            # Find symbol identifier in response
            symbol_fields = ['symbol', 'ticker', 'Symbol', 'Ticker', 's']
            response_symbol = None
            for field in symbol_fields:
                if field in data_item:
                    response_symbol = data_item[field]
                    break
            
            if response_symbol:
                response_map[response_symbol.upper()] = data_item
                print(f"  Mapped response[{i}] -> symbol: {response_symbol}")
            else:
                print(f"  WARNING: No symbol field found in response[{i}]")
        
        # Process each requested symbol using correct mapping
        for symbol in symbols:
            symbol_upper = symbol.upper()
            print(f"  Processing symbol: {symbol}")
            
            if symbol_upper not in response_map:
                print(f"No data available for symbol: {symbol}")
                results[symbol] = None
                continue
                
            data_item = response_map[symbol_upper]
            
            # Check if we have the required OHLCV arrays
            required_keys = ['o', 'h', 'l', 'c', 'v', 't']
            if not all(key in data_item for key in required_keys):
                print(f"Missing required keys for {symbol}. Available: {list(data_item.keys())}")
                results[symbol] = None
                continue
                
            # Get the arrays
            opens = data_item['o']
            highs = data_item['h'] 
            lows = data_item['l']
            closes = data_item['c']
            volumes = data_item['v']
            times = data_item['t']
            
            # Debug: Show last close price for this response item
            if len(closes) > 0:
                print(f"    Last close price in response[{i}]: {closes[-1]}")
            
            # Check if all arrays have the same length
            lengths = [len(arr) for arr in [opens, highs, lows, closes, volumes, times]]
            if not all(length == lengths[0] for length in lengths):
                print(f"Inconsistent array lengths for {symbol}: {lengths}")
                results[symbol] = None
                continue
                
            if lengths[0] == 0:
                print(f"Empty data arrays for {symbol}")
                results[symbol] = None
                continue
                
            # Convert to DataFrame
            df_data = []
            for j in range(len(times)):
                close_val = float(closes[j])
                # Debug: Track VND close price transformation
                if symbol == 'VND' and j == len(times) - 1:  # Last row
                    print(f"    VND DataFrame conversion: raw_close={closes[j]} -> float_close={close_val}")
                
                df_data.append({
                    'time': pd.to_datetime(int(times[j]), unit='s'),
                    'open': float(opens[j]),
                    'high': float(highs[j]),
                    'low': float(lows[j]),
                    'close': close_val,
                    'volume': int(volumes[j]) if volumes[j] is not None else 0
                })
                
            df = pd.DataFrame(df_data)
            
            # Debug: Show VND data after DataFrame creation
            if symbol == 'VND' and not df.empty:
                print(f"    VND DataFrame before filtering: {len(df)} rows")
                for i, row in df.iterrows():
                    print(f"      Row {i}: time={row['time']}, close={row['close']}, open={row['open']}")
                last_row = df.iloc[-1]
                print(f"    VND after DataFrame creation: close={last_row['close']}, open={last_row['open']}")
            
            # Filter by start date
            df = df[df['time'] >= start_dt].reset_index(drop=True)
            
            # Debug: Show VND data after filtering
            if symbol == 'VND' and not df.empty:
                last_row = df.iloc[-1]
                print(f"    VND after filtering: close={last_row['close']}, open={last_row['open']}")
            
            # Sort by time
            df = df.sort_values('time').reset_index(drop=True)
            
            # Debug: Show VND data after sorting
            if symbol == 'VND' and not df.empty:
                last_row = df.iloc[-1]
                print(f"    VND after sorting: close={last_row['close']}, open={last_row['open']}")
            
            # Apply resampling if needed (cloned from vnstock logic)
            if interval in self.resample_map and interval not in ["1m", "1H", "1D"]:
                if not df.empty:
                    print(f"    Applying {interval} resampling for {symbol}...")
                    df = df.set_index('time').resample(self.resample_map[interval]).agg({
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum'
                    }).reset_index()
                    
                    # Remove rows with NaN values (weekends, holidays)
                    df = df.dropna().reset_index(drop=True)
            
            # Add symbol column for identification
            df['symbol'] = symbol
            
            # Debug: Show final VND data before returning to main pipeline
            if symbol == 'VND' and not df.empty:
                last_row = df.iloc[-1]
                print(f"    VND FINAL VCI CLIENT DATA: close={last_row['close']}, open={last_row['open']}")
            
            results[symbol] = df
            print(f"✅ {symbol}: {len(df)} data points")
        
        successful_count = sum(1 for df in results.values() if df is not None)
        print(f"Successfully fetched data for {successful_count}/{len(symbols)} symbols")
        
        return results
    
    def overview(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get company overview data using VCI GraphQL endpoint (same as vnstock).
        
        Args:
            symbol: Stock symbol (e.g., "VCB", "VCI")
            
        Returns:
            DataFrame with comprehensive company information
        """
        # Use the same GraphQL endpoint as vnstock
        url = f"{self.base_url.replace('/api/', '/data-mt/')}graphql"
        
        # The EXACT same GraphQL query used by vnstock
        graphql_query = """query Query($ticker: String!, $lang: String!) {
  AnalysisReportFiles(ticker: $ticker, langCode: $lang) {
    date
    description
    link
    name
    __typename
  }
  News(ticker: $ticker, langCode: $lang) {
    id
    organCode
    ticker
    newsTitle
    newsSubTitle
    friendlySubTitle
    newsImageUrl
    newsSourceLink
    createdAt
    publicDate
    updatedAt
    langCode
    newsId
    newsShortContent
    newsFullContent
    closePrice
    referencePrice
    floorPrice
    ceilingPrice
    percentPriceChange
    __typename
  }
  TickerPriceInfo(ticker: $ticker) {
    financialRatio {
      yearReport
      lengthReport
      updateDate
      revenue
      revenueGrowth
      netProfit
      netProfitGrowth
      ebitMargin
      roe
      roic
      roa
      pe
      pb
      eps
      currentRatio
      cashRatio
      quickRatio
      interestCoverage
      ae
      fae
      netProfitMargin
      grossMargin
      ev
      issueShare
      ps
      pcf
      bvps
      evPerEbitda
      at
      fat
      acp
      dso
      dpo
      epsTTM
      charterCapital
      RTQ4
      charterCapitalRatio
      RTQ10
      dividend
      ebitda
      ebit
      le
      de
      ccc
      RTQ17
      __typename
    }
    ticker
    exchange
    ev
    ceilingPrice
    floorPrice
    referencePrice
    openPrice
    matchPrice
    closePrice
    priceChange
    percentPriceChange
    highestPrice
    lowestPrice
    totalVolume
    highestPrice1Year
    lowestPrice1Year
    percentLowestPriceChange1Year
    percentHighestPriceChange1Year
    foreignTotalVolume
    foreignTotalRoom
    averageMatchVolume2Week
    foreignHoldingRoom
    currentHoldingRatio
    maxHoldingRatio
    __typename
  }
  Subsidiary(ticker: $ticker) {
    id
    organCode
    subOrganCode
    percentage
    subOrListingInfo {
      enOrganName
      organName
      __typename
    }
    __typename
  }
  Affiliate(ticker: $ticker) {
    id
    organCode
    subOrganCode
    percentage
    subOrListingInfo {
      enOrganName
      organName
      __typename
    }
    __typename
  }
  CompanyListingInfo(ticker: $ticker) {
    id
    issueShare
    en_History
    history
    en_CompanyProfile
    companyProfile
    icbName3
    enIcbName3
    icbName2
    enIcbName2
    icbName4
    enIcbName4
    financialRatio {
      id
      ticker
      issueShare
      charterCapital
      __typename
    }
    __typename
  }
  OrganizationManagers(ticker: $ticker) {
    id
    ticker
    fullName
    positionName
    positionShortName
    en_PositionName
    en_PositionShortName
    updateDate
    percentage
    quantity
    __typename
  }
  OrganizationShareHolders(ticker: $ticker) {
    id
    ticker
    ownerFullName
    en_OwnerFullName
    quantity
    percentage
    updateDate
    __typename
  }
  OrganizationResignedManagers(ticker: $ticker) {
    id
    ticker
    fullName
    positionName
    positionShortName
    en_PositionName
    en_PositionShortName
    updateDate
    percentage
    quantity
    __typename
  }
  OrganizationEvents(ticker: $ticker) {
    id
    organCode
    ticker
    eventTitle
    en_EventTitle
    publicDate
    issueDate
    sourceUrl
    eventListCode
    ratio
    value
    recordDate
    exrightDate
    eventListName
    en_EventListName
    __typename
  }
}"""
        
        payload = {
            "query": graphql_query,
            "variables": {"ticker": symbol.upper(), "lang": "vi"}
        }
        
        print(f"Fetching company overview for {symbol}...")
        
        response_data = self._make_request(url, payload)
        
        if not response_data or "data" not in response_data:
            print("No company data received from API")
            return None
            
        if not response_data["data"] or "CompanyListingInfo" not in response_data["data"]:
            print("No CompanyListingInfo found in response")
            return None
            
        # Extract company listing info (same as vnstock)
        company_data = response_data["data"]["CompanyListingInfo"]
        
        # Flatten the nested structure
        overview_data = {}
        
        # Basic company info
        overview_data.update({
            'symbol': symbol.upper(),
            'issueShare': company_data.get('issueShare', 'N/A'),
            'companyProfile': company_data.get('companyProfile', 'N/A'),
            'en_CompanyProfile': company_data.get('en_CompanyProfile', 'N/A'),
            'history': company_data.get('history', 'N/A'),
            'en_History': company_data.get('en_History', 'N/A'),
            'icbName2': company_data.get('icbName2', 'N/A'),
            'enIcbName2': company_data.get('enIcbName2', 'N/A'),
            'icbName3': company_data.get('icbName3', 'N/A'),
            'enIcbName3': company_data.get('enIcbName3', 'N/A'),
            'icbName4': company_data.get('icbName4', 'N/A'),
            'enIcbName4': company_data.get('enIcbName4', 'N/A')
        })
        
        # Financial ratio data from company listing
        if 'financialRatio' in company_data and company_data['financialRatio']:
            fin_ratio = company_data['financialRatio']
            overview_data.update({
                'charterCapital': fin_ratio.get('charterCapital', 'N/A')
            })
        
        # Convert to DataFrame (same format as vnstock)
        df = pd.DataFrame([overview_data]).T
        df.columns = ["value"]
        df.index.name = "attribute"
        
        print(f"Successfully fetched company overview for {symbol}")
        return df
    
    def ratio_summary(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get financial ratio summary using VCI GraphQL endpoint (same as vnstock).
        
        Args:
            symbol: Stock symbol (e.g., "VCB", "VCI")
            
        Returns:
            DataFrame with comprehensive financial ratios
        """
        # Use the same GraphQL approach as overview method
        url = f"{self.base_url.replace('/api/', '/data-mt/')}graphql"
        
        # Same GraphQL query as overview (reuse the comprehensive query)
        graphql_query = """query Query($ticker: String!, $lang: String!) {
  TickerPriceInfo(ticker: $ticker) {
    financialRatio {
      yearReport
      lengthReport
      updateDate
      revenue
      revenueGrowth
      netProfit
      netProfitGrowth
      ebitMargin
      roe
      roic
      roa
      pe
      pb
      eps
      currentRatio
      cashRatio
      quickRatio
      interestCoverage
      ae
      fae
      netProfitMargin
      grossMargin
      ev
      issueShare
      ps
      pcf
      bvps
      evPerEbitda
      at
      fat
      acp
      dso
      dpo
      epsTTM
      charterCapital
      RTQ4
      charterCapitalRatio
      RTQ10
      dividend
      ebitda
      ebit
      le
      de
      ccc
      RTQ17
      __typename
    }
    ticker
    exchange
    ev
    ceilingPrice
    floorPrice
    referencePrice
    openPrice
    matchPrice
    closePrice
    priceChange
    percentPriceChange
    highestPrice
    lowestPrice
    totalVolume
    __typename
  }
}"""
        
        payload = {
            "query": graphql_query,
            "variables": {"ticker": symbol.upper(), "lang": "vi"}
        }
        
        print(f"Fetching financial ratios for {symbol}...")
        
        response_data = self._make_request(url, payload)
        
        if not response_data or "data" not in response_data:
            print("No financial ratio data received from API")
            return None
            
        if not response_data["data"] or "TickerPriceInfo" not in response_data["data"]:
            print("No TickerPriceInfo found in response")
            return None
            
        # Extract financial ratio data (same as vnstock)
        ticker_info = response_data["data"]["TickerPriceInfo"]
        if not ticker_info or "financialRatio" not in ticker_info:
            print("No financial ratios available for this symbol")
            return None
            
        financial_ratios = ticker_info["financialRatio"]
        
        # Convert to DataFrame format (same as vnstock)
        df_data = []
        for key, value in financial_ratios.items():
            if key != "__typename" and value is not None and value != 'N/A':
                df_data.append({
                    "symbol": symbol.upper(),
                    "ratio_name": key,
                    "value": value
                })
        
        if not df_data:
            print("No valid financial ratios found")
            return None
            
        df = pd.DataFrame(df_data)
        
        # Reorder columns to match vnstock format
        df = df[["symbol", "ratio_name", "value"]]
        
        print(f"Successfully fetched {len(df)} financial ratios for {symbol}")
        return df
    
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
    
    def _normalize_vci_data(self, company_data: Dict) -> Dict:
        """Normalize VCI-specific data structure to standard format."""
        normalized = {
            'symbol': company_data.get('symbol'),
            'exchange': None,
            'industry': None,
            'company_type': None,
            'established_year': None,
            'employees': None,
            'market_cap': company_data.get('market_cap'),
            'current_price': company_data.get('current_price'),
            'outstanding_shares': company_data.get('issue_shares'),
            'company_profile': None,
            'website': None
        }
        
        # Extract from CompanyListingInfo
        if 'CompanyListingInfo' in company_data and company_data['CompanyListingInfo']:
            listing_info = company_data['CompanyListingInfo']
            normalized.update({
                'industry': listing_info.get('icbName3'),
                'company_profile': listing_info.get('companyProfile'),
                'outstanding_shares': listing_info.get('issueShare')
            })
            
        # Extract from TickerPriceInfo
        if 'TickerPriceInfo' in company_data and company_data['TickerPriceInfo']:
            price_info = company_data['TickerPriceInfo']
            normalized.update({
                'exchange': price_info.get('exchange'),
                'current_price': price_info.get('matchPrice'),
                'price_change': price_info.get('priceChange'),
                'percent_price_change': price_info.get('percentPriceChange'),
                'volume': price_info.get('totalVolume'),
                'high_52w': price_info.get('highestPrice1Year'),
                'low_52w': price_info.get('lowestPrice1Year')
            })
            
            # Extract financial ratios
            if 'financialRatio' in price_info and price_info['financialRatio']:
                ratios = price_info['financialRatio']
                normalized.update({
                    'pe': ratios.get('pe'),
                    'pb': ratios.get('pb'),
                    'roe': ratios.get('roe'),
                    'roa': ratios.get('roa'),
                    'eps': ratios.get('eps'),
                    'revenue': ratios.get('revenue'),
                    'net_profit': ratios.get('netProfit'),
                    'dividend': ratios.get('dividend')
                })
        
        # Normalize shareholders
        if 'OrganizationShareHolders' in company_data and company_data['OrganizationShareHolders']:
            normalized_shareholders = []
            for shareholder in company_data['OrganizationShareHolders']:
                normalized_shareholders.append({
                    'shareholder_name': shareholder.get('ownerFullName'),
                    'shareholder_percent': shareholder.get('percentage')
                })
            normalized['shareholders'] = normalized_shareholders
        
        # Normalize officers  
        if 'OrganizationManagers' in company_data and company_data['OrganizationManagers']:
            normalized_officers = []
            for manager in company_data['OrganizationManagers']:
                normalized_officers.append({
                    'officer_name': manager.get('fullName'),
                    'officer_position': manager.get('positionName'),
                    'officer_percent': manager.get('percentage')
                })
            normalized['officers'] = normalized_officers
            
        return normalized

    def company_info(self, symbol: str, mapping: bool = True) -> Optional[Dict]:
        """
        Get comprehensive company information in a single object (same as vnstock approach).
        
        Args:
            symbol: Stock symbol (e.g., "VCB", "VCI")
            mapping: Whether to apply normalized field mapping for cross-platform consistency
            
        Returns:
            Dictionary containing all company data: overview, ratios, price info, shareholders, managers, etc.
        """
        url = f"{self.base_url.replace('/api/', '/data-mt/')}graphql"
        
        # Complete GraphQL query that fetches ALL company data at once
        graphql_query = """query Query($ticker: String!, $lang: String!) {
  AnalysisReportFiles(ticker: $ticker, langCode: $lang) {
    date
    description
    link
    name
    __typename
  }
  News(ticker: $ticker, langCode: $lang) {
    id
    organCode
    ticker
    newsTitle
    newsSubTitle
    friendlySubTitle
    newsImageUrl
    newsSourceLink
    createdAt
    publicDate
    updatedAt
    langCode
    newsId
    newsShortContent
    newsFullContent
    closePrice
    referencePrice
    floorPrice
    ceilingPrice
    percentPriceChange
    __typename
  }
  TickerPriceInfo(ticker: $ticker) {
    financialRatio {
      yearReport
      lengthReport
      updateDate
      revenue
      revenueGrowth
      netProfit
      netProfitGrowth
      ebitMargin
      roe
      roic
      roa
      pe
      pb
      eps
      currentRatio
      cashRatio
      quickRatio
      interestCoverage
      ae
      fae
      netProfitMargin
      grossMargin
      ev
      issueShare
      ps
      pcf
      bvps
      evPerEbitda
      at
      fat
      acp
      dso
      dpo
      epsTTM
      charterCapital
      RTQ4
      charterCapitalRatio
      RTQ10
      dividend
      ebitda
      ebit
      le
      de
      ccc
      RTQ17
      __typename
    }
    ticker
    exchange
    ev
    ceilingPrice
    floorPrice
    referencePrice
    openPrice
    matchPrice
    closePrice
    priceChange
    percentPriceChange
    highestPrice
    lowestPrice
    totalVolume
    highestPrice1Year
    lowestPrice1Year
    percentLowestPriceChange1Year
    percentHighestPriceChange1Year
    foreignTotalVolume
    foreignTotalRoom
    averageMatchVolume2Week
    foreignHoldingRoom
    currentHoldingRatio
    maxHoldingRatio
    __typename
  }
  Subsidiary(ticker: $ticker) {
    id
    organCode
    subOrganCode
    percentage
    subOrListingInfo {
      enOrganName
      organName
      __typename
    }
    __typename
  }
  Affiliate(ticker: $ticker) {
    id
    organCode
    subOrganCode
    percentage
    subOrListingInfo {
      enOrganName
      organName
      __typename
    }
    __typename
  }
  CompanyListingInfo(ticker: $ticker) {
    id
    issueShare
    en_History
    history
    en_CompanyProfile
    companyProfile
    icbName3
    enIcbName3
    icbName2
    enIcbName2
    icbName4
    enIcbName4
    financialRatio {
      id
      ticker
      issueShare
      charterCapital
      __typename
    }
    __typename
  }
  OrganizationManagers(ticker: $ticker) {
    id
    ticker
    fullName
    positionName
    positionShortName
    en_PositionName
    en_PositionShortName
    updateDate
    percentage
    quantity
    __typename
  }
  OrganizationShareHolders(ticker: $ticker) {
    id
    ticker
    ownerFullName
    en_OwnerFullName
    quantity
    percentage
    updateDate
    __typename
  }
  OrganizationResignedManagers(ticker: $ticker) {
    id
    ticker
    fullName
    positionName
    positionShortName
    en_PositionName
    en_PositionShortName
    updateDate
    percentage
    quantity
    __typename
  }
  OrganizationEvents(ticker: $ticker) {
    id
    organCode
    ticker
    eventTitle
    en_EventTitle
    publicDate
    issueDate
    sourceUrl
    eventListCode
    ratio
    value
    recordDate
    exrightDate
    eventListName
    en_EventListName
    __typename
  }
}"""
        
        payload = {
            "query": graphql_query,
            "variables": {"ticker": symbol.upper(), "lang": "vi"}
        }
        
        print(f"Fetching comprehensive company information for {symbol}...")
        
        response_data = self._make_request(url, payload)
        
        if not response_data or "data" not in response_data:
            print("No company data received from API")
            return None
            
        # Return the complete data structure
        company_data = response_data["data"]
        
        # Add symbol to the root level for convenience
        company_data["symbol"] = symbol.upper()
        
        # Calculate market cap if we have the required data
        try:
            ticker_price_info = company_data.get("TickerPriceInfo")
            company_listing_info = company_data.get("CompanyListingInfo")
            
            if ticker_price_info and company_listing_info:
                current_price = ticker_price_info.get("matchPrice")
                issue_shares = company_listing_info.get("issueShare")
                
                if current_price is not None and issue_shares is not None:
                    # VCI returns actual share counts (not millions like TCBS)
                    market_cap = issue_shares * current_price
                    company_data["market_cap"] = market_cap
                    company_data["current_price"] = current_price
                    company_data["issue_shares"] = issue_shares
                    
                    print(f"Issue shares: {issue_shares:,.0f}")
                    print(f"Current price: {current_price:,.0f} VND")
                    print(f"Calculated market cap: {market_cap:,.0f} VND")
                else:
                    company_data["market_cap"] = None
                    company_data["current_price"] = current_price
                    company_data["issue_shares"] = issue_shares
            else:
                company_data["market_cap"] = None
                company_data["current_price"] = None
                company_data["issue_shares"] = None
        except Exception as e:
            print(f"Could not calculate market cap: {e}")
            company_data["market_cap"] = None
            company_data["current_price"] = None
            company_data["issue_shares"] = None
        
        print(f"Successfully fetched comprehensive company information for {symbol}")
        
        # Apply field mapping if requested
        if mapping:
            return self._normalize_vci_data(company_data)
        else:
            return company_data

    def financial_ratios(self, symbol: str, period: str = "quarter") -> Optional[pd.DataFrame]:
        """Get financial ratios data using direct VCI GraphQL API call."""
        period_map = {"quarter": "Q", "year": "Y"}
        vci_period = period_map.get(period, "Q")
        
        # VCI GraphQL query for comprehensive financial ratios
        payload = {
            "query": """fragment Ratios on CompanyFinancialRatio {
  ticker
  yearReport
  lengthReport
  updateDate
  revenue
  revenueGrowth
  netProfit
  netProfitGrowth
  ebitMargin
  roe
  roic
  roa
  pe
  pb
  eps
  currentRatio
  cashRatio
  quickRatio
  interestCoverage
  ae
  netProfitMargin
  grossMargin
  ev
  issueShare
  ps
  pcf
  bvps
  evPerEbitda
  BSA1
  BSA2
  BSA5
  BSA8
  BSA10
  BSA159
  BSA16
  BSA22
  BSA23
  BSA24
  BSA162
  BSA27
  BSA29
  BSA43
  BSA46
  BSA50
  BSA209
  BSA53
  BSA54
  BSA55
  BSA56
  BSA58
  BSA67
  BSA71
  BSA173
  BSA78
  BSA79
  BSA80
  BSA175
  BSA86
  BSA90
  BSA96
  CFA21
  CFA22
  at
  fat
  acp
  dso
  dpo
  ccc
  de
  le
  ebitda
  ebit
  dividend
  RTQ10
  charterCapitalRatio
  RTQ4
  epsTTM
  charterCapital
  fae
  RTQ17
  CFA26
  CFA6
  CFA9
  BSA85
  CFA36
  BSB98
  BSB101
  BSA89
  CFA34
  CFA14
  ISB34
  ISB27
  ISA23
  ISS152
  ISA102
  CFA27
  CFA12
  CFA28
  BSA18
  BSB102
  BSB110
  BSB108
  CFA23
  ISB41
  BSB103
  BSA40
  BSB99
  CFA16
  CFA18
  CFA3
  ISB30
  BSA33
  ISB29
  CFS200
  ISA2
  CFA24
  BSB105
  CFA37
  ISS141
  BSA95
  CFA10
  ISA4
  BSA82
  CFA25
  BSB111
  ISI64
  BSB117
  ISA20
  CFA19
  ISA6
  ISA3
  BSB100
  ISB31
  ISB38
  ISB26
  BSA210
  CFA20
  CFA35
  ISA17
  ISS148
  BSB115
  ISA9
  CFA4
  ISA7
  CFA5
  ISA22
  CFA8
  CFA33
  CFA29
  BSA30
  BSA84
  BSA44
  BSB107
  ISB37
  ISA8
  BSB109
  ISA19
  ISB36
  ISA13
  ISA1
  BSB121
  ISA14
  BSB112
  ISA21
  ISA10
  CFA11
  ISA12
  BSA15
  BSB104
  BSA92
  BSB106
  BSA94
  ISA18
  CFA17
  ISI87
  BSB114
  ISA15
  BSB116
  ISB28
  BSB97
  CFA15
  ISA11
  ISB33
  BSA47
  ISB40
  ISB39
  CFA7
  CFA13
  ISS146
  ISB25
  BSA45
  BSB118
  CFA1
  CFS191
  ISB35
  CFB65
  CFA31
  BSB113
  ISB32
  ISA16
  CFS210
  BSA48
  BSA36
  ISI97
  CFA30
  CFA2
  CFB80
  CFA38
  CFA32
  ISA5
  BSA49
  CFB64
  __typename
}

query Query($ticker: String!, $period: String!) {
  CompanyFinancialRatio(ticker: $ticker, period: $period) {
    ratio {
      ...Ratios
      __typename
    }
    period
    __typename
  }
}""",
            "variables": {
                "ticker": symbol.upper(),
                "period": vci_period
            }
        }
        
        try:
            response = self._make_request("https://trading.vietcap.com.vn/data-mt/graphql", payload)
            if response and 'data' in response and response['data']['CompanyFinancialRatio']:
                ratios_data = response['data']['CompanyFinancialRatio']['ratio']
                if ratios_data:
                    return pd.DataFrame(ratios_data)
            return None
        except Exception as e:
            print(f"Error fetching VCI financial ratios: {e}")
            return None

    def financial_info(self, symbol: str, period: str = "quarter", mapping: bool = True) -> Optional[Dict]:
        """
        Get comprehensive financial information in a single object using direct VCI API calls.
        
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
        
        # Get financial ratios data (contains most key metrics)
        print(f"Fetching financial ratios for {symbol}...")
        try:
            ratios_df = self.financial_ratios(symbol, period)
            if ratios_df is not None and not ratios_df.empty:
                financial_data["ratios"] = ratios_df.to_dict('records')
            else:
                financial_data["ratios"] = None
        except Exception as e:
            print(f"Could not fetch financial ratios: {e}")
            financial_data["ratios"] = None
            
        # Small delay between requests
        time.sleep(0.5)
        
        # Get balance sheet data (using BSA fields from ratios)
        print(f"Extracting balance sheet for {symbol}...")
        try:
            if ratios_df is not None and not ratios_df.empty:
                # Extract balance sheet fields (BSA codes)
                bs_fields = [col for col in ratios_df.columns if col.startswith('BSA') or col in ['ticker', 'yearReport', 'lengthReport']]
                if bs_fields:
                    balance_sheet_df = ratios_df[bs_fields].copy()
                    financial_data["balance_sheet"] = balance_sheet_df.to_dict('records')
                else:
                    financial_data["balance_sheet"] = None
            else:
                financial_data["balance_sheet"] = None
        except Exception as e:
            print(f"Could not extract balance sheet: {e}")
            financial_data["balance_sheet"] = None
            
        # Get income statement data (using ISA, ISB fields from ratios)
        print(f"Extracting income statement for {symbol}...")
        try:
            if ratios_df is not None and not ratios_df.empty:
                # Extract income statement fields (ISA, ISB codes)
                is_fields = [col for col in ratios_df.columns if col.startswith(('ISA', 'ISB', 'ISS', 'ISI')) or col in ['ticker', 'yearReport', 'lengthReport', 'revenue', 'netProfit', 'grossMargin', 'netProfitMargin']]
                if is_fields:
                    income_statement_df = ratios_df[is_fields].copy()
                    financial_data["income_statement"] = income_statement_df.to_dict('records')
                else:
                    financial_data["income_statement"] = None
            else:
                financial_data["income_statement"] = None
        except Exception as e:
            print(f"Could not extract income statement: {e}")
            financial_data["income_statement"] = None
            
        # Get cash flow data (using CFA, CFB, CFS fields from ratios)
        print(f"Extracting cash flow for {symbol}...")
        try:
            if ratios_df is not None and not ratios_df.empty:
                # Extract cash flow fields (CFA, CFB, CFS codes)
                cf_fields = [col for col in ratios_df.columns if col.startswith(('CFA', 'CFB', 'CFS')) or col in ['ticker', 'yearReport', 'lengthReport']]
                if cf_fields:
                    cash_flow_df = ratios_df[cf_fields].copy()
                    financial_data["cash_flow"] = cash_flow_df.to_dict('records')
                else:
                    financial_data["cash_flow"] = None
            else:
                financial_data["cash_flow"] = None
        except Exception as e:
            print(f"Could not extract cash flow: {e}")
            financial_data["cash_flow"] = None
            
        print(f"Successfully fetched comprehensive financial information for {symbol}")
        
        # Apply field mapping if requested
        if mapping:
            return self._normalize_vci_financial_data(financial_data)
        else:
            return financial_data
    
    def _normalize_vci_financial_data(self, financial_data: Dict) -> Dict:
        """Normalize VCI-specific financial data structure to standard format."""
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
            if len(financial_data['balance_sheet']) > 0:
                latest_bs = financial_data['balance_sheet'][0]
                # Map common balance sheet fields (VCI specific field names)
                normalized['total_assets'] = latest_bs.get('Total assets') or latest_bs.get('Total Assets')
                normalized['total_liabilities'] = latest_bs.get('Total liabilities') or latest_bs.get('Total Liabilities')
                normalized['shareholders_equity'] = latest_bs.get('Shareholders\' equity') or latest_bs.get('Total Equity')
        
        if financial_data.get('income_statement'):
            normalized['income_statement'] = financial_data['income_statement']
            # Extract key income statement metrics from most recent period
            if len(financial_data['income_statement']) > 0:
                latest_is = financial_data['income_statement'][0]
                # Map common income statement fields (VCI specific field names)
                normalized['total_revenue'] = latest_is.get('Net sales') or latest_is.get('Revenue')
                normalized['gross_profit'] = latest_is.get('Gross profit')
                normalized['operating_profit'] = latest_is.get('Profit from business activities') or latest_is.get('Operating Income')
                normalized['net_income'] = latest_is.get('Profit after tax') or latest_is.get('Net Income')
        
        if financial_data.get('cash_flow'):
            normalized['cash_flow'] = financial_data['cash_flow']
            # Extract key cash flow metrics from most recent period
            if len(financial_data['cash_flow']) > 0:
                latest_cf = financial_data['cash_flow'][0]
                # Map common cash flow fields (VCI specific field names)
                normalized['cash_from_operations'] = latest_cf.get('Net cash flows from operating activities')
                normalized['cash_from_investing'] = latest_cf.get('Net cash flows from investing activities')
                normalized['cash_from_financing'] = latest_cf.get('Net cash flows from financing activities')
                # Calculate free cash flow if possible
                if normalized['cash_from_operations'] and normalized['cash_from_investing']:
                    normalized['free_cash_flow'] = normalized['cash_from_operations'] + normalized['cash_from_investing']
        
        if financial_data.get('ratios'):
            normalized['ratios'] = financial_data['ratios']
            # Extract key ratios from most recent period
            if len(financial_data['ratios']) > 0:
                latest_ratios = financial_data['ratios'][0]
                # Map common ratio fields (VCI actual field names from API)
                normalized['pe'] = latest_ratios.get('pe')
                normalized['pb'] = latest_ratios.get('pb')
                normalized['roe'] = latest_ratios.get('roe')
                normalized['roa'] = latest_ratios.get('roa')
                normalized['debt_to_equity'] = latest_ratios.get('de')
                normalized['current_ratio'] = latest_ratios.get('currentRatio')
                normalized['quick_ratio'] = latest_ratios.get('quickRatio')
                normalized['gross_margin'] = latest_ratios.get('grossMargin')
                normalized['net_margin'] = latest_ratios.get('netProfitMargin')
                
                # Extract key financial metrics from ratios data
                normalized['total_revenue'] = latest_ratios.get('revenue')
                normalized['net_income'] = latest_ratios.get('netProfit')
                normalized['total_assets'] = latest_ratios.get('BSA1')  # Total assets from balance sheet code
                normalized['shareholders_equity'] = latest_ratios.get('ae')  # Average equity
        
        return normalized


def test_batch_history():
    """Test the new batch history functionality with 10 tickers."""
    print("\n" + "="*60)
    print("VCI CLIENT - BATCH HISTORY TESTING")
    print("="*60)
    
    client = VCIClient(random_agent=True, rate_limit_per_minute=6)
    
    # Test with the provided 10 tickers
    test_symbols = ["AAA", "ACB", "ACV", "ANV", "BCM", "BIC", "BID", "BMP", "BSI", "BSR"]
    
    print(f"\n📊 Testing batch history for {len(test_symbols)} symbols")
    print(f"Symbols: {', '.join(test_symbols)}")
    print("-" * 60)
    
    try:
        batch_data = client.get_batch_history(
            symbols=test_symbols,
            start="2025-08-01",
            end="2025-08-13",
            interval="1D"
        )
        
        if batch_data:
            print(f"\n✅ Batch request successful!")
            print(f"📈 Results summary:")
            print("-" * 40)
            
            successful_symbols = []
            failed_symbols = []
            
            for symbol, df in batch_data.items():
                if df is not None and len(df) > 0:
                    successful_symbols.append(symbol)
                    latest = df.iloc[-1]
                    print(f"  {symbol}: {len(df)} points | Latest: {latest['close']:.0f} VND (Vol: {latest['volume']:,})")
                else:
                    failed_symbols.append(symbol)
                    print(f"  {symbol}: ❌ No data")
            
            print(f"\n📊 Final Results:")
            print(f"  ✅ Success: {len(successful_symbols)}/{len(test_symbols)} symbols")
            print(f"  ❌ Failed: {len(failed_symbols)} symbols")
            
            if failed_symbols:
                print(f"  Failed symbols: {', '.join(failed_symbols)}")
                
            # Show sample data structure
            if successful_symbols:
                sample_symbol = successful_symbols[0]
                sample_df = batch_data[sample_symbol]
                print(f"\n📋 Sample data structure ({sample_symbol}):")
                print(sample_df.head(2).to_string(index=False))
                
        else:
            print("❌ Batch request failed - no data received")
            
    except Exception as e:
        print(f"💥 Error in batch history: {e}")
    
    print(f"\n{'='*60}")
    print("✅ BATCH HISTORY TESTING COMPLETED")
    print("="*60)


def test_1w_interval():
    """Test 1W interval specifically"""
    print("\n" + "="*50)
    print("VCI CLIENT - 1W INTERVAL TEST")
    print("="*50)
    
    client = VCIClient(random_agent=True, rate_limit_per_minute=6)
    test_symbol = "VCI"
    
    print(f"\n📈 Testing 1W interval for {test_symbol}")
    print("-" * 30)
    
    try:
        # Test single symbol 1W interval
        df = client.get_history(
            symbol=test_symbol,
            start="2025-07-01",  # More data for weekly aggregation
            end="2025-08-13", 
            interval="1W"
        )
        
        if df is not None and len(df) > 0:
            print(f"✅ Success! Retrieved {len(df)} weekly data points")
            print(f"📅 Date range: {df['time'].min()} to {df['time'].max()}")
            print(f"📊 Sample data:")
            print(df.head(3).to_string(index=False))
            
            # Check if data looks weekly aggregated
            if len(df) >= 2:
                time_diff = df['time'].iloc[1] - df['time'].iloc[0]
                print(f"⏱️  Time difference between points: {time_diff}")
                
                # Latest data
                latest = df.iloc[-1] 
                print(f"💹 Latest weekly close: {latest['close']:.0f} VND")
                print(f"📊 Latest weekly volume: {latest['volume']:,}")
        else:
            print("❌ Failed to retrieve 1W data")
            
    except Exception as e:
        print(f"💥 Error in 1W test: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*50}")
    print("✅ 1W INTERVAL TEST COMPLETED")
    print("="*50)


def test_batch_vnindex_vix():
    """Test batch history with VNINDEX and VIX"""
    print("\n" + "="*60)
    print("VCI CLIENT - BATCH TEST: VNINDEX & VIX")
    print("="*60)
    
    client = VCIClient(random_agent=True, rate_limit_per_minute=6)
    test_symbols = ["VNINDEX", "VIX"]
    
    print(f"\n📊 Testing batch history for {test_symbols}")
    print("-" * 40)
    
    try:
        # Test batch with 1W interval
        batch_data = client.get_batch_history(
            symbols=test_symbols,
            start="2025-07-01",
            end="2025-08-13", 
            interval="1W"
        )
        
        if batch_data:
            print(f"✅ Batch request successful!")
            print(f"📈 Results for {len(test_symbols)} symbols:")
            print("-" * 50)
            
            for symbol, df in batch_data.items():
                print(f"\n🔍 {symbol}:")
                if df is not None and len(df) > 0:
                    print(f"  📊 Data points: {len(df)}")
                    print(f"  📅 Date range: {df['time'].min()} to {df['time'].max()}")
                    
                    # Show sample data
                    print(f"  📋 Sample weekly data:")
                    display_df = df.drop('symbol', axis=1) if 'symbol' in df.columns else df
                    print(display_df.head(3).to_string(index=False, float_format='%.0f'))
                    
                    # Latest data
                    latest = df.iloc[-1]
                    print(f"  💹 Latest weekly close: {latest['close']:.0f}")
                    print(f"  📊 Latest weekly volume: {latest['volume']:,}")
                    
                    # Weekly change
                    if len(df) >= 2:
                        first_close = df['close'].iloc[0]
                        last_close = df['close'].iloc[-1]
                        weekly_change = ((last_close - first_close) / first_close) * 100
                        print(f"  📈 Period change: {weekly_change:+.2f}%")
                else:
                    print(f"  ❌ No data available")
        else:
            print("❌ Batch request failed")
            
    except Exception as e:
        print(f"💥 Error in batch test: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("✅ BATCH TEST COMPLETED")
    print("="*60)


def test_batch_1m_interval():
    """Test batch history with VNINDEX and VIX using 1M interval"""
    print("\n" + "="*60)
    print("VCI CLIENT - BATCH TEST: 1M INTERVAL")
    print("="*60)
    
    client = VCIClient(random_agent=True, rate_limit_per_minute=6)
    test_symbols = ["VNINDEX", "VIX"]
    
    print(f"\n📊 Testing batch history for {test_symbols} with 1M interval")
    print("-" * 40)
    
    try:
        # Test batch with 1M interval - need longer date range for monthly data
        batch_data = client.get_batch_history(
            symbols=test_symbols,
            start="2025-01-01",  # Longer range for monthly aggregation
            end="2025-08-13", 
            interval="1M"
        )
        
        if batch_data:
            print(f"✅ Batch request successful!")
            print(f"📈 Results for {len(test_symbols)} symbols:")
            print("-" * 50)
            
            for symbol, df in batch_data.items():
                print(f"\n🔍 {symbol}:")
                if df is not None and len(df) > 0:
                    print(f"  📊 Data points: {len(df)} monthly periods")
                    print(f"  📅 Date range: {df['time'].min()} to {df['time'].max()}")
                    
                    # Show all monthly data (should be manageable number)
                    print(f"  📋 Monthly data:")
                    display_df = df.drop('symbol', axis=1) if 'symbol' in df.columns else df
                    print(display_df.to_string(index=False, float_format='%.0f'))
                    
                    # Latest data
                    latest = df.iloc[-1]
                    print(f"  💹 Latest monthly close: {latest['close']:.0f}")
                    print(f"  📊 Latest monthly volume: {latest['volume']:,}")
                    
                    # Monthly change analysis
                    if len(df) >= 2:
                        first_close = df['close'].iloc[0]
                        last_close = df['close'].iloc[-1]
                        period_change = ((last_close - first_close) / first_close) * 100
                        print(f"  📈 YTD change: {period_change:+.2f}%")
                        
                        # Month-over-month changes
                        print(f"  📊 Month-over-month changes:")
                        for i in range(1, len(df)):
                            prev_close = df['close'].iloc[i-1]
                            curr_close = df['close'].iloc[i]
                            mom_change = ((curr_close - prev_close) / prev_close) * 100
                            month_label = df['time'].iloc[i].strftime('%Y-%m')
                            print(f"    {month_label}: {mom_change:+.2f}%")
                else:
                    print(f"  ❌ No data available")
        else:
            print("❌ Batch request failed")
            
    except Exception as e:
        print(f"💥 Error in 1M batch test: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("✅ 1M BATCH TEST COMPLETED")
    print("="*60)


def main():
    """Test VCI client: 1. Company Info, 2. Financial Info, 3. History, 4. Batch History."""
    print("\n" + "="*60)
    print("VCI CLIENT - COMPREHENSIVE TESTING")
    print("="*60)
    
    client = VCIClient(random_agent=True, rate_limit_per_minute=6)
    test_symbol = "VCI"
    
    # 1. COMPANY INFO
    print(f"\n🏢 Step 1: Company Information for {test_symbol}")
    print("-" * 40)
    try:
        company_data = client.company_info(test_symbol)
        if company_data:
            print(f"✅ Success! Company data retrieved")
            print(f"📊 Exchange: {company_data.get('TickerPriceInfo', {}).get('exchange', 'N/A')}")
            print(f"🏭 Industry: {company_data.get('CompanyListingInfo', {}).get('icbName3', 'N/A')}")
            if company_data.get('CompanyListingInfo', {}).get('issueShare') and company_data.get('TickerPriceInfo', {}).get('matchPrice'):
                market_cap_b = (company_data['CompanyListingInfo']['issueShare'] * company_data['TickerPriceInfo']['matchPrice']) / 1_000_000_000
                print(f"💰 Market Cap: {market_cap_b:,.1f}B VND")
            if company_data.get('CompanyListingInfo', {}).get('issueShare'):
                print(f"📈 Outstanding Shares: {company_data['CompanyListingInfo']['issueShare']:,.0f}")
            print(f"👥 Shareholders: {len(company_data.get('OrganizationShareHolders', []))} major")
            print(f"👔 Officers: {len(company_data.get('OrganizationManagers', []))} management")
        else:
            print("❌ Failed to retrieve company data")
    except Exception as e:
        print(f"💥 Error in company info: {e}")
    
    time.sleep(2)
    
    # 2. FINANCIAL INFO
    print(f"\n💹 Step 2: Financial Information for {test_symbol}")
    print("-" * 40)
    try:
        # Extract financial ratios from company data
        if company_data and company_data.get('TickerPriceInfo', {}).get('financialRatio'):
            ratios = company_data['TickerPriceInfo']['financialRatio']
            print(f"✅ Success! Financial data retrieved")
            
            # Key metrics
            if ratios.get('revenue'):
                print(f"💵 Revenue: {ratios['revenue']:,.0f} VND")
            if ratios.get('netProfit'):
                print(f"💰 Net Income: {ratios['netProfit']:,.0f} VND")
            if company_data.get('CompanyListingInfo', {}).get('issueShare') and company_data.get('TickerPriceInfo', {}).get('matchPrice'):
                total_assets = company_data['CompanyListingInfo']['issueShare'] * company_data['TickerPriceInfo']['matchPrice']
                print(f"🏦 Total Assets: {total_assets:,.0f} VND")
            
            # Financial ratios
            pe = ratios.get('pe', 'N/A')
            pb = ratios.get('pb', 'N/A') 
            roe = ratios.get('roe', 'N/A')
            roa = ratios.get('roa', 'N/A')
            if roe != 'N/A' and isinstance(roe, (int, float)):
                roe = f"{roe:.1%}"
            if roa != 'N/A' and isinstance(roa, (int, float)):
                roa = f"{roa:.1%}"
            print(f"📊 Ratios: PE: {pe} | PB: {pb} | ROE: {roe} | ROA: {roa}")
        else:
            print("❌ Failed to retrieve financial data")
    except Exception as e:
        print(f"💥 Error in financial info: {e}")
    
    time.sleep(2)
    
    # 3. HISTORICAL DATA
    print(f"\n📈 Step 3: Historical Data for {test_symbol}")
    print("-" * 40)
    try:
        hist_data = client.get_history(
            symbol=test_symbol,
            start="2025-08-01",
            end="2025-08-13",
            interval="1D"
        )
        if hist_data is not None:
            print(f"✅ Success! Retrieved {len(hist_data)} data points")
            print(f"📅 Range: {hist_data['time'].iloc[0]} to {hist_data['time'].iloc[-1]}")
            latest = hist_data.iloc[-1]
            print(f"💹 Latest: {latest['close']:.0f} VND (Vol: {latest['volume']:,})")
            price_range = f"{hist_data['low'].min():.0f}-{hist_data['high'].max():.0f}"
            change = ((latest['close'] - hist_data['close'].iloc[0]) / hist_data['close'].iloc[0]) * 100
            print(f"📊 Change: {change:+.2f}% | Range: {price_range}")
        else:
            print("❌ Failed to retrieve historical data")
    except Exception as e:
        print(f"💥 Error in historical data: {e}")
    
    time.sleep(2)
    
    # 4. BATCH HISTORICAL DATA
    print(f"\n📊 Step 4: Batch Historical Data (10 symbols - 2025-08-14)")
    print("-" * 40)
    try:
        test_symbols = ["AAA", "ACB", "ACV", "ANV", "BCM", "BIC", "BID", "BMP", "BSI", "BSR"]
        batch_data = client.get_batch_history(
            symbols=test_symbols,
            start="2025-08-14",
            end="2025-08-14",
            interval="1D"
        )
        
        if batch_data:
            successful_count = sum(1 for df in batch_data.values() if df is not None and len(df) > 0)
            print(f"✅ Batch request successful for {successful_count}/{len(test_symbols)} symbols!")
            print(f"📈 2025-08-14 closing prices:")
            print("-" * 40)
            
            for symbol in test_symbols:
                df = batch_data.get(symbol)
                if df is not None and len(df) > 0:
                    latest = df.iloc[-1]
                    print(f"  {symbol}: {latest['close']:.0f} VND")
                else:
                    print(f"  {symbol}: ❌ No data")
        else:
            print("❌ Batch request failed")
    except Exception as e:
        print(f"💥 Error in batch data: {e}")
    
    print(f"\n{'='*60}")
    print("✅ VCI CLIENT TESTING COMPLETED")
    print("="*60)
    
if __name__ == "__main__":
    main()
