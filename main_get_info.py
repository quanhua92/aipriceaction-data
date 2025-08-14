#!/usr/bin/env python3
"""
AIPriceAction Company Information Collector

This script fetches comprehensive company and financial information for Vietnamese stocks
using VCI as primary source with TCBS as fallback. Data is cached to avoid rate limits
and saved in multiple formats for different use cases.

Output files per ticker:
- {TICKER}_company_info.json: Raw company info from API
- {TICKER}_financial_info.json: Raw financial info from API  
- {TICKER}.json: Curated data optimized for AI analysis
"""

import os
import json
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import sys
import re
import html
import math
import glob

# Add docs directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'docs'))

try:
    from vci import VCIClient
    from tcbs import TCBSClient
except ImportError as e:
    print(f"Error importing client modules: {e}")
    print("Make sure vci.py and tcbs.py are in the docs/ directory")
    sys.exit(1)

# Configuration
DATA_DIR = "company_data"
CACHE_DAYS = 7  # Number of days before refreshing cached data
RATE_LIMIT_DELAY = 2.0  # Seconds between API calls
TEST_MODE_COUNT = 3  # Number of tickers to process in test mode

def load_tickers_from_groups() -> List[str]:
    """
    Load all tickers from ticker_group.json, flattening all sectors.
    
    Returns:
        List of unique ticker symbols
    """
    try:
        with open('ticker_group.json', 'r', encoding='utf-8') as f:
            ticker_groups = json.load(f)
        
        tickers = []
        for group, group_tickers in ticker_groups.items():
            tickers.extend(group_tickers)
        
        # Remove duplicates and sort
        unique_tickers = sorted(list(set(tickers)))
        print(f"Loaded {len(unique_tickers)} unique tickers from {len(ticker_groups)} groups")
        return unique_tickers
    except FileNotFoundError:
        print("ticker_group.json not found. Using default test tickers.")
        return ["VCI", "FPT", "VCB"]
    except Exception as e:
        print(f"Error loading ticker groups: {e}")
        return ["VCI", "FPT", "VCB"]

