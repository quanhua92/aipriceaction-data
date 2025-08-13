#!/usr/bin/env node

/**
 * Standalone TCBS Stock Data Client (JavaScript)
 * 
 * This client bypasses the vnai dependency by implementing direct API calls
 * to TCBS (Techcom Securities) using reverse-engineering insights from vnstock library.
 * 
 * This is a 1:1 port of tcbs.py - refer to tcbs.md guide for complete understanding.
 * Works in both Node.js and modern browsers.
 */

class TCBSClient {
  /**
   * Standalone TCBS client for fetching Vietnamese stock market data.
   * 
   * This implementation provides direct access to TCBS API without dependencies.
   * Core functionality: historical price data (OHLCV) with sophisticated request handling.
   */

  constructor(randomAgent = true, rateLimitPerMinute = 10) {
    this.baseUrl = "https://apipubaws.tcbs.com.vn";
    this.randomAgent = randomAgent;
    
    // Rate limiting
    this.rateLimitPerMinute = rateLimitPerMinute;
    this.requestTimestamps = []; // Track request timestamps for rate limiting
    
    // Browser profiles for user agent rotation
    this.userAgents = [
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15",
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    ];
    
    // Interval mapping from vnstock
    this.intervalMap = {
      '1m': '1',
      '5m': '5',
      '15m': '15',
      '30m': '30',
      '1H': '60',
      '1D': 'D',
      '1W': 'W',
      '1M': 'M'
    };
    
    // Index mapping for Vietnamese market indices
    this.indexMapping = {
      'VNINDEX': 'VNINDEX',
      'HNXINDEX': 'HNXIndex', 
      'UPCOMINDEX': 'UPCOM'
    };
    
    // Initialize session with realistic browser behavior
    this.setupSession();
  }

  /**
   * Initialize session with browser-like configuration.
   */
  setupSession() {
    // Set up default headers that mimic browser behavior
    const userAgent = this.randomAgent ? 
      this.userAgents[Math.floor(Math.random() * this.userAgents.length)] : 
      this.userAgents[0];
      
    this.defaultHeaders = {
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
      'User-Agent': userAgent,
      'Referer': 'https://www.tcbs.com.vn/',
      'Origin': 'https://www.tcbs.com.vn'
    };
  }

  /**
   * Get headers for the request, optionally rotating user agent.
   */
  getHeaders() {
    const headers = { ...this.defaultHeaders };
    
    if (this.randomAgent) {
      headers['User-Agent'] = this.userAgents[Math.floor(Math.random() * this.userAgents.length)];
    }
    
    return headers;
  }

  /**
   * Enforce rate limiting by tracking request timestamps.
   */
  async enforceRateLimit() {
    const currentTime = Date.now() / 1000; // Convert to seconds to match Python
    
    // Remove timestamps older than 1 minute
    this.requestTimestamps = this.requestTimestamps.filter(ts => currentTime - ts < 60);
    
    // If we're at the rate limit, wait until we can make another request
    if (this.requestTimestamps.length >= this.rateLimitPerMinute) {
      const oldestRequest = Math.min(...this.requestTimestamps);
      const waitTime = 60 - (currentTime - oldestRequest);
      
      if (waitTime > 0) {
        console.log(`Rate limit reached (${this.rateLimitPerMinute}/min). Waiting ${waitTime.toFixed(1)} seconds...`);
        await this.sleep((waitTime + 0.1) * 1000); // Convert to milliseconds, add small buffer
      }
    }
    
    // Record this request timestamp
    this.requestTimestamps.push(currentTime);
  }

  /**
   * Calculate exponential backoff delay.
   */
  exponentialBackoff(attempt, baseDelay = 1.0, maxDelay = 60.0) {
    const delay = baseDelay * Math.pow(2, attempt) + Math.random();
    return Math.min(delay, maxDelay);
  }

