import os
import time
import pandas as pd
from vnstock import *
import re
import json
import argparse
from collections import defaultdict
from datetime import datetime, timedelta

# --- Configuration ---
# Load all tickers from ticker_group.json
def load_tickers_from_groups():
    try:
        with open('ticker_group.json', 'r', encoding='utf-8') as f:
            ticker_groups = json.load(f)
        tickers = []
        for group, group_tickers in ticker_groups.items():
            tickers.extend(group_tickers)
        # Add VNINDEX if not already in the list
        if "VNINDEX" not in tickers:
            tickers.insert(0, "VNINDEX")
        return sorted(list(set(tickers)))  # Remove duplicates and sort
    except FileNotFoundError:
        print("ticker_group.json not found. Using default list.")
        return ["VNINDEX", "TCB", "FPT"]

TICKERS_TO_DOWNLOAD = load_tickers_from_groups()
print(f"Loaded {len(TICKERS_TO_DOWNLOAD)} tickers from ticker_group.json")


# Define the names for your data directory.
DATA_DIR = "market_data"
MASTER_REPORT_FILENAME = "REPORT.md"
VPA_ANALYSIS_FILENAME = "VPA.md"

# Instantiate the vnstock object once
stock_reader = Vnstock().stock(symbol="SSI", source="VCI")

# --- Core Functions ---

def setup_directories():
    """
    Creates the main data directory if it doesn't already exist.
    Uses the global DATA_DIR variable.
    """
    print("Setting up base directories...")
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"  - Created directory: {DATA_DIR}")

def check_for_dividend_simple(ticker):
    """
    Simple dividend detection: Get last 30 days from API, compare with same dates from existing file.
    If prices differ significantly for matching dates from a week ago, it's likely a dividend.
    """
    file_path = os.path.join(DATA_DIR, f"{ticker}.csv")
    
    if not os.path.exists(file_path):
        return False  # No existing data to compare
    
    try:
        # Download last 30 days from API
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        print(f"   - DEBUG: Checking dividend by downloading {start_date} to {end_date}")
        api_df = stock_reader.quote.history(
            symbol=ticker,
            start=start_date,
            end=end_date,
            interval='1D'
        )
        time.sleep(2)  # Rate limiting
        
        if api_df.empty:
            print(f"   - DEBUG: No API data for dividend check")
            return False
        
        api_df['time'] = pd.to_datetime(api_df['time'])
        
        # Load existing data
        existing_df = pd.read_csv(file_path)
        existing_df['time'] = pd.to_datetime(existing_df['time'])
        
        # Get dates from a week ago (more stable than very recent dates)
        week_ago = datetime.now() - timedelta(days=7)
        two_weeks_ago = datetime.now() - timedelta(days=14)
        
        # Filter both datasets to the comparison period
        api_compare = api_df[(api_df['time'] >= two_weeks_ago) & (api_df['time'] <= week_ago)].copy()
        existing_compare = existing_df[(existing_df['time'] >= two_weeks_ago) & (existing_df['time'] <= week_ago)].copy()
        
        print(f"   - DEBUG: API compare data: {len(api_compare)} rows")
        print(f"   - DEBUG: Existing compare data: {len(existing_compare)} rows")
        
        if len(api_compare) < 3 or len(existing_compare) < 3:
            print(f"   - DEBUG: Not enough data for comparison")
            return False
        
        # Merge on matching dates
        merged = pd.merge(api_compare, existing_compare, on='time', suffixes=('_api', '_existing'))
        print(f"   - DEBUG: Merged {len(merged)} matching dates")
        
        if len(merged) < 3:
            print(f"   - DEBUG: Not enough matching dates")
            return False
        
        # Compare close prices - if they're consistently different, it's likely a dividend
        price_diffs = []
        for _, row in merged.iterrows():
            if row['close_existing'] > 0 and row['close_api'] > 0:
                ratio = row['close_existing'] / row['close_api']
                price_diffs.append(ratio)
                print(f"   - DEBUG: Date {row['time'].strftime('%Y-%m-%d')}: existing={row['close_existing']}, api={row['close_api']}, ratio={ratio:.4f}")
        
        if len(price_diffs) < 3:
            return False
        
        avg_ratio = sum(price_diffs) / len(price_diffs)
        
        # If average ratio > 1.02 (2% difference), likely dividend
        is_dividend = avg_ratio > 1.02
        
        if is_dividend:
            print(f"   - DIVIDEND DETECTED for {ticker}: avg_ratio={avg_ratio:.4f}")
        else:
            print(f"   - No dividend detected for {ticker}: avg_ratio={avg_ratio:.4f}")
        
        return is_dividend
        
    except Exception as e:
        print(f"   - ERROR checking dividend for {ticker}: {e}")
        return False