def setup_directories():
    """Create the company data directory if it doesn't exist."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created directory: {DATA_DIR}")

def get_file_paths(ticker: str) -> Dict[str, str]:
    """
    Get file paths for all output files for a given ticker.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Dictionary with file paths for different output types
    """
    return {
        'company_info': os.path.join(DATA_DIR, f"{ticker}_company_info.json"),
        'financial_info': os.path.join(DATA_DIR, f"{ticker}_financial_info.json"),
        'curated': os.path.join(DATA_DIR, f"{ticker}.json")
    }

def is_cache_valid(file_path: str, cache_days: int = CACHE_DAYS) -> bool:
    """
    Check if cached data is still valid based on created_at timestamp.
    
    Args:
        file_path: Path to the JSON file to check
        cache_days: Number of days before cache expires
        
    Returns:
        True if cache is valid, False otherwise
    """
    if not os.path.exists(file_path):
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'created_at' not in data:
            return False
        
        created_at = datetime.fromisoformat(data['created_at'])
        now = datetime.now()
        age = now - created_at
        
        is_valid = age.days < cache_days
        if is_valid:
            print(f"   - Cache valid (age: {age.days} days)")
        else:
            print(f"   - Cache expired (age: {age.days} days)")
        
        return is_valid
    except Exception as e:
        print(f"   - Error checking cache: {e}")
        return False

def clean_nan_values(obj):
    """
    Recursively clean NaN values from data structures, replacing them with None.
    
    Args:
        obj: Object to clean (dict, list, or primitive)
        
    Returns:
        Cleaned object with NaN values replaced by None
    """
    if isinstance(obj, dict):
        return {k: clean_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan_values(item) for item in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    else:
        return obj

def save_json_with_timestamp(data: Dict, file_path: str):
    """
    Save data to JSON file with created_at timestamp, ensuring valid JSON output.
    
    Args:
        data: Data to save
        file_path: Path to save the file
    """
    data['created_at'] = datetime.now().isoformat()
    
    # Clean NaN values to ensure valid JSON
    cleaned_data = clean_nan_values(data)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
    
    print(f"   - Saved: {os.path.basename(file_path)}")

def extract_company_name_from_profile(company_profile: str) -> Optional[str]:
    """
    Extract company name from HTML company profile.
    
    Args:
        company_profile: HTML content containing company information
        
    Returns:
        Extracted company name or None if not found
    """
    if not company_profile:
        return None
    
    # Remove HTML tags and get text content
    text = re.sub(r'<[^>]+>', '', company_profile)
    
    # Decode HTML entities (e.g., &ocirc; -> ô, &aacute; -> á)
    text = html.unescape(text)
    
    # Clean up whitespace characters like &nbsp;
    text = re.sub(r'&nbsp;|\xa0', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Look for patterns like "Công ty Cổ phần [Name] (TICKER)" and banks
    patterns = [
        (r'Ngân hàng ([^(]+)\s*\([^)]+\)', 'Ngân hàng {}'),           # "Ngân hàng [Type] (TICKER)"
        (r'Công ty Cổ phần ([^(]+)\s*\([^)]+\)', 'Công ty Cổ phần {}'), # "Công ty Cổ phần [Name] (AAA)"
        (r'Công ty TNHH ([^(]+)\s*\([^)]+\)', 'Công ty TNHH {}'),     # "Công ty TNHH [Name] (AAA)"
        (r'Ngân hàng ([^.]+)', 'Ngân hàng {}'),                       # "Ngân hàng [Type]"
        (r'Công ty Cổ phần ([^.]+)', 'Công ty Cổ phần {}'),          # "Công ty Cổ phần [Name]"
        (r'Công ty TNHH ([^.]+)', 'Công ty TNHH {}'),                 # "Công ty TNHH [Name]"
    ]
    
    for pattern, template in patterns:
        match = re.search(pattern, text)
        if match:
            company_name = match.group(1).strip()
            # Clean up any extra whitespace
            company_name = re.sub(r'\s+', ' ', company_name)
            return template.format(company_name)
    
    return None

def extract_curated_data(company_data: Dict, financial_data: Dict, ticker: str) -> Dict:
    """
    Extract essential data for AI analysis from raw company and financial data.
    
    Args:
        company_data: Raw company information
        financial_data: Raw financial information
        ticker: Stock ticker symbol
        
    Returns:
        Curated data dictionary with essential fields only
    """
    # Determine which API was used for processing
    company_source = company_data.get('data_source') if company_data else None
    financial_source = financial_data.get('data_source') if financial_data else None
    
    # Create processed_by summary
    if company_source == financial_source:
        processed_by = company_source
    elif company_source and financial_source:
        processed_by = f"company:{company_source}, financial:{financial_source}"
    elif company_source:
        processed_by = f"company:{company_source}"
    elif financial_source:
        processed_by = f"financial:{financial_source}"
    else:
        processed_by = "unknown"
    
    curated = {
        'symbol': ticker.upper(),
        'processed_by': processed_by,
        'data_source': company_source or financial_source,
        'created_at': datetime.now().isoformat(),
        
        # Basic Company Info
        'company_name': None,
        'exchange': None,
        'industry': None,
        'company_profile': None,
        'established_year': None,
        'employees': None,
        'website': None,
        
        # Market Data
        'current_price': None,
        'market_cap': None,
        'outstanding_shares': None,
        
        # Key Financial Metrics
        'revenue': None,
        'net_income': None,
        'total_assets': None,
        'shareholders_equity': None,
        
        # Key Ratios
        'pe_ratio': None,
        'pb_ratio': None,
        'roe': None,
        'roa': None,
        'debt_to_equity': None,
        'current_ratio': None,
        'gross_margin': None,
        'net_margin': None
    }
    
    # Extract from company data
    if company_data:
        curated['data_source'] = company_data.get('data_source', 'unknown')
        # Try direct fields first, then extract from company_profile
        curated['company_name'] = (
            company_data.get('company_name') or 
            company_data.get('short_name') or
            extract_company_name_from_profile(company_data.get('company_profile'))
        )
        curated['exchange'] = company_data.get('exchange')
        curated['industry'] = company_data.get('industry')
        curated['company_profile'] = company_data.get('company_profile')
        curated['established_year'] = company_data.get('established_year')
        curated['employees'] = company_data.get('employees')
        curated['website'] = company_data.get('website')
        curated['current_price'] = company_data.get('current_price')
        curated['market_cap'] = company_data.get('market_cap')
        curated['outstanding_shares'] = company_data.get('outstanding_shares')
    
    # Extract from financial data
    if financial_data:
        curated['revenue'] = financial_data.get('total_revenue')
        curated['net_income'] = financial_data.get('net_income')
        curated['total_assets'] = financial_data.get('total_assets')
        curated['shareholders_equity'] = financial_data.get('shareholders_equity')
        curated['pe_ratio'] = financial_data.get('pe')
        curated['pb_ratio'] = financial_data.get('pb')
        curated['roe'] = financial_data.get('roe')
        curated['roa'] = financial_data.get('roa')
        curated['debt_to_equity'] = financial_data.get('debt_to_equity')
        curated['current_ratio'] = financial_data.get('current_ratio')
        curated['gross_margin'] = financial_data.get('gross_margin')
        curated['net_margin'] = financial_data.get('net_margin')
    
    return curated

def check_rate_limit_status(client) -> bool:
    """
    Check if a client is currently rate limited.
    
    Args:
        client: VCI or TCBS client instance
        
    Returns:
        True if rate limited, False if available
    """
    current_time = time.time()
    # Remove timestamps older than 1 minute
    client.request_timestamps = [ts for ts in client.request_timestamps if current_time - ts < 60]
    
    # Check if we're at the rate limit
    return len(client.request_timestamps) >= client.rate_limit_per_minute

def fetch_ticker_data(ticker: str, vci_client: VCIClient, tcbs_client: TCBSClient, preferred_client: str = 'VCI') -> tuple:
    """
    Fetch company and financial data for a ticker using intelligent client selection.
    
    Args:
        ticker: Stock ticker symbol
        vci_client: VCI client instance
        tcbs_client: TCBS client instance
        preferred_client: Preferred client to try first ('VCI' or 'TCBS')
        
    Returns:
        Tuple of (company_data, financial_data, data_source)
    """
    print(f"\n-> Processing ticker: {ticker}")
    
    company_data = None
    financial_data = None
    data_source = None
    
    # Determine which client to try first based on rate limit status
    vci_rate_limited = check_rate_limit_status(vci_client)
    tcbs_rate_limited = check_rate_limit_status(tcbs_client)
    
    # Smart client selection logic
    if preferred_client == 'VCI' and not vci_rate_limited:
        primary_client, primary_name = vci_client, 'VCI'
        fallback_client, fallback_name = tcbs_client, 'TCBS'
    elif preferred_client == 'TCBS' and not tcbs_rate_limited:
        primary_client, primary_name = tcbs_client, 'TCBS'
        fallback_client, fallback_name = vci_client, 'VCI'
    elif not vci_rate_limited:
        primary_client, primary_name = vci_client, 'VCI'
        fallback_client, fallback_name = tcbs_client, 'TCBS'
    elif not tcbs_rate_limited:
        primary_client, primary_name = tcbs_client, 'TCBS'
        fallback_client, fallback_name = vci_client, 'VCI'
    else:
        # Both are rate limited, use preferred anyway (will wait)
        primary_client, primary_name = vci_client, 'VCI'
        fallback_client, fallback_name = tcbs_client, 'TCBS'
        print(f"   - ⚠️ Both clients rate limited, using {primary_name} (will wait)")
    
    # Try primary client first
    try:
        print(f"   - Trying {primary_name} client...")
        company_data = primary_client.company_info(ticker, mapping=True)
        if company_data:
            company_data['data_source'] = primary_name
            data_source = primary_name
            print(f"   - ✅ {primary_name} company info success")
            
            time.sleep(RATE_LIMIT_DELAY)
            
            financial_data = primary_client.financial_info(ticker, period="quarter", mapping=True)
            if financial_data:
                financial_data['data_source'] = primary_name
                print(f"   - ✅ {primary_name} financial info success")
            else:
                print(f"   - ⚠️ {primary_name} financial info failed")
        else:
            print(f"   - ❌ {primary_name} company info failed")
    except Exception as e:
        print(f"   - ❌ {primary_name} error: {e}")
        # Check if it's a rate limit error
        if "rate limit" in str(e).lower() or "429" in str(e):
            print(f"   - 🔄 {primary_name} rate limited, switching to {fallback_name}")
    
    # Fallback to secondary client if primary failed
    if not company_data or not financial_data:
        try:
            print(f"   - Trying {fallback_name} fallback...")
            time.sleep(RATE_LIMIT_DELAY)
            
            if not company_data:
                company_data = fallback_client.company_info(ticker, mapping=True)
                if company_data:
                    company_data['data_source'] = fallback_name
                    data_source = fallback_name
                    print(f"   - ✅ {fallback_name} company info success")
                else:
                    print(f"   - ❌ {fallback_name} company info failed")
            
            if not financial_data:
                time.sleep(RATE_LIMIT_DELAY)
                financial_data = fallback_client.financial_info(ticker, period="quarter", mapping=True)
                if financial_data:
                    financial_data['data_source'] = fallback_name
                    print(f"   - ✅ {fallback_name} financial info success")
                else:
                    print(f"   - ❌ {fallback_name} financial info failed")
        except Exception as e:
            print(f"   - ❌ {fallback_name} error: {e}")
    
    return company_data, financial_data, data_source

def process_ticker(ticker: str, vci_client: VCIClient, tcbs_client: TCBSClient, preferred_client: str, force_refresh: bool = False):
    """
    Process a single ticker: check cache, fetch data if needed, save results.
    
    Args:
        ticker: Stock ticker symbol
        vci_client: VCI client instance
        tcbs_client: TCBS client instance
        preferred_client: Preferred client to try first ('VCI' or 'TCBS')
        force_refresh: Whether to ignore cache and force refresh
    """
    file_paths = get_file_paths(ticker)
    
    # Check if we need to fetch new data
    needs_refresh = force_refresh or not all(
        is_cache_valid(file_paths[key]) for key in ['company_info', 'financial_info', 'curated']
    )
    
    if not needs_refresh:
        print(f"💾 Cache hit - all files valid for {ticker}")
        return "Skipped"  # Indicate this was a cache hit
    
    # Fetch data
    company_data, financial_data, data_source = fetch_ticker_data(ticker, vci_client, tcbs_client, preferred_client)
    
    # Save results if we got any data
    if company_data or financial_data:
        if company_data:
            save_json_with_timestamp(company_data, file_paths['company_info'])
        
        if financial_data:
            save_json_with_timestamp(financial_data, file_paths['financial_info'])
        
        # Create curated data
        curated_data = extract_curated_data(company_data, financial_data, ticker)
        save_json_with_timestamp(curated_data, file_paths['curated'])
        
        print(f"   - ✅ Completed {ticker} (processed by: {curated_data['processed_by']})")
        
        # Return the data source as the new preferred client for the next ticker
        return data_source or preferred_client
    else:
        print(f"   - ❌ No data available for {ticker}")
        return preferred_client

def rewrite_json_files():
    """
    Rewrite all JSON files in the company_data directory to fix NaN values and ensure valid JSON.
    """
    print("🔧 Rewriting JSON files to fix NaN values...")
    setup_directories()
    
    # Find all JSON files in the data directory
    json_pattern = os.path.join(DATA_DIR, "*.json")
    json_files = glob.glob(json_pattern)
    
    if not json_files:
        print(f"   - No JSON files found in {DATA_DIR}/")
        return
    
    print(f"   - Found {len(json_files)} JSON files to process")
    
    processed = 0
    errors = 0
    
    for file_path in json_files:
        try:
            print(f"   - Processing: {os.path.basename(file_path)}")
            
            # Read the existing file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Clean NaN values
            cleaned_data = clean_nan_values(data)
            
            # Write back with proper JSON formatting
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
            
            processed += 1
            
        except Exception as e:
            print(f"   - ❌ Error processing {os.path.basename(file_path)}: {e}")
            errors += 1
    
    print(f"\n✅ JSON rewrite completed:")
    print(f"   - Processed: {processed} files")
    print(f"   - Errors: {errors} files")
    if errors == 0:
        print("   - All files now contain valid JSON without NaN values")

def main():
    """Main function to orchestrate the data collection."""
    parser = argparse.ArgumentParser(description="AIPriceAction Company Information Collector")
    parser.add_argument('--test', action='store_true', help=f"Test mode: process only first {TEST_MODE_COUNT} tickers")
    parser.add_argument('--force', action='store_true', help="Force refresh all data (ignore cache)")
    parser.add_argument('--tickers', nargs='+', help="Process specific tickers only")
    parser.add_argument('--rewrite-json', action='store_true', help="Rewrite all existing JSON files to fix NaN values and ensure valid JSON")
    args = parser.parse_args()
    
    # Handle --rewrite-json option
    if getattr(args, 'rewrite_json', False):
        rewrite_json_files()
        return
    
    start_time = time.time()
    print("🚀 AIPriceAction Company Information Collector: START")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 Cache expires after: {CACHE_DAYS} days")
    print(f"⏱️  Rate limit delay: {RATE_LIMIT_DELAY} seconds")
    print(f"🗂️  Force refresh: {'YES' if args.force else 'NO'}")
    
    setup_directories()
    
    # Load tickers
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
        print(f"🎯 Processing specified tickers: {tickers}")
    else:
        print("📋 Loading tickers from ticker_group.json...")
        tickers = load_tickers_from_groups()
        print(f"📊 Found {len(tickers)} total tickers")
        if args.test:
            tickers = tickers[:TEST_MODE_COUNT]
            print(f"🧪 TEST MODE: Processing first {len(tickers)} tickers: {tickers}")
    
    # Initialize clients
    print("\n🔗 Initializing API clients...")
    vci_client = VCIClient(random_agent=True, rate_limit_per_minute=60)
    tcbs_client = TCBSClient(random_agent=True, rate_limit_per_minute=60)
    print("   ✅ VCI client: 60 calls/minute")
    print("   ✅ TCBS client: 60 calls/minute")
    
    # Process each ticker with dynamic client switching
    successful = 0
    failed = 0
    skipped = 0
    preferred_client = 'VCI'  # Start with VCI as preferred
    
    # Track client usage for stats
    client_stats = {'VCI': 0, 'TCBS': 0, 'Mixed': 0, 'Skipped': 0}
    
    print(f"\n🔄 Starting processing of {len(tickers)} tickers...")
    
    for i, ticker in enumerate(tickers, 1):
        ticker_start = time.time()
        print(f"\n{'='*20} [{i:3d}/{len(tickers)}] {ticker} {'='*20}")
        print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"🎯 Preferred client: {preferred_client}")
        
        # Show rate limit status
        vci_requests = len(vci_client.request_timestamps)
        tcbs_requests = len(tcbs_client.request_timestamps)
        print(f"📡 Rate limits: VCI={vci_requests}/60, TCBS={tcbs_requests}/60")
        
        cache_hit = False
        try:
            new_preferred = process_ticker(ticker, vci_client, tcbs_client, preferred_client, args.force)
            if new_preferred:
                # Update stats based on result
                if new_preferred == "Skipped":
                    client_stats['Skipped'] += 1
                    skipped += 1
                    cache_hit = True  # No API call made, no need to sleep
                elif new_preferred in ['VCI', 'TCBS']:
                    client_stats[new_preferred] += 1
                    # Update preferred client for next iteration
                    if new_preferred != preferred_client:
                        print(f"   🔄 Switching preferred client: {preferred_client} → {new_preferred}")
                    preferred_client = new_preferred
                    successful += 1
                elif 'company:' in new_preferred:
                    client_stats['Mixed'] += 1
                    # For mixed cases, keep the current preferred client
                    successful += 1
                else:
                    successful += 1
            else:
                failed += 1
        except Exception as e:
            print(f"   ❌ Error processing {ticker}: {e}")
            failed += 1
        
        # Show ticker completion time
        ticker_time = time.time() - ticker_start
        print(f"⏱️  Ticker {ticker} completed in {ticker_time:.1f}s")
        
        # Progress update every 10 tickers or for the last ticker
        if i % 10 == 0 or i == len(tickers):
            elapsed = time.time() - start_time
            progress = (i / len(tickers)) * 100
            if i < len(tickers):
                avg_time_per_ticker = elapsed / i
                estimated_total = avg_time_per_ticker * len(tickers)
                remaining = estimated_total - elapsed
                print(f"\n📈 Progress: {progress:.1f}% ({i}/{len(tickers)})")
                print(f"⏱️  Elapsed: {elapsed/60:.1f}min, ETA: {remaining/60:.1f}min")
                print(f"📊 Status: ✅{successful} ❌{failed} 💾{skipped}")
        
        # Rate limiting between tickers - only if we made API calls (no cache hit)
        if i < len(tickers) and not cache_hit:
            print(f"⏸️  Rate limiting delay ({RATE_LIMIT_DELAY}s)...")
            time.sleep(RATE_LIMIT_DELAY)
    
    # Final summary
    total_time = time.time() - start_time
    print("\n" + "="*70)
    print("🎉 PROCESSING COMPLETE!")
    print("="*70)
    print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Total time: {total_time/60:.1f} minutes ({total_time:.1f} seconds)")
    print(f"📊 Results: ✅{successful} successful, ❌{failed} failed, 💾{skipped} cached")
    print(f"\n🔵 API Usage Statistics:")
    print(f"   VCI only: {client_stats['VCI']} tickers")
    print(f"   TCBS only: {client_stats['TCBS']} tickers") 
    print(f"   Mixed APIs: {client_stats['Mixed']} tickers")
    print(f"   Cache hits: {client_stats['Skipped']} tickers")
    
    # Show file count
    try:
        files = os.listdir(DATA_DIR)
        json_files = [f for f in files if f.endswith('.json')]
        unique_tickers = set([f.split('_')[0].split('.')[0] for f in json_files])
        print(f"\n📁 Files created:")
        print(f"   Total JSON files: {len(json_files)}")
        print(f"   Unique tickers: {len(unique_tickers)}")
        print(f"   Data directory: {DATA_DIR}/")
    except Exception as e:
        print(f"   Error reading directory: {e}")
    
    print("\n🏁 AIPriceAction Company Information Collector: FINISHED")

if __name__ == "__main__":
    main()