  /**
   * Sleep for specified milliseconds.
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Make HTTP request with sophisticated retry and anti-bot measures.
   * 
   * @param {string} url - API endpoint URL
   * @param {Object} params - URL parameters
   * @param {number} maxRetries - Maximum number of retry attempts
   * @returns {Promise<Object|null>} JSON response data or null if failed
   */
  async makeRequest(url, params = null, maxRetries = 5) {
    // Enforce rate limiting before making any request
    await this.enforceRateLimit();
    
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        // Apply exponential backoff on retries
        if (attempt > 0) {
          const delay = this.exponentialBackoff(attempt - 1);
          console.log(`Retry ${attempt}/${maxRetries-1} after ${delay.toFixed(1)}s delay...`);
          await this.sleep(delay * 1000); // Convert to milliseconds
        }
        
        // Get headers (with potential user agent rotation)
        const headers = this.getHeaders();
        
        // Build URL with parameters
        let requestUrl = url;
        if (params) {
          const urlParams = new URLSearchParams();
          Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== undefined) {
              urlParams.append(key, params[key]);
            }
          });
          requestUrl = `${url}?${urlParams.toString()}`;
        }
        
        const response = await fetch(requestUrl, {
          method: 'GET',
          headers,
        });
        
        if (response.status === 200) {
          try {
            const data = await response.json();
            return data;
          } catch (e) {
            console.log(`JSON decode error: ${e.message}`);
            const text = await response.text();
            console.log(`Response text: ${text.slice(0, 500)}`);
            continue;
          }
        } else if (response.status === 403) {
          console.log(`Access denied (403) on attempt ${attempt + 1}`);
          continue;
        } else if (response.status === 429) {
          console.log(`Rate limited (429) on attempt ${attempt + 1}`);
          continue;
        } else if (response.status >= 500) {
          console.log(`Server error (${response.status}) on attempt ${attempt + 1}`);
          continue;
        } else {
          console.log(`HTTP Error ${response.status} on attempt ${attempt + 1}`);
          if (response.status < 500) {
            // Client errors (4xx) - don't retry
            break;
          }
          continue;
        }
      } catch (e) {
        if (e.name === 'TypeError' && e.message.includes('fetch')) {
          console.log(`Connection error on attempt ${attempt + 1}: ${e.message}`);
          continue;
        } else {
          console.log(`Request exception on attempt ${attempt + 1}: ${e.message}`);
          continue;
        }
      }
    }
    
    return null;
  }

  /**
   * Fetch historical stock data from TCBS API.
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCI", "VNINDEX")
   * @param {string} start - Start date in "YYYY-MM-DD" format
   * @param {string} end - End date in "YYYY-MM-DD" format (optional)
   * @param {string} interval - Time interval - 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M
   * @param {number} countBack - Number of data points to return
   * @returns {Promise<Array|null>} Array of OHLCV data or null if failed
   */
  async getHistory(symbol, start, end, interval = "1D", countBack = 365) {
    if (!(interval in this.intervalMap)) {
      throw new Error(`Invalid interval: ${interval}. Valid options: ${Object.keys(this.intervalMap).join(', ')}`);
    }
    
    // Handle index symbols
    if (symbol in this.indexMapping) {
      symbol = this.indexMapping[symbol];
    }
    
    // Calculate timestamps
    const startTime = new Date(start + 'T00:00:00.000Z');
    let endTime;
    if (end) {
      endTime = new Date(end + 'T00:00:00.000Z');
    } else {
      endTime = new Date();
    }
    
    // Validate date range
    if (endTime < startTime) {
      throw new Error("End date cannot be earlier than start date.");
    }
    
    const endStamp = Math.floor(endTime.getTime() / 1000);
    const intervalValue = this.intervalMap[interval];
    
    // Determine asset type and endpoint
    let assetType, basePath;
    if (['VN30F2312', 'VN30F2403', 'VN30F2406', 'VN30F2409'].includes(symbol)) { // Futures
      assetType = "derivative";
      basePath = "futures-insight";
    } else {
      assetType = "stock";
      basePath = "stock-insight";
    }
    
    // Determine endpoint based on interval
    let endpoint;
    if (["1D", "1W", "1M"].includes(interval)) {
      endpoint = "bars-long-term";
    } else {
      endpoint = "bars";
    }
    
    // Construct URL
    const url = `${this.baseUrl}/${basePath}/v2/stock/${endpoint}`;
    
    const params = {
      'resolution': intervalValue,
      'ticker': symbol,
      'type': assetType,
      'to': endStamp,
      'countBack': countBack
    };
    
    console.log(`Fetching ${symbol} data: ${start} to ${end || 'now'} [${interval}] (count_back=${countBack})`);
    
    // Make the request
    const responseData = await this.makeRequest(url, params);
    
    if (!responseData || !responseData.data) {
      console.log("No data received from API");
      return null;
    }
    
    // Extract data from response
    const data = responseData.data;
    
    // TCBS returns data in a different format than VCI
    // Check if data is a list (TCBS format) or dict (VCI format)
    let times = [], opens = [], highs = [], lows = [], closes = [], volumes = [];
    
    if (Array.isArray(data)) {
      // TCBS format: list of objects with tradingDate, open, high, low, close, volume
      if (data.length === 0) {
        console.log("Empty data array in response");
        return null;
      }
      
      // Convert TCBS format to arrays
      for (const item of data) {
        if (item.tradingDate) {
          // Handle different date formats from TCBS
          const tradingDate = item.tradingDate;
          let dateObj;
          
          try {
            // Try with just date first
            if (tradingDate.includes('T')) {
              // Remove timezone info if present
              const datePart = tradingDate.split('T')[0];
              dateObj = new Date(datePart + 'T00:00:00.000Z');
            } else {
              dateObj = new Date(tradingDate + 'T00:00:00.000Z');
            }
          } catch (e) {
            console.log(`Date parsing error for ${tradingDate}: ${e.message}`);
            continue;
          }
          
          times.push(Math.floor(dateObj.getTime() / 1000));
          opens.push(item.open || 0);
          highs.push(item.high || 0);
          lows.push(item.low || 0);
          closes.push(item.close || 0);
          volumes.push(item.volume || 0);
        } else {
          console.log(`Unexpected item format: ${JSON.stringify(item)}`);
        }
      }
    } else {
      // VCI-style format with parallel arrays
      const requiredKeys = ['t', 'o', 'h', 'l', 'c', 'v'];
      if (!requiredKeys.every(key => key in data)) {
        console.log(`Missing required keys in response. Available: ${Object.keys(data).join(', ')}`);
        return null;
      }
      
      // Get the arrays
      times = data.t;
      opens = data.o;
      highs = data.h;
      lows = data.l;
      closes = data.c;
      volumes = data.v;
    }
    
    // Check if all arrays have the same length
    const lengths = [times.length, opens.length, highs.length, lows.length, closes.length, volumes.length];
    if (!lengths.every(length => length === lengths[0])) {
      console.log(`Inconsistent array lengths: ${lengths.join(', ')}`);
      return null;
    }
    
    if (lengths[0] === 0) {
      console.log("Empty data arrays in response");
      return null;
    }
    
    // Convert to array of OHLCV objects
    const ohlcvData = [];
    for (let i = 0; i < times.length; i++) {
      ohlcvData.push({
        time: new Date(times[i] * 1000), // Convert Unix timestamp to Date
        open: parseFloat(opens[i]),
        high: parseFloat(highs[i]),
        low: parseFloat(lows[i]),
        close: parseFloat(closes[i]),
        volume: volumes[i] !== null ? parseInt(volumes[i]) : 0
      });
    }
    
    // Filter by start date
    const startDt = new Date(start + 'T00:00:00.000Z');
    const filteredData = ohlcvData.filter(item => item.time >= startDt);
    
    // Sort by time
    filteredData.sort((a, b) => a.time.getTime() - b.time.getTime());
    
    console.log(`Successfully fetched ${filteredData.length} data points`);
    return filteredData;
  }
}