def download_full_data(ticker, start_date, end_date):
    """
    Downloads complete historical data for a ticker.
    """
    print(f"   - Downloading full history from {start_date} to {end_date}...")
    try:
        df = stock_reader.quote.history(
            symbol=ticker,
            start=start_date,
            end=end_date,
            interval='1D'
        )
        time.sleep(2)  # Rate limiting
        
        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])
            df.insert(0, 'ticker', ticker)
            df = df.sort_values(by='time')
            print(f"   - Downloaded {len(df)} records for full history")
            return df
        else:
            print(f"   - ERROR: Could not retrieve full data for {ticker}")
            return None
            
    except Exception as e:
        print(f"   - ERROR downloading full data for {ticker}: {e}")
        return None

def update_last_row_and_append_new_data(existing_df, new_df):
    """
    Update the last row of existing data and append new data, avoiding duplicates.
    This handles cases where the last row might be incomplete or needs updating.
    Returns the combined DataFrame with updated last row and new rows added.
    """
    print(f"   - DEBUG: Existing data has {len(existing_df)} rows")
    print(f"   - DEBUG: New data has {len(new_df)} rows")
    
    if existing_df.empty:
        print(f"   - DEBUG: No existing data, returning new data")
        return new_df
    
    # Find the latest date in existing data
    latest_date = existing_df['time'].max()
    print(f"   - DEBUG: Latest existing date: {latest_date.strftime('%Y-%m-%d')}")
    
    # Check if new data contains the same date as the last existing row
    same_date_rows = new_df[new_df['time'] == latest_date].copy()
    print(f"   - DEBUG: Found {len(same_date_rows)} rows with same date as last existing row")
    
    if not same_date_rows.empty:
        print(f"   - Updating last row for date {latest_date.strftime('%Y-%m-%d')}")
        # Get the old values for comparison
        old_row = existing_df[existing_df['time'] == latest_date].iloc[0]
        new_row = same_date_rows.iloc[0]
        print(f"   - DEBUG: Old close: {old_row['close']}, New close: {new_row['close']}")
        # Remove the last row from existing data
        existing_df = existing_df[existing_df['time'] != latest_date].copy()
        print(f"   - DEBUG: Removed last row, now have {len(existing_df)} existing rows")
        # The updated data for that date will be included in new_rows below
    
    # Filter new data to include dates from the latest existing date onwards
    new_rows = new_df[new_df['time'] >= latest_date].copy()
    print(f"   - DEBUG: Filtered to {len(new_rows)} new rows to add")
    
    if not new_rows.empty:
        print(f"   - Adding {len(new_rows)} rows (including any updated last row)")
        combined = pd.concat([existing_df, new_rows], ignore_index=True)
        result = combined.sort_values(by='time')
        print(f"   - DEBUG: Final result has {len(result)} rows")
        return result
    else:
        print(f"   - No new data to add")
        return existing_df

def append_new_data(existing_df, new_df):
    """
    Append new data to existing DataFrame, avoiding duplicates.
    Returns the combined DataFrame with only new rows added.
    """
    if existing_df.empty:
        return new_df
    
    # Find the latest date in existing data
    latest_date = existing_df['time'].max()
    
    # Filter new data to only include dates after the latest existing date
    new_rows = new_df[new_df['time'] > latest_date].copy()
    
    if not new_rows.empty:
        print(f"   - Adding {len(new_rows)} new rows")
        combined = pd.concat([existing_df, new_rows], ignore_index=True)
        return combined.sort_values(by='time')
    else:
        print(f"   - No new data to add")
        return existing_df

