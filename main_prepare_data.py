#!/usr/bin/env python3
"""
Data preparation script for AIPriceAction
Creates:
1. ticker_info.json - contains ticker, company name, and market cap
2. ticker_60_days.csv - last 60 rows from all market data CSVs
3. ticker_180_days.csv - last 180 rows from all market data CSVs
"""

import json
import pandas as pd
import os
import re
from pathlib import Path

def extract_company_name(company_profile):
    """Extract company name from HTML company profile"""
    if not company_profile:
        return None
    
    # Remove HTML tags and decode entities
    clean_text = re.sub(r'<[^>]+>', '', company_profile)
    clean_text = clean_text.replace('&ocirc;', 'ô').replace('&aacute;', 'á').replace('&ecirc;', 'ê')
    clean_text = clean_text.replace('&iacute;', 'í').replace('&ugrave;', 'ù').replace('&agrave;', 'à')
    clean_text = clean_text.replace('&nbsp;', ' ').replace('&ndash;', '–').replace('&Aacute;', 'Á')
    clean_text = clean_text.replace('&acirc;', 'â').replace('&uacute;', 'ú').replace('&otilde;', 'õ')
    
    # Pattern 1: "Công ty ... (TICKER)"
    pattern1 = r'C[ôo]ng ty[^(]*\(([A-Z]+)\)'
    match = re.search(pattern1, clean_text)
    if match:
        full_match = match.group(0)
        company_name = full_match.replace(f'({match.group(1)})', '').strip()
        return company_name
    
    # Pattern 2: "Ngân hàng ... (TICKER)" for banks
    pattern2 = r'Ngân hàng[^(]*\(([A-Z]+)\)'
    match = re.search(pattern2, clean_text)
    if match:
        full_match = match.group(0)
        company_name = full_match.replace(f'({match.group(1)})', '').strip()
        return company_name
    
    # Pattern 3: Find first sentence with company/bank name
    sentences = clean_text.split('.')
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 10:
            continue
            
        # Look for company patterns
        if any(keyword in sentence for keyword in ['Công ty Cổ phần', 'Ngân hàng Thương mại Cổ phần', 'Ngân hàng']):
            # Try to extract up to the established year or other break points
            for break_point in [' được thành lập', ' thành lập', ' hoạt động', '. ']:
                if break_point in sentence:
                    company_name = sentence.split(break_point)[0].strip()
                    if len(company_name) > 10:
                        return company_name
            
            # If no break point found, return the whole sentence if reasonable length
            if len(sentence) < 200:
                return sentence
    
    return None

def create_ticker_info():
    """Create ticker_info.json with ticker, company name, and market cap"""
    print("Creating ticker_info.json...")
    
    # Load ticker groups
    with open('ticker_group.json', 'r', encoding='utf-8') as f:
        ticker_groups = json.load(f)
    
    # Get all unique tickers
    all_tickers = set()
    for tickers in ticker_groups.values():
        all_tickers.update(tickers)
    
    # Add VNINDEX
    all_tickers.add('VNINDEX')
    
    ticker_info = {}
    
    for ticker in sorted(all_tickers):
        print(f"Processing {ticker}...")
        
        company_info_file = f'company_data/{ticker}_company_info.json'
        
        if ticker == 'VNINDEX':
            # Special case for VNINDEX
            ticker_info[ticker] = {
                "company_name": "VN-Index",
                "market_cap": None
            }
        elif os.path.exists(company_info_file):
            try:
                with open(company_info_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract company name from company_profile
                company_name = extract_company_name(data.get('company_profile', ''))
                
                # Fallback to industry if no company name found
                if not company_name:
                    company_name = data.get('industry', ticker)
                
                ticker_info[ticker] = {
                    "company_name": company_name,
                    "market_cap": data.get('market_cap')
                }
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                ticker_info[ticker] = {
                    "company_name": ticker,
                    "market_cap": None
                }
        else:
            print(f"Warning: {company_info_file} not found")
            ticker_info[ticker] = {
                "company_name": ticker,
                "market_cap": None
            }
    
    # Save ticker_info.json
    with open('ticker_info.json', 'w', encoding='utf-8') as f:
        json.dump(ticker_info, f, ensure_ascii=False, indent=2)
    
    print(f"Created ticker_info.json with {len(ticker_info)} tickers")
    return ticker_info

def create_ticker_days_csv(days, filename):
    """Create ticker CSV with last N days from all market data CSVs"""
    print(f"Creating {filename}...")
    
    # Load ticker groups to get all tickers
    with open('ticker_group.json', 'r', encoding='utf-8') as f:
        ticker_groups = json.load(f)
    
    # Get all unique tickers
    all_tickers = set()
    for tickers in ticker_groups.values():
        all_tickers.update(tickers)
    
    # Add VNINDEX
    all_tickers.add('VNINDEX')
    
    combined_data = []
    
    for ticker in sorted(all_tickers):
        csv_file = f'market_data/{ticker}.csv'
        
        if os.path.exists(csv_file):
            try:
                print(f"Processing {ticker}.csv...")
                
                # Read CSV
                df = pd.read_csv(csv_file)
                
                # Get last N rows
                last_n = df.tail(days).copy()
                
                # Add to combined data
                combined_data.append(last_n)
                
            except Exception as e:
                print(f"Error processing {csv_file}: {e}")
        else:
            print(f"Warning: {csv_file} not found")
    
    if combined_data:
        # Concatenate all dataframes
        final_df = pd.concat(combined_data, ignore_index=True)
        
        # Sort by ticker and time
        final_df = final_df.sort_values(['ticker', 'time'])
        
        # Save to CSV
        final_df.to_csv(filename, index=False)
        
        print(f"Created {filename} with {len(final_df)} rows")
        print(f"Date range: {final_df['time'].min()} to {final_df['time'].max()}")
        print(f"Tickers included: {sorted(final_df['ticker'].unique())}")
    else:
        print("No data found to combine")

def create_ticker_60_days():
    """Create ticker_60_days.csv with last 60 rows from all market data CSVs"""
    create_ticker_days_csv(60, 'ticker_60_days.csv')

def create_ticker_180_days():
    """Create ticker_180_days.csv with last 180 rows from all market data CSVs"""
    create_ticker_days_csv(180, 'ticker_180_days.csv')

def main():
    """Main function to run both data preparation tasks"""
    print("Starting data preparation...")
    
    # Check if required directories exist
    if not os.path.exists('company_data'):
        print("Error: company_data directory not found")
        return
    
    if not os.path.exists('market_data'):
        print("Error: market_data directory not found")
        return
    
    if not os.path.exists('ticker_group.json'):
        print("Error: ticker_group.json not found")
        return
    
    # Create ticker_info.json
    ticker_info = create_ticker_info()
    
    print()
    
    # Create ticker_60_days.csv
    create_ticker_60_days()
    
    print()
    
    # Create ticker_180_days.csv
    create_ticker_180_days()
    
    print("\nData preparation completed!")
    print("Created files:")
    print("- ticker_info.json")
    print("- ticker_60_days.csv")
    print("- ticker_180_days.csv")

if __name__ == "__main__":
    main()