/**
 * Test the TCBS client with Vietnamese stock data.
 */
async function main() {
  const client = new TCBSClient(true, 6); // Conservative rate limit
  
  // Test symbols - use proper TCBS symbol names
  const symbols = ["VCI", "FPT", "VCB"]; // Skip VNINDEX for now, test with actual stocks
  
  for (const symbol of symbols) {
    console.log(`\n${"=".repeat(60)}`);
    console.log(`Testing ${symbol} with 1D interval...`);
    console.log(`Date range: 2025-08-01 to 2025-08-13`);
    console.log("=".repeat(60));
    
    const startTime = Date.now();
    
    try {
      const data = await client.getHistory(
        symbol,
        "2025-08-01",
        "2025-08-13", 
        "1D"
      );
      
      const endTime = Date.now();
      const duration = (endTime - startTime) / 1000;
      
      if (data !== null) {
        console.log(`\n✅ Success! Retrieved ${data.length} data points in ${duration.toFixed(1)}s`);
        console.log(`Data range: ${data[0]?.time.toISOString()} to ${data[data.length-1]?.time.toISOString()}`);
        
        // Show first few and last few rows
        if (data.length > 6) {
          console.log(`\nFirst 3 rows:`);
          for (let i = 0; i < 3; i++) {
            const item = data[i];
            console.log(`${item.time.toISOString().split('T')[0]} ${item.open.toFixed(2)} ${item.high.toFixed(2)} ${item.low.toFixed(2)} ${item.close.toFixed(2)} ${item.volume.toLocaleString()}`);
          }
          console.log(`\nLast 3 rows:`);
          for (let i = data.length - 3; i < data.length; i++) {
            const item = data[i];
            console.log(`${item.time.toISOString().split('T')[0]} ${item.open.toFixed(2)} ${item.high.toFixed(2)} ${item.low.toFixed(2)} ${item.close.toFixed(2)} ${item.volume.toLocaleString()}`);
          }
        } else {
          console.log(`\nAll data:`);
          data.forEach(item => {
            console.log(`${item.time.toISOString().split('T')[0]} ${item.open.toFixed(2)} ${item.high.toFixed(2)} ${item.low.toFixed(2)} ${item.close.toFixed(2)} ${item.volume.toLocaleString()}`);
          });
        }
        
        // Basic statistics
        const opens = data.map(d => d.open);
        const highs = data.map(d => d.high);
        const lows = data.map(d => d.low);
        const closes = data.map(d => d.close);
        const volumes = data.map(d => d.volume);
        
        console.log(`\nBasic Statistics:`);
        console.log(`Open: ${Math.min(...opens).toFixed(2)} - ${Math.max(...opens).toFixed(2)}`);
        console.log(`High: ${Math.min(...highs).toFixed(2)} - ${Math.max(...highs).toFixed(2)}`);
        console.log(`Low: ${Math.min(...lows).toFixed(2)} - ${Math.max(...lows).toFixed(2)}`);
        console.log(`Close: ${Math.min(...closes).toFixed(2)} - ${Math.max(...closes).toFixed(2)}`);
        console.log(`Volume: ${Math.min(...volumes).toLocaleString()} - ${Math.max(...volumes).toLocaleString()}`);
        
      } else {
        console.log(`\n❌ Failed to retrieve data for ${symbol}`);
      }
      
    } catch (e) {
      console.log(`\n💥 Exception occurred for ${symbol}: ${e.message}`);
    }
    
    // Add delay between different symbol requests
    if (symbol !== symbols[symbols.length - 1]) {
      console.log(`\nWaiting 3 seconds before next symbol test...`);
      await new Promise(resolve => setTimeout(resolve, 3000));
    }
  }
}

// Export for use as module (works in both Node.js and modern bundlers)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { TCBSClient };
}

// Also support ES6 imports in browsers/bundlers
if (typeof window !== 'undefined') {
  window.TCBSClient = TCBSClient;
}

// Run main function if this file is executed directly
if (typeof require !== 'undefined' && require.main === module) {
  main().catch(console.error);
}