def download_stock_data(ticker, start_date, end_date):
    """
    Smart data fetching with dividend detection and last row validation.
    """
    print(f"\n-> Processing ticker: {ticker}")
    
    file_path = os.path.join(DATA_DIR, f"{ticker}.csv")
    
    if os.path.exists(file_path):
        # Step 1: Check for dividend
        if check_for_dividend_simple(ticker):
            # Dividend detected - download full history from start_date
            print(f"   - Dividend detected, downloading full history from {start_date}")
            return download_full_data(ticker, start_date, end_date)
        else:
            # Step 2: No dividend - load existing data and update last row + append new records
            print(f"   - No dividend, loading existing data from {file_path}")
            existing_df = pd.read_csv(file_path)
            existing_df['time'] = pd.to_datetime(existing_df['time'])
            
            # Get latest date from existing data
            latest_date = existing_df['time'].max()
            print(f"   - DEBUG: Existing data has {len(existing_df)} rows, latest date: {latest_date.strftime('%Y-%m-%d')}")
            
            # Download data from the last date to today to check for updates and get new data
            last_date_str = latest_date.strftime('%Y-%m-%d')
            today_str = datetime.now().strftime('%Y-%m-%d')
            
            # Download data starting from the last existing date (to update it) to today
            if last_date_str <= today_str:
                print(f"   - Fetching data from {last_date_str} to {today_str} (including last row update)")
                try:
                    new_df = stock_reader.quote.history(
                        symbol=ticker,
                        start=last_date_str,
                        end=today_str,
                        interval='1D'
                    )
                    time.sleep(2)  # Rate limiting
                    
                    if not new_df.empty:
                        new_df['time'] = pd.to_datetime(new_df['time'])
                        new_df.insert(0, 'ticker', ticker)
                        return update_last_row_and_append_new_data(existing_df, new_df)
                    else:
                        print(f"   - No new data available from API")
                        return existing_df
                except Exception as e:
                    print(f"   - ERROR downloading update data for {ticker}: {e}")
                    return existing_df
            else:
                print(f"   - Data is already up to date")
                return existing_df
    else:
        # No existing data - download full history
        print(f"   - No existing data found, downloading full history")
        return download_full_data(ticker, start_date, end_date)

# REMOVED: reformat_time_column_for_weekly_data is no longer needed
# as the 'time' column will always retain the datetime objects from vnstock.

def save_data_to_csv(df, ticker, start_date, end_date):
    """
    Saves the DataFrame to a CSV file in the main data directory.
    The 'time' column is saved as is (datetime objects).
    """
    file_name = f"{ticker}.csv"
    output_file = os.path.join(DATA_DIR, file_name)
    
    df.to_csv(output_file, index=False)
    print(f"   - Data saved to: {output_file}")
    return output_file

def parse_vpa_analysis(file_path):
    """
    Parses the VPA.md file to extract analysis for each ticker, preserving indentation.
    
    Args:
        file_path (str): The path to the VPA.md file.

    Returns:
        dict: A dictionary with tickers as keys and analysis text as values.
    """
    print(f"\n-> Reading VPA analysis from: {file_path}")
    if not os.path.exists(file_path):
        print(f"   - {os.path.basename(file_path)} not found. Skipping analysis section.")
        return {}

    analyses = {}
    current_ticker = None
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped_line = line.strip()

            # Check for a ticker header (e.g., "# VNINDEX").
            # The header line should only contain the ticker and the leading '#'.
            if stripped_line.startswith('# ') and len(stripped_line.split()) == 2:
                current_ticker = stripped_line.split()[1]
                analyses[current_ticker] = []
                continue

            # Stop capturing content at a separator line
            if stripped_line == '---':
                current_ticker = None
                continue

            # If we are inside a ticker's section, append the line
            if current_ticker:
                # Use rstrip() to remove the trailing newline but preserve leading spaces
                analyses[current_ticker].append(line.rstrip('\n'))

    # Join the collected lines for each ticker into a single block of text
    for ticker, lines in analyses.items():
        analyses[ticker] = '\n'.join(lines).strip()
        
    print(f"   - Found analysis for {len(analyses)} tickers.")
    return analyses


