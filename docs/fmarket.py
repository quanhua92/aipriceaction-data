#!/usr/bin/env python3
"""
Standalone FMarket Fund Data Client

This client provides access to FMarket API for Vietnamese mutual fund data
including fund listings, NAV history, and portfolio holdings.

Based on vnstock/explorer/fmarket/fund.py analysis.
"""

import requests
import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import pandas as pd


class FMarketClient:
    """
    Standalone FMarket client for fetching Vietnamese mutual fund data.
    
    This implementation provides direct access to FMarket API without dependencies.
    Core functionality: fund listings and NAV (Net Asset Value) history.
    """
    
    def __init__(self, random_agent: bool = True, rate_limit_per_minute: int = 10):
        self.base_url = "https://api.fmarket.vn/res/products"
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
        
        # Fund type mapping
        self.fund_type_mapping = {
            "BALANCED": ["BALANCED"],
            "BOND": ["BOND", "MONEY_MARKET"],
            "STOCK": ["STOCK"]
        }
        
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
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'DNT': '1',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': user_agent,
            'Referer': 'https://fmarket.vn/',
            'Origin': 'https://fmarket.vn'
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
    
    def _make_request(self, url: str, payload: Dict = None, method: str = "POST", max_retries: int = 5) -> Optional[Dict]:
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
                    response = self.session.post(url=url, json=payload, timeout=30)
                else:
                    response = self.session.get(url=url, timeout=30)
                
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
    
    def _convert_unix_to_datetime(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """Convert Unix timestamps to datetime format."""
        df_copy = df.copy()
        for col in columns:
            if col in df_copy.columns:
                df_copy[col] = pd.to_datetime(df_copy[col], unit="ms", utc=True, errors="coerce").dt.strftime("%Y-%m-%d")
                df_copy[col] = df_copy[col].where(df_copy[col].ge("1970-01-01"))
        return df_copy
    
    def get_fund_listing(self, fund_type: str = "") -> Optional[pd.DataFrame]:
        """
        Get list of all available mutual funds on FMarket.
        
        Args:
            fund_type: Type of fund to filter. Options: "", "BALANCED", "BOND", "STOCK"
                      Empty string returns all funds.
        
        Returns:
            DataFrame with fund information including short_name, full_name, nav_change, etc.
        """
        fund_type = fund_type.upper()
        fund_asset_types = self.fund_type_mapping.get(fund_type, [])
        
        if fund_type and fund_type not in {"BALANCED", "BOND", "STOCK"}:
            print(f"Warning: Unsupported fund type: '{fund_type}'. Using all funds.")
            fund_asset_types = []
        
        payload = {
            "types": ["NEW_FUND", "TRADING_FUND"],
            "issuerIds": [],
            "sortOrder": "DESC",
            "sortField": "navTo6Months",
            "page": 1,
            "pageSize": 100,
            "isIpo": False,
            "fundAssetTypes": fund_asset_types,
            "bondRemainPeriods": [],
            "searchField": "",
            "isBuyByReward": False,
            "thirdAppIds": [],
        }
        
        url = f"{self.base_url}/filter"
        
        print(f"Fetching fund listings{' for ' + fund_type if fund_type else ''}...")
        
        response_data = self._make_request(url, payload)
        
        if not response_data:
            print("No response from API")
            return None
            
        try:
            # Extract fund data
            if 'data' not in response_data or 'rows' not in response_data['data']:
                print("Unexpected response format")
                return None
                
            funds_data = response_data['data']['rows']
            total_funds = response_data['data'].get('total', len(funds_data))
            
            print(f"Total funds found: {total_funds}")
            
            if not funds_data:
                print("No fund data available")
                return None
                
            # Convert to DataFrame
            df = pd.json_normalize(funds_data)
            
            # Select relevant columns
            columns_to_keep = [
                'id', 'shortName', 'name', 'issuerName',
                'fundAssetTypeName', 'firstIssueAt',
                'productNavChange.navTo1Months', 'productNavChange.navTo3Months', 
                'productNavChange.navTo6Months', 'productNavChange.navTo12Months',
                'productNavChange.navTo36Months', 'productNavChange.updateAt'
            ]
            
            # Keep only available columns
            available_columns = [col for col in columns_to_keep if col in df.columns]
            df = df[available_columns]
            
            # Convert Unix timestamps to date format
            timestamp_columns = ["firstIssueAt", "productNavChange.updateAt"]
            df = self._convert_unix_to_datetime(df, timestamp_columns)
            
            # Rename columns to more readable format
            column_mapping = {
                'id': 'fund_id',
                'shortName': 'short_name',
                'name': 'full_name',
                'issuerName': 'issuer',
                'fundAssetTypeName': 'fund_type',
                'firstIssueAt': 'first_issue_date',
                'productNavChange.navTo1Months': 'nav_change_1m',
                'productNavChange.navTo3Months': 'nav_change_3m',
                'productNavChange.navTo6Months': 'nav_change_6m',
                'productNavChange.navTo12Months': 'nav_change_12m',
                'productNavChange.navTo36Months': 'nav_change_36m',
                'productNavChange.updateAt': 'nav_update_date'
            }
            
            # Only rename columns that exist
            existing_mapping = {k: v for k, v in column_mapping.items() if k in df.columns}
            df = df.rename(columns=existing_mapping)
            
            # Sort by 36-month NAV change (descending)
            if 'nav_change_36m' in df.columns:
                df = df.sort_values(by="nav_change_36m", ascending=False)
            
            # Reset index
            df = df.reset_index(drop=True)
            
            print(f"Successfully fetched {len(df)} fund records")
            return df
            
        except Exception as e:
            print(f"Error processing fund listing data: {e}")
            return None
    
    def get_nav_history(self, fund_symbol: str) -> Optional[pd.DataFrame]:
        """
        Get NAV (Net Asset Value) history for a specific fund.
        
        Args:
            fund_symbol: Fund short name (e.g., "SSISCA", "VCBF-BCF")
        
        Returns:
            DataFrame with columns: date, nav_per_unit
            
        Note: NAV history endpoint appears to be currently unavailable or changed.
              This method is kept for future implementation when the API is restored.
        """
        print(f"⚠️  NAV history feature temporarily unavailable")
        print(f"The FMarket API endpoint for NAV history appears to have changed or requires authentication.")
        print(f"Fund listings and basic fund information are still available via get_fund_listing().")
        print(f"Requested symbol: {fund_symbol}")
        
        # Return None to indicate feature unavailability rather than raising an error
        return None
    
    def _get_fund_id(self, fund_symbol: str) -> Optional[int]:
        """Get fund ID from fund symbol."""
        payload = {
            "searchField": fund_symbol.upper(),
            "types": ["NEW_FUND", "TRADING_FUND"],
            "pageSize": 100,
        }
        
        url = f"{self.base_url}/filter"
        response_data = self._make_request(url, payload)
        
        if not response_data:
            return None
            
        try:
            if 'data' in response_data and 'rows' in response_data['data']:
                funds = response_data['data']['rows']
                if funds:
                    # Return the first matching fund's ID
                    return funds[0].get('id')
        except Exception:
            pass
            
        return None


def main():
    """Test the FMarket client with Vietnamese mutual fund data."""
    client = FMarketClient(random_agent=True, rate_limit_per_minute=6)
    
    # Test 1: Get fund listings
    print("=" * 60)
    print("Testing Fund Listings")
    print("=" * 60)
    
    try:
        # Get all funds
        all_funds = client.get_fund_listing()
        if all_funds is not None:
            print(f"\n✅ All Funds - Retrieved {len(all_funds)} funds")
            print("\nFirst 3 funds:")
            print(all_funds.head(3).to_string(index=False))
            
            # Test specific fund type
            stock_funds = client.get_fund_listing("STOCK")
            if stock_funds is not None:
                print(f"\n✅ Stock Funds - Retrieved {len(stock_funds)} funds")
                
        time.sleep(3)  # Brief pause between tests
        
        # Test 2: Get NAV history for a specific fund
        print(f"\n{'=' * 60}")
        print("Testing NAV History")
        print("=" * 60)
        
        # Use first fund from the listing if available
        if all_funds is not None and len(all_funds) > 0:
            test_symbol = all_funds.iloc[0]['short_name']
            print(f"Testing NAV history for: {test_symbol}")
            
            nav_history = client.get_nav_history(test_symbol)
            if nav_history is not None:
                print(f"\n✅ NAV History - Retrieved {len(nav_history)} data points")
                print(f"Date range: {nav_history['date'].min()} to {nav_history['date'].max()}")
                
                print("\nFirst 3 records:")
                print(nav_history.head(3).to_string(index=False))
                
                print("\nLast 3 records:")
                print(nav_history.tail(3).to_string(index=False))
                
                # Basic statistics
                print(f"\nNAV Statistics:")
                print(f"Min NAV: {nav_history['nav_per_unit'].min():.2f}")
                print(f"Max NAV: {nav_history['nav_per_unit'].max():.2f}")
                print(f"Latest NAV: {nav_history['nav_per_unit'].iloc[-1]:.2f}")
            else:
                print(f"❌ Failed to retrieve NAV history for {test_symbol}")
        else:
            print("❌ No funds available to test NAV history")
            
    except Exception as e:
        print(f"💥 Exception during testing: {e}")


if __name__ == "__main__":
    main()