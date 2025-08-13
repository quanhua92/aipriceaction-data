#!/usr/bin/env node

/**
 * Standalone VCI Stock Data Client (JavaScript)
 * 
 * This client bypasses the vnai dependency by implementing sophisticated anti-bot measures
 * directly using fetch API. Based on reverse-engineering of the vnstock library
 * and VCI API research.
 * 
 * This is a 1:1 port of vci.py - refer to vci.md guide for complete understanding.
 * Works in both Node.js and modern browsers.
 */

class VCIClient {
  /**
   * Standalone VCI client for fetching Vietnamese stock market data.
   * 
   * This implementation uses sophisticated anti-bot measures including:
   * - Browser-like headers with proper referer/origin
   * - Session persistence with cookies
   * - User agent rotation
   * - Request timing and retry strategies
   */

  constructor(randomAgent = true, rateLimitPerMinute = 10) {
    this.baseUrl = "https://trading.vietcap.com.vn/api/";
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
      '1m': 'ONE_MINUTE',
      '5m': 'ONE_MINUTE', 
      '15m': 'ONE_MINUTE',
      '30m': 'ONE_MINUTE',
      '1H': 'ONE_HOUR',
      '1D': 'ONE_DAY',
      '1W': 'ONE_DAY',
      '1M': 'ONE_DAY'
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
      'User-Agent': userAgent,
      'Referer': 'https://trading.vietcap.com.vn/',
      'Origin': 'https://trading.vietcap.com.vn'
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
   * @param {Object} payload - Request payload
   * @param {number} maxRetries - Maximum number of retry attempts
   * @returns {Promise<Array|null>} JSON response data or null if failed
   */
  async makeRequest(url, payload, maxRetries = 5) {
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
        
        const response = await fetch(url, {
          method: 'POST',
          headers,
          body: JSON.stringify(payload),
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
   * Calculate Unix timestamp for the given date or current date.
   */
  calculateTimestamp(dateStr) {
    let dt;
    
    if (dateStr) {
      dt = new Date(dateStr + 'T00:00:00.000Z'); // Parse as UTC to match Python behavior
    } else {
      dt = new Date();
    }
    
    // Add one day to get the 'to' timestamp (exclusive end)
    dt.setDate(dt.getDate() + 1);
    return Math.floor(dt.getTime() / 1000); // Convert to seconds
  }

  /**
   * Calculate business days between two dates (simplified version).
   * Note: This is a simplified implementation. For production, consider using a proper business days library.
   */
  calculateBusinessDays(startDate, endDate) {
    const start = new Date(startDate + 'T00:00:00.000Z');
    const end = new Date(endDate + 'T00:00:00.000Z');
    
    let count = 0;
    const current = new Date(start);
    
    while (current <= end) {
      const dayOfWeek = current.getDay();
      // 0 = Sunday, 6 = Saturday
      if (dayOfWeek !== 0 && dayOfWeek !== 6) {
        count++;
      }
      current.setDate(current.getDate() + 1);
    }
    
    return count;
  }

  /**
   * Calculate the number of data points to request based on date range.
   */
  calculateCountBack(startDate, endDate, interval = '1D') {
    const endDateStr = endDate || new Date().toISOString().split('T')[0];
    const businessDays = this.calculateBusinessDays(startDate, endDateStr);
    
    const intervalMapped = this.intervalMap[interval] || "ONE_DAY";
    
    if (intervalMapped === "ONE_DAY") {
      return businessDays + 10; // Add buffer
    } else if (intervalMapped === "ONE_HOUR") {
      return Math.floor(businessDays * 6.5) + 10;
    } else if (intervalMapped === "ONE_MINUTE") {
      return Math.floor(businessDays * 6.5 * 60) + 10;
    } else {
      return 1000; // Default fallback
    }
  }

  /**
   * Fetch historical stock data from VCI API.
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCI", "VN30F2312")
   * @param {string} start - Start date in "YYYY-MM-DD" format
   * @param {string} end - End date in "YYYY-MM-DD" format (optional)
   * @param {string} interval - Time interval - 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M
   * @returns {Promise<Array|null>} Array of OHLCV data or null if failed
   */
  async getHistory(symbol, start, end, interval = "1D") {
    if (!(interval in this.intervalMap)) {
      throw new Error(`Invalid interval: ${interval}. Valid options: ${Object.keys(this.intervalMap).join(', ')}`);
    }
    
    // Prepare request parameters
    const endTimestamp = this.calculateTimestamp(end);
    const countBack = this.calculateCountBack(start, end, interval);
    const intervalValue = this.intervalMap[interval];
    
    const url = `${this.baseUrl}chart/OHLCChart/gap-chart`;
    const payload = {
      timeFrame: intervalValue,
      symbols: [symbol],
      to: endTimestamp,
      countBack: countBack
    };
    
    console.log(`Fetching ${symbol} data: ${start} to ${end || 'now'} [${interval}] (count_back=${countBack})`);
    
    // Make the request
    const responseData = await this.makeRequest(url, payload);
    
    if (!responseData || !Array.isArray(responseData) || responseData.length === 0) {
      console.log("No data received from API");
      return null;
    }
    
    // Extract data from response
    const dataItem = responseData[0];
    
    // Check if we have the required OHLCV arrays
    const requiredKeys = ['o', 'h', 'l', 'c', 'v', 't'];
    if (!requiredKeys.every(key => key in dataItem)) {
      console.log(`Missing required keys in response. Available: ${Object.keys(dataItem).join(', ')}`);
      return null;
    }
    
    // Get the arrays
    const opens = dataItem.o;
    const highs = dataItem.h;
    const lows = dataItem.l;
    const closes = dataItem.c;
    const volumes = dataItem.v;
    const times = dataItem.t;
    
    // Check if all arrays have the same length
    const lengths = [opens.length, highs.length, lows.length, closes.length, volumes.length, times.length];
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
 * Test the VCI client with VNINDEX data across different intervals.
 */
async function main() {
  const client = new VCIClient(true, 6); // Conservative rate limit
  
  // Test intervals
  const intervals = ["1D", "1H", "1m"];
  
  for (const interval of intervals) {
    console.log(`\n${"=".repeat(60)}`);
    console.log(`Testing VNINDEX with ${interval} interval...`);
    console.log(`Date range: 2025-08-01 to 2025-08-13`);
    console.log("=".repeat(60));
    
    const startTime = Date.now();
    
    try {
      const data = await client.getHistory(
        "VNINDEX",
        "2025-08-01",
        "2025-08-13", 
        interval
      );
      
      const endTime = Date.now();
      const duration = (endTime - startTime) / 1000;
      
      if (data !== null) {
        console.log(`\n✅ Success! Retrieved ${data.length} data points in ${duration.toFixed(1)}s`);
        console.log(`Data range: ${data[0]?.time.toISOString()} to ${data[data.length-1]?.time.toISOString()}`);
        
        // Show first few and last few rows
        if (data.length > 10) {
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
        console.log(`\n❌ Failed to retrieve ${interval} data`);
      }
      
    } catch (e) {
      console.log(`\n💥 Exception occurred for ${interval}: ${e.message}`);
    }
    
    // Add delay between different interval requests
    if (interval !== intervals[intervals.length - 1]) {
      console.log(`\nWaiting 3 seconds before next interval test...`);
      await new Promise(resolve => setTimeout(resolve, 3000));
    }
  }
}

// Export for use as module (works in both Node.js and modern bundlers)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { VCIClient };
}

// Also support ES6 imports in browsers/bundlers
if (typeof window !== 'undefined') {
  window.VCIClient = VCIClient;
}

// Run main function if this file is executed directly
if (typeof require !== 'undefined' && require.main === module) {
  main().catch(console.error);
}