def get_latest_vpa_signal(analysis_text: str) -> str | None:
    """
    Parses the VPA analysis text for a single ticker to find the signal
    from the most recent entry.

    Args:
        analysis_text: The full VPA analysis content for one ticker.

    Returns:
        The normalized signal string (e.g., "Sign of Strength") or None.
    """
    # Robust splitting that handles multiple VPA entry formats:
    # "- **Ngày YYYY-MM-DD:**" or "**Ngày YYYY-MM-DD:**"
    
    # Use a single pattern that matches both formats
    entries = re.split(r'\n(?=(?:-\s*)?\*\*Ngày.*?\:\*\*)', analysis_text)

    if len(entries) <= 1:
        return None  # No valid date entries found

    # The text of the last entry is the last element of the split list.
    latest_entry_text = entries[-1]

    # Less important signals are at the top, most important are at the bottom.
    # The last match found in this dictionary will be the one that is returned.
    signals_to_check = {
        # --- Minor Signals ---
        "Test for Supply": r"Test for Supply",
        "No Demand": r"No Demand",
        "No Supply": r"No Supply",
        # --- Effort Signals ---
        "Effort to Rise": r"Effort to Rise",
        "Effort to Fall": r"Effort to Fall",
        # --- Potential Turning Points ---
        "Stopping Volume": r"Stopping Volume",
        "Buying Climax": r"Buying Climax|Topping Out Volume",
        "Selling Climax": r"Selling Climax",
        "Anomaly": r"Anomaly|sự bất thường",
        # --- Major, More Definitive Signals ---
        "Shakeout": r"Shakeout",
        "Sign of Weakness": r"Sign of Weakness|SOW",
        "Sign of Strength": r"Sign of Strength|SOS",
    }

    found_signal = None  # Initialize variable to store the latest match
    for signal_name, signal_pattern in signals_to_check.items():
        if re.search(signal_pattern, latest_entry_text, re.IGNORECASE):
            # If a match is found, update the variable.
            # This will be overwritten by any subsequent matches.
            found_signal = signal_name
    # After checking all possible signals, return the last one that was found.
    return found_signal



