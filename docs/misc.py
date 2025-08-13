#!/usr/bin/env python3
"""
Standalone Misc Data Client

This client provides access to miscellaneous financial data including:
- Exchange rates from Vietcombank (VCB)
- Gold prices from SJC and Bao Tin Minh Chau (BTMC)

Based on vnstock/explorer/misc/ analysis.
"""

import requests
import json
import time
import random
import base64
from io import BytesIO
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import pandas as pd


class MiscClient:
    """
    Standalone Misc client for Vietnamese financial data.
    
    This implementation provides access to exchange rates and gold prices
    from Vietnamese financial institutions.
    Core functionality: VCB exchange rates and SJC/BTMC gold prices.
    """
    
    def __init__(self, random_agent: bool = True, rate_limit_per_minute: int = 10):
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
        
        # Initialize session
        self._setup_session()
        
    def _setup_session(self):
        """Initialize session with browser-like configuration."""
        user_agent = random.choice(self.user_agents) if self.random_agent else self.user_agents[0]
        
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'DNT': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': user_agent
        })
    
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
    
    def _make_request(self, url: str, method: str = "GET", data: str = None, max_retries: int = 5) -> Optional[requests.Response]:
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
                
                if method.upper() == "POST":
                    response = self.session.post(url=url, data=data, timeout=30)
                else:
                    response = self.session.get(url=url, timeout=30)
                
                if response.status_code == 200:
                    return response
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
    
    def _camel_to_snake(self, name: str) -> str:
        """Convert camelCase to snake_case."""
        result = []
        for i, c in enumerate(name):
            if c.isupper() and i > 0:
                result.append('_')
            result.append(c.lower())
        return ''.join(result)
    
    def get_vcb_exchange_rate(self, date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Get exchange rates from Vietcombank for a specific date.
        
        Args:
            date: Date in format YYYY-MM-DD. If None, current date will be used.
        
        Returns:
            DataFrame with columns: currency_code, currency_name, buy_cash, buy_transfer, sell, date
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        else:
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                raise ValueError("Error: Incorrect date format. Should be YYYY-MM-DD.")
        
        url = f"https://www.vietcombank.com.vn/api/exchangerates/exportexcel?date={date}"
        
        print(f"Fetching VCB exchange rates for {date}...")
        
        response = self._make_request(url)
        
        if not response:
            print("Failed to get response from VCB API")
            return None
            
        try:
            json_data = response.json()
            
            if "Data" not in json_data:
                print("No data field in VCB response")
                return None
                
            # Decode base64 Excel data
            excel_data = base64.b64decode(json_data["Data"])
            
            # Read Excel data
            df = pd.read_excel(BytesIO(excel_data), sheet_name='ExchangeRate')
            
            # Set proper column names
            columns = ['CurrencyCode', 'CurrencyName', 'Buy Cash', 'Buy Transfer', 'Sell']
            df.columns = columns
            
            # Remove header and footer rows
            df = df.iloc[2:-4]
            
            # Add date column
            df['date'] = date
            
            # Convert column names to snake_case
            df.columns = [self._camel_to_snake(col) for col in df.columns]
            
            # Clean and convert numeric columns
            numeric_columns = ['buy_cash', 'buy_transfer', 'sell']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
            
            # Remove rows with all NaN values
            df = df.dropna(how='all')
            
            print(f"Successfully fetched {len(df)} exchange rates")
            return df
            
        except Exception as e:
            print(f"Error processing VCB exchange rate data: {e}")
            return None
    
    def get_sjc_gold_price(self, date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Get gold prices from SJC (Saigon Jewelry Company).
        
        Args:
            date: Date in format YYYY-MM-DD. If None, current date will be used.
                  Data available from 2016-01-02 onwards.
        
        Returns:
            DataFrame with columns: name, branch, buy_price, sell_price, date
        """
        # Define minimum allowed date
        min_date = datetime(2016, 1, 2)
        
        if date is None:
            input_date = datetime.now()
        else:
            try:
                input_date = datetime.strptime(date, "%Y-%m-%d")
                if input_date < min_date:
                    raise ValueError("Date must be from 2016-01-02 onwards.")
            except ValueError as e:
                if "Date must be from" in str(e):
                    raise e
                else:
                    raise ValueError("Invalid date format. Please use YYYY-MM-DD format.")
        
        # Format date for API request (DD/MM/YYYY)
        formatted_date = input_date.strftime("%d/%m/%Y")
        
        url = "https://sjc.com.vn/GoldPrice/Services/PriceService.ashx"
        payload = f"method=GetSJCGoldPriceByDate&toDate={formatted_date}"
        
        # Set appropriate headers for SJC
        headers = self.session.headers.copy()
        headers.update({
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://sjc.com.vn/'
        })
        
        print(f"Fetching SJC gold prices for {date or 'today'}...")
        
        response = self._make_request(url, method="POST", data=payload)
        
        if not response:
            print("Failed to get response from SJC API")
            return None
            
        try:
            data = response.json()
            
            if not data.get("success"):
                print("SJC API returned unsuccessful response")
                return None
                
            gold_data = data.get("data", [])
            if not gold_data:
                print("No gold price data available")
                return None
                
            # Convert to DataFrame
            df = pd.DataFrame(gold_data)
            
            # Select and rename columns
            if all(col in df.columns for col in ["TypeName", "BranchName", "BuyValue", "SellValue"]):
                df = df[["TypeName", "BranchName", "BuyValue", "SellValue"]]
                df.columns = ["name", "branch", "buy_price", "sell_price"]
                
                # Add date column
                df["date"] = input_date.date()
                
                # Convert price columns to numeric
                df["buy_price"] = pd.to_numeric(df["buy_price"], errors='coerce')
                df["sell_price"] = pd.to_numeric(df["sell_price"], errors='coerce')
                
                # Remove rows with invalid prices
                df = df.dropna(subset=['buy_price', 'sell_price'])
                
                print(f"Successfully fetched {len(df)} gold price records")
                return df
            else:
                print("Required columns not found in SJC response")
                return None
                
        except Exception as e:
            print(f"Error processing SJC gold price data: {e}")
            return None
    
    def get_btmc_gold_price(self) -> Optional[pd.DataFrame]:
        """
        Get current gold prices from Bao Tin Minh Chau (BTMC).
        
        Returns:
            DataFrame with columns: name, karat, gold_content, buy_price, sell_price, world_price, time
        """
        url = 'http://api.btmc.vn/api/BTMCAPI/getpricebtmc?key=3kd8ub1llcg9t45hnoh8hmn7t5kc2v'
        
        print("Fetching BTMC gold prices...")
        
        response = self._make_request(url)
        
        if not response:
            print("Failed to get response from BTMC API")
            return None
            
        try:
            json_data = response.json()
            
            if 'DataList' not in json_data or 'Data' not in json_data['DataList']:
                print("Unexpected BTMC response format")
                return None
                
            data_list = json_data['DataList']['Data']
            
            if not data_list:
                print("No BTMC gold price data available")
                return None
                
            # Parse the complex data structure
            data = []
            for item in data_list:
                row_number = item.get("@row", "")
                if not row_number:
                    continue
                    
                # Build dynamic key names based on row number
                n_key = f'@n_{row_number}'
                k_key = f'@k_{row_number}'
                h_key = f'@h_{row_number}'
                pb_key = f'@pb_{row_number}'
                ps_key = f'@ps_{row_number}'
                pt_key = f'@pt_{row_number}'
                d_key = f'@d_{row_number}'
                
                data.append({
                    "name": item.get(n_key, ''),
                    "karat": item.get(k_key, ''),
                    "gold_content": item.get(h_key, ''),
                    "buy_price": item.get(pb_key, ''),
                    "sell_price": item.get(ps_key, ''),
                    "world_price": item.get(pt_key, ''),
                    "time": item.get(d_key, '')
                })
            
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Convert price columns to numeric
            price_columns = ['buy_price', 'sell_price', 'world_price']
            for col in price_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
            
            # Sort by sell price (descending)
            if 'sell_price' in df.columns:
                df = df.sort_values(by=['sell_price'], ascending=False)
                
            # Remove rows with missing essential data
            df = df.dropna(subset=['name', 'sell_price'])
            
            print(f"Successfully fetched {len(df)} BTMC gold price records")
            return df
            
        except Exception as e:
            print(f"Error processing BTMC gold price data: {e}")
            return None


def main():
    """Test the Misc client with Vietnamese financial data."""
    client = MiscClient(random_agent=True, rate_limit_per_minute=6)
    
    print("=" * 60)
    print("Testing Misc Financial Data APIs")
    print("=" * 60)
    
    # Test 1: VCB Exchange Rates
    print("\n1. Testing VCB Exchange Rates")
    print("-" * 40)
    
    try:
        vcb_rates = client.get_vcb_exchange_rate()
        if vcb_rates is not None:
            print(f"✅ VCB Exchange Rates - Retrieved {len(vcb_rates)} currency pairs")
            print("\nFirst 5 rates:")
            print(vcb_rates.head().to_string(index=False))
            
            # Show some statistics
            if 'buy_cash' in vcb_rates.columns:
                print(f"\nUSD/VND rates:")
                usd_row = vcb_rates[vcb_rates['currency_code'].str.contains('USD', na=False)]
                if not usd_row.empty:
                    print(f"Buy Cash: {usd_row.iloc[0]['buy_cash']:,.0f}")
                    print(f"Sell: {usd_row.iloc[0]['sell']:,.0f}")
        else:
            print("❌ Failed to retrieve VCB exchange rates")
            
    except Exception as e:
        print(f"💥 Exception in VCB test: {e}")
    
    # Brief pause
    time.sleep(3)
    
    # Test 2: SJC Gold Prices
    print(f"\n2. Testing SJC Gold Prices")
    print("-" * 40)
    
    try:
        sjc_gold = client.get_sjc_gold_price()
        if sjc_gold is not None:
            print(f"✅ SJC Gold Prices - Retrieved {len(sjc_gold)} records")
            print("\nFirst 5 records:")
            print(sjc_gold.head().to_string(index=False))
            
            # Show price range
            if 'sell_price' in sjc_gold.columns:
                print(f"\nPrice range:")
                print(f"Min sell price: {sjc_gold['sell_price'].min():,.0f} VND")
                print(f"Max sell price: {sjc_gold['sell_price'].max():,.0f} VND")
        else:
            print("❌ Failed to retrieve SJC gold prices")
            
    except Exception as e:
        print(f"💥 Exception in SJC test: {e}")
    
    # Brief pause
    time.sleep(3)
    
    # Test 3: BTMC Gold Prices
    print(f"\n3. Testing BTMC Gold Prices")
    print("-" * 40)
    
    try:
        btmc_gold = client.get_btmc_gold_price()
        if btmc_gold is not None:
            print(f"✅ BTMC Gold Prices - Retrieved {len(btmc_gold)} records")
            print("\nTop 5 by sell price:")
            print(btmc_gold.head().to_string(index=False))
            
            # Show statistics
            if 'sell_price' in btmc_gold.columns:
                print(f"\nPrice statistics:")
                print(f"Average sell price: {btmc_gold['sell_price'].mean():,.0f} VND")
                print(f"Highest sell price: {btmc_gold['sell_price'].max():,.0f} VND")
        else:
            print("❌ Failed to retrieve BTMC gold prices")
            
    except Exception as e:
        print(f"💥 Exception in BTMC test: {e}")
    
    print(f"\n{'=' * 60}")
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()