def generate_master_report(report_data, vpa_analyses, ticker_groups, ticker_to_group_map, start_date, end_date):
    """
    Generates an improved master REPORT.md file with a Table of Contents and deep links.
    This file is overwritten on each run.
    """
    print(f"\n-> Generating master report: {MASTER_REPORT_FILENAME}")
    signal_groups = defaultdict(list)
    for ticker, analysis_text in vpa_analyses.items():
        # Skip any tickers that might have been parsed but have no actual analysis text
        if not analysis_text or not analysis_text.strip():
            continue

        latest_signal = get_latest_vpa_signal(analysis_text)

        if latest_signal:
            signal_groups[latest_signal].append(ticker)
        else:
            # If no specific signal is found in the latest entry, group it as "Others"
            signal_groups["Others"].append(ticker)

    with open(MASTER_REPORT_FILENAME, 'w', encoding='utf-8') as f:
        # --- Main Header ---
        f.write("# AIPriceAction Market Report\n")
        f.write(f"*Report generated for data from **{start_date}** to **{end_date}**.*\n")
        f.write(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
        # --- START: Add invitation to view Trading Plan ---
        f.write("---\n\n")
        f.write("## 🎯 View the Trading Plan\n\n")
        f.write("**➡️ [Click here to view the trading plan](PLAN.md)**\n\n")
        f.write("**🎢 [Click here to view the latest market leaders](LEADER.md)**\n\n")
        f.write("---\n\n")
        # --- END: Add invitation ---

        # --- Write the VPA Signal Summary Table ---
        if signal_groups:
            # Use an explicit ID for a stable anchor link
            f.write('<h3 id="vpa-signal-summary">VPA Signal Summary (from Latest Analysis)</h3>\n\n')
            f.write("| Signal | Tickers |\n")
            f.write("|:---|:---|\n")

            # Pop "Others" from the dictionary to handle it separately at the end
            other_tickers = sorted(signal_groups.pop("Others", []))

            # Sort and write the main, recognized signals
            sorted_signals = sorted(signal_groups.keys())
            for signal in sorted_signals:
                tickers = sorted(signal_groups[signal])
                ticker_links = [f"[{t}](#{t.lower()})" for t in tickers]
                f.write(f"| {signal} | {', '.join(ticker_links)} |\n")

            # Now, write the "Others" row at the end of the table if it's not empty
            if other_tickers:
                ticker_links = [f"[{t}](#{t.lower()})" for t in other_tickers]
                f.write(f"| Others | {', '.join(ticker_links)} |\n")

            f.write("\n---\n\n")

        # --- Write the Ticker Groups Section ---
        if ticker_groups:
            f.write("## Groups\n")
            # Create a set of tickers that are actually in the report for efficient lookup
            tickers_in_report = {rd['ticker'] for rd in report_data}
            sorted_groups = sorted(ticker_groups.keys())
            for group in sorted_groups:
                tickers_in_group = sorted(ticker_groups[group])
                # Create a list of markdown links ONLY for tickers that are both in the group and in the report
                ticker_links = [f"[{t}](#{t.lower()})" for t in tickers_in_group if t in tickers_in_report]
                if ticker_links:
                    group_anchor = group.lower().replace('_', '-')
                    f.write(f'<h3 id="{group_anchor}">{group}</h3>\n\n')
                    f.write(', '.join(ticker_links) + "\n\n")
            f.write("---\n\n")

        # --- Table of Contents ---
        f.write("## Table of Contents\n")
        f.write("| Ticker | Actions |\n")
        f.write("|:-------|:--------|\n")
        for data in report_data:
            ticker_id = data['ticker'].lower() # Markdown anchors are typically lowercase
            # Add a direct link to the CSV data file
            f.write(f"| **[{data['ticker']}](#{ticker_id})** | [[Download CSV]({data['csv_path']})] |\n")
        f.write("\n---\n\n")

        # --- Summary Table ---
        f.write("## Ticker Performance Summary\n")
        f.write("| Ticker | Period High | Period Low | Latest Close | Change % | Total Volume |\n")
        f.write("|:-------|------------:|-----------:|-------------:|---------:|-------------:|\n")
        for data in report_data:
            change_color = "green" if data['change_pct'] >= 0 else "red"
            change_symbol = "📈" if data['change_pct'] >= 0 else "📉"
            f.write(
                f"| **{data['ticker']}** | {data['period_high']:,} | {data['period_low']:,} | **{data['latest_close']:,}** | "
                f"<span style='color:{change_color};'>{data['change_pct']:.2f}% {change_symbol}</span> | "
                f"{data['total_volume']:,} |\n"
            )
        
        f.write("\n---\n\n")

        # --- Detailed Section for each Ticker ---
        f.write("## Individual Ticker Analysis\n")
        for data in report_data:
            ticker_id = data['ticker'].lower()
            f.write(f"### {data['ticker']}\n\n")
            
            # --- VPA Analysis Section with Deep Link and Limited Blockquote ---
            if data['ticker'] in vpa_analyses:
                full_analysis_text = vpa_analyses[data['ticker']]

                # Check if there is any analysis text to process
                if full_analysis_text and full_analysis_text.strip():
                    # 1. Extract all dates from the full analysis to create the date range for the link
                    dates = re.findall(r'\d{4}-\d{2}-\d{2}', full_analysis_text)
                    if dates:
                        # Sort unique dates to ensure correct start and end
                        sorted_dates = sorted(list(set(dates)))
                        start_date_str = sorted_dates[0]
                        end_date_str = sorted_dates[-1]
                        vpa_link_text = f"VPA Analysis ({start_date_str} - {end_date_str})"
                    else:
                        vpa_link_text = "VPA Analysis"  # Fallback if no dates are found

                    f.write(f"#### [{vpa_link_text}](./{VPA_ANALYSIS_FILENAME}#{ticker_id})\n")

                    # 2. Split the full analysis into daily entries using a robust pattern.
                    # This handles both "- **Ngày" and "**Ngày" formats in one regex.
                    
                    # Split on pattern that matches either "- **Ngày" or "**Ngày" at line start
                    daily_entries = re.split(r'\n(?=(?:-\s*)?\*\*Ngày)', full_analysis_text)
                    
                    # Filter out empty entries and entries that don't actually contain date patterns
                    valid_entries = []
                    for entry in daily_entries:
                        entry = entry.strip()
                        if entry and re.search(r'\*\*Ngày\s+\d{4}-\d{2}-\d{2}:', entry):
                            valid_entries.append(entry)
                    
                    daily_entries = valid_entries

                    # 3. Get the last 5 daily entries for the summary
                    limited_entries = daily_entries[-5:]

                    # 4. Join the limited entries back into a single text block
                    limited_analysis_text = "\n".join(limited_entries)

                    # 5. Format the limited analysis as a blockquote for better rendering in Markdown
                    blockquote_analysis = '> ' + limited_analysis_text.replace('\n', '\n> ')
                    f.write(blockquote_analysis + "\n\n")

            
            # --- Build the Back to Top / Back to Group links ---
            # Start with the standard Back to Top link
            links = []

            # Check if the current ticker belongs to a group
            ticker_name = data['ticker']
            if ticker_name in ticker_to_group_map:
                group_name = ticker_to_group_map[ticker_name]
                group_anchor = group_name.lower().replace('_', '-')
                # Add the "Back to Group" link
                links.append(f'<a href="#{group_anchor}">↑ Back to group {group_name}</a>')

            links.append('<a href="#vpa-signal-summary">↑ Back to Top</a>')
            # Join the links with a separator and wrap them in the paragraph tag
            up_link_html = f'<p align="right">{"  |  ".join(links)}</p>\n\n'
            f.write(up_link_html)

            # --- Statistics Table ---
            f.write("#### Key Statistics\n")
            f.write("| Metric | Value |\n")
            f.write("|:---|---:|\n")
            f.write(f"| Date Range | {data['start_date']} to {data['end_date']} |\n")
            f.write(f"| **Latest Close** | **{data['latest_close']:,}** |\n")
            f.write(f"| Period Open | {data['period_open']:,} |\n")
            f.write(f"| Period High | {data['period_high']:,} |\n")
            f.write(f"| Period Low | {data['period_low']:,} |\n")
            f.write(f"| Period Change % | {data['change_pct']:.2f}% |\n")

            f.write(f"\n**[Download {data['ticker']} Data (.csv)]({data['csv_path']})**\n\n")
            f.write("---\n\n")
            
    print("   - Master report generated successfully.")




def main():
    """Main function to orchestrate the data download and report generation."""
    parser = argparse.ArgumentParser(description="AIPriceAction Data Pipeline")
    parser.add_argument('--start-date', default="2017-01-03", type=str, help="The start date for data download in 'YYYY-MM-DD' format.")
    parser.add_argument('--end-date', default=datetime.now().strftime('%Y-%m-%d'), type=str, help="The end date for data download in 'YYYY-MM-DD' format.")
    args = parser.parse_args()

    START_DATE = args.start_date
    END_DATE = args.end_date

    print("--- AIPriceAction Data Pipeline: START ---")
    print(f"--- Using data period: {START_DATE} to {END_DATE} ---")
    
    setup_directories()
    # vpa_analyses = parse_vpa_analysis(VPA_ANALYSIS_FILENAME)

    try:
        with open('ticker_group.json', 'r', encoding='utf-8') as f:
            ticker_groups = json.load(f)
        print("Loaded ticker groups from ticker_group.json")
    except FileNotFoundError:
        print("ticker_group.json not found. Skipping group section.")
        ticker_groups = {}

    ticker_to_group_map = {}
    for group, tickers in ticker_groups.items():
        for ticker in tickers:
            ticker_to_group_map[ticker] = group
    
    master_report_data = []
    # Ensure VNINDEX is first, then sort the rest
    tickers_sorted = sorted([t for t in TICKERS_TO_DOWNLOAD if t != 'VNINDEX'])
    if 'VNINDEX' in TICKERS_TO_DOWNLOAD:
        tickers_sorted = ['VNINDEX'] + tickers_sorted
    
    for ticker in tickers_sorted:
        stock_df = download_stock_data(ticker, START_DATE, END_DATE)
        
        if stock_df is not None and not stock_df.empty:
            period_open = stock_df['open'].iloc[0]
            latest_close = stock_df['close'].iloc[-1]
            change_pct = ((latest_close - period_open) / period_open) * 100 if period_open != 0 else 0
            
            csv_path = save_data_to_csv(stock_df, ticker, START_DATE, END_DATE)

            report_entry = {
                'ticker': ticker, 'records': len(stock_df),
                'start_date': stock_df['time'].min().strftime('%Y-%m-%d'),
                'end_date': stock_df['time'].max().strftime('%Y-%m-%d'),
                'period_open': period_open, 'latest_close': latest_close,
                'period_high': stock_df['high'].max(), 'period_low': stock_df['low'].min(),
                'change_pct': change_pct, 'total_volume': stock_df['volume'].sum(),
                'csv_path': csv_path,
            }
            master_report_data.append(report_entry)
            
    # if master_report_data:
    #     generate_master_report(master_report_data, vpa_analyses, ticker_groups, ticker_to_group_map, START_DATE, END_DATE)

    print("\n--- AIPriceAction Data Pipeline: FINISHED ---")

if __name__ == "__main__":
    os.environ["ACCEPT_TC"] = "tôi đồng ý"
    main()
