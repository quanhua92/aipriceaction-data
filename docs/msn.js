#!/usr/bin/env node

/**
 * Standalone MSN Stock Data Client (JavaScript)
 * 
 * This client provides access to MSN Finance API for international stocks,
 * currencies, cryptocurrencies, and global indices.
 * 
 * This is a 1:1 port of msn.py - refer to msn.md guide for complete understanding.
 * Works in both Node.js and modern browsers.
 */

class MSNClient {
  /**
   * Standalone MSN client for fetching international financial data.
   * 
   * This implementation provides direct access to MSN Finance API without dependencies.
   * Core functionality: historical price data for stocks, currencies, crypto, indices.
   */

  constructor(randomAgent = true, rateLimitPerMinute = 10) {
    this.baseUrl = "https://assets.msn.com/service/Finance";
    this.randomAgent = randomAgent;
    
    // Rate limiting
    this.rateLimitPerMinute = rateLimitPerMinute;
    this.requestTimestamps = [];
    
    // Browser profiles for user agent rotation
    this.userAgents = [
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15"
    ];
    
    // Supported intervals
    this.intervalMap = {
      '1D': '1D',
      '1W': '1W', 
      '1M': '1M'
    };
    
    // Currency pairs mapping (sample from vnstock)
    this.currencyIds = {
      'USDVND': 'avyufr',
      'JPYVND': 'ave8sm',
      'AUDVND': 'auxrkr',
      'CNYVND': 'av55fr',
      'EURUSD': 'av932w',
      'GBPUSD': 'avyjhw',
      'USDJPY': 'avyomw'
    };
    
    // Cryptocurrency mapping
    this.cryptoIds = {
      'BTC': 'c2111',
      'ETH': 'c2112',
      'USDT': 'c2115',
      'USDC': 'c211a',
      'BNB': 'c2113',
      'XRP': 'c2117',
      'ADA': 'c2114',
      'SOL': 'c2116',
      'DOGE': 'c2119'
    };
    
    // Global indices mapping
    this.indexIds = {
      'SPX': 'a33k6h',  // S&P 500
      'DJI': 'a6qja2',  // Dow Jones
      'IXIC': 'a3oxnm', // Nasdaq
      'FTSE': 'aopnp2', // FTSE 100
      'DAX': 'afx2kr',  // DAX
      'N225': 'a9j7bh', // Nikkei 225
      'HSI': 'ah7etc',  // Hang Seng
      'VNI': 'aqk2nm'   // VN Index
    };
    
    // Initialize session and get API key
    this.setupSession();
    this.apiKey = null;
    this.initializeApiKey();
  }

  /**
   * Initialize session with browser-like configuration.
   */
  setupSession() {
    const userAgent = this.randomAgent ? 
      this.userAgents[Math.floor(Math.random() * this.userAgents.length)] : 
      this.userAgents[0];
      
    this.defaultHeaders = {
      'Accept': 'application/json, text/plain, */*',
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept-Encoding': 'gzip, deflate, br',
      'Connection': 'keep-alive',
      'Cache-Control': 'no-cache',
      'Pragma': 'no-cache',
      'DNT': '1',
      'Sec-Fetch-Dest': 'empty',
      'Sec-Fetch-Mode': 'cors',
      'Sec-Fetch-Site': 'cross-site',
      'User-Agent': userAgent,
      'Referer': 'https://www.msn.com/',
      'Origin': 'https://www.msn.com'
    };
  }

  /**
   * Initialize API key asynchronously.
   */
  async initializeApiKey() {
    this.apiKey = await this.getApiKey('20240430', false);
  }

  /**
   * Extract API key from MSN API using vnstock method.
   */
  async getApiKey(version = '20240430', showLog = false) {
    const scope = `{
      "audienceMode":"adult",
      "browser":{"browserType":"chrome","version":"0","ismobile":"false"},
      "deviceFormFactor":"desktop","domain":"www.msn.com",
      "locale":{"content":{"language":"vi","market":"vn"},"display":{"language":"vi","market":"vn"}},
      "ocid":"hpmsn","os":"macos","platform":"web",
      "pageType":"financestockdetails"
    }`;
    
    if (version === null) {
      const today = new Date();
      today.setHours(today.getHours() - 7); // Subtract 7 hours like Python
      version = today.toISOString().slice(0, 10).replace(/-/g, '');
    }
    
    const url = `https://assets.msn.com/resolver/api/resolve/v3/config/?expType=AppConfig&expInstance=default&apptype=finance&v=${version}.130&targetScope=${scope}`;
    
    try {
      const response = await fetch(url, {
        headers: this.defaultHeaders,
        timeout: 10000
      });
      
      if (response.status !== 200) {
        if (showLog) {
          console.log(`Failed to get API key: HTTP ${response.status}`);
        }
        // Fallback API key
        return "okvJq6RrRQJaGKmj6M21Hq1CnJjCq49Ss1pdfxl0pJ9L3b0lmWIJp/lcdJaL7t8l7e9nOoC8O6KjE2h7cP9JWs";
      }
      
      const text = await response.text();
      if (!text.trim()) {
        if (showLog) {
          console.log("Empty response from MSN API");
        }
        return "okvJq6RrRQJaGKmj6M21Hq1CnJjCq49Ss1pdfxl0pJ9L3b0lmWIJp/lcdJaL7t8l7e9nOoC8O6KjE2h7cP9JWs";
      }
      
      const data = JSON.parse(text);
      
      // Extract API key from the complex nested structure
      try {
        const apikey = data.configs["shared/msn-ns/HoroscopeAnswerCardWC/default"].properties.horoscopeAnswerServiceClientSettings.apikey;
        if (showLog) {
          console.log(`Successfully extracted API key: ${apikey.slice(0, 20)}...`);
        }
        return apikey;
      } catch (e) {
        if (showLog) {
          console.log(`API key structure not found: ${e.message}`);
          console.log(`Available keys: ${typeof data === 'object' ? Object.keys(data).join(', ') : 'Not an object'}`);
        }
        // Fallback API key
        return "okvJq6RrRQJaGKmj6M21Hq1CnJjCq49Ss1pdfxl0pJ9L3b0lmWIJp/lcdJaL7t8l7e9nOoC8O6KjE2h7cP9JWs";
      }
      
    } catch (e) {
      if (showLog) {
        console.log(`Error extracting API key: ${e.message}`);
      }
      // Fallback API key
      return "okvJq6RrRQJaGKmj6M21Hq1CnJjCq49Ss1pdfxl0pJ9L3b0lmWIJp/lcdJaL7t8l7e9nOoC8O6KjE2h7cP9JWs";
    }
  }

  /**
   * Enforce rate limiting by tracking request timestamps.
   */
  async enforceRateLimit() {
    const currentTime = Date.now() / 1000;
    
    // Remove timestamps older than 1 minute
    this.requestTimestamps = this.requestTimestamps.filter(ts => currentTime - ts < 60);
    
    // If we're at the rate limit, wait until we can make another request
    if (this.requestTimestamps.length >= this.rateLimitPerMinute) {
      const oldestRequest = Math.min(...this.requestTimestamps);
      const waitTime = 60 - (currentTime - oldestRequest);
      
      if (waitTime > 0) {
        console.log(`Rate limit reached (${this.rateLimitPerMinute}/min). Waiting ${waitTime.toFixed(1)} seconds...`);
        await this.sleep((waitTime + 0.1) * 1000);
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
   * Make HTTP request with retry logic.
   */
  async makeRequest(url, params = null, maxRetries = 5) {
    await this.enforceRateLimit();
    
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        if (attempt > 0) {
          const delay = this.exponentialBackoff(attempt - 1);
          console.log(`Retry ${attempt}/${maxRetries-1} after ${delay.toFixed(1)}s delay...`);
          await this.sleep(delay * 1000);
        }
        
        if (attempt > 0 && this.randomAgent) {
          this.defaultHeaders['User-Agent'] = this.userAgents[Math.floor(Math.random() * this.userAgents.length)];
        }
        
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
          headers: this.defaultHeaders,
          timeout: 30000
        });
        
        if (response.status === 200) {
          try {
            return await response.json();
          } catch (e) {
            console.log(`JSON decode error: ${e.message}`);
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
            break;
          }
          continue;
        }
        
      } catch (e) {
        console.log(`Request exception on attempt ${attempt + 1}: ${e.message}`);
        continue;
      }
    }
    
    return null;
  }

  /**
   * Detect asset type based on symbol ID.
   */
  detectAssetType(symbolId) {
    if (Object.values(this.cryptoIds).includes(symbolId)) {
      return "crypto";
    } else if (Object.values(this.currencyIds).includes(symbolId)) {
      return "currency";
    } else if (Object.values(this.indexIds).includes(symbolId)) {
      return "index";
    } else {
      return "stock";
    }
  }

  /**
   * Resolve symbol to MSN symbol ID.
   */
  resolveSymbol(symbol) {
    const symbolUpper = symbol.toUpperCase();
    
    // Check if it's already a symbol ID (lowercase with numbers)
    if (symbol === symbol.toLowerCase() && /\d/.test(symbol)) {
      return symbol;
    }
    
    // Check currency pairs
    if (symbolUpper in this.currencyIds) {
      return this.currencyIds[symbolUpper];
    }
    
    // Check cryptocurrencies  
    if (symbolUpper in this.cryptoIds) {
      return this.cryptoIds[symbolUpper];
    }
    
    // Check indices
    if (symbolUpper in this.indexIds) {
      return this.indexIds[symbolUpper];
    }
    
    // For stocks, return as-is (user needs to provide correct MSN ID)
    return symbol.toLowerCase();
  }

  /**
   * Fetch historical data from MSN Finance API.
   * 
   * @param {string} symbol - Symbol or MSN symbol ID (e.g., "USDVND", "BTC", "SPX", or "a33k6h")
   * @param {string} start - Start date in "YYYY-MM-DD" format
   * @param {string} end - End date in "YYYY-MM-DD" format (optional)
   * @param {string} interval - Time interval - 1D, 1W, 1M only
   * @param {number} countBack - Maximum number of data points to return
   * @returns {Promise<Array|null>} Array of OHLCV data or null if failed
   */
  async getHistory(symbol, start, end, interval = "1D", countBack = 365) {
    if (!(interval in this.intervalMap)) {
      throw new Error(`Invalid interval: ${interval}. Valid options: ${Object.keys(this.intervalMap).join(', ')}`);
    }
    
    // Ensure API key is available
    if (!this.apiKey) {
      await this.initializeApiKey();
    }
    
    // Resolve symbol to MSN ID
    const symbolId = this.resolveSymbol(symbol);
    const assetType = this.detectAssetType(symbolId);
    
    // Calculate date range
    if (!end) {
      end = new Date().toISOString().split('T')[0];
    }
    
    // Determine endpoint based on asset type
    let url;
    if (assetType === "crypto") {
      url = `${this.baseUrl}/Cryptocurrency/chart`;
    } else {
      url = `${this.baseUrl}/Charts/TimeRange`;
    }
    
    // Prepare parameters (match vnstock exactly)
    const params = {
      "apikey": this.apiKey,
      'StartTime': `${start}T17:00:00.000Z`,
      'EndTime': `${end}T16:59:00.858Z`,
      'timeframe': 1,
      "ocid": "finance-utils-peregrine",
      "cm": "vi-vn",  // Changed to match vnstock
      "it": "web",
      "scn": "ANON",
      "ids": symbolId,
      "type": "All",
      "wrapodata": "false",
      "disableSymbol": "false"
    };
    
    console.log(`Fetching ${symbol} (${symbolId}) data: ${start} to ${end} [${interval}]`);
    
    // Make the request
    const responseData = await this.makeRequest(url, params);
    
    if (!responseData) {
      console.log("No response from API");
      return null;
    }
    
    try {
      // Extract series data
      let seriesData;
      if (Array.isArray(responseData) && responseData.length > 0) {
        seriesData = responseData[0].series || {};
      } else {
        console.log("Unexpected response format");
        return null;
      }
      
      if (!seriesData || Object.keys(seriesData).length === 0) {
        console.log("No series data in response");
        return null;
      }
      
      // Convert series object with arrays to array of objects
      const timeStamps = seriesData.timeStamps || [];
      const openPrices = seriesData.openPrices || [];
      const pricesHigh = seriesData.pricesHigh || [];
      const pricesLow = seriesData.pricesLow || [];
      const prices = seriesData.prices || [];
      const volumes = seriesData.volumes || [];
      
      if (timeStamps.length === 0) {
        console.log("No timestamps in series data");
        return null;
      }
      
      // Convert to array of objects
      const processedData = [];
      
      for (let i = 0; i < timeStamps.length; i++) {
        const processedItem = {};
        
        if (timeStamps[i]) processedItem.time = timeStamps[i];
        if (openPrices[i] !== undefined) processedItem.open = openPrices[i];
        if (pricesHigh[i] !== undefined) processedItem.high = pricesHigh[i];
        if (pricesLow[i] !== undefined) processedItem.low = pricesLow[i];
        if (prices[i] !== undefined) processedItem.close = prices[i];
        if (volumes[i] !== undefined) processedItem.volume = volumes[i];
        
        processedData.push(processedItem);
      }
      
      if (processedData.length === 0) {
        console.log("No processed data available");
        return null;
      }
      
      // Convert to final format
      const finalData = processedData.map(item => {
        const result = {};
        
        // Parse time column
        if (item.time) {
          let timeValue = new Date(item.time);
          // Add 7 hours to convert from UTC to Asia/Ho_Chi_Minh
          timeValue = new Date(timeValue.getTime() + 7 * 60 * 60 * 1000);
          // Remove hours info from time  
          result.time = new Date(timeValue.toISOString().split('T')[0] + 'T00:00:00.000Z');
        }
        
        // Round price columns to 2 decimal places
        const priceColumns = ["open", "high", "low", "close"];
        for (const col of priceColumns) {
          if (item[col] !== undefined) {
            result[col] = Math.round(parseFloat(item[col]) * 100) / 100;
          }
        }
        
        // Handle volume column
        if (item.volume !== undefined) {
          result.volume = parseInt(item.volume) || 0;
        }
        
        return result;
      }).filter(item => item.time); // Remove items without valid time
      
      // Replace invalid values and remove invalid rows
      const validData = finalData.filter(item => {
        // Replace -99999901.0 with null and filter out invalid rows
        if (item.open === -99999901.0) item.open = null;
        if (item.high === -99999901.0) item.high = null;
        if (item.low === -99999901.0) item.low = null;
        if (item.close === -99999901.0) item.close = null;
        
        return item.open !== null && item.high !== null && item.low !== null;
      });
      
      // Filter by date range
      const startDt = new Date(start + 'T00:00:00.000Z');
      const endDt = new Date(end + 'T23:59:59.999Z');
      
      const filteredData = validData.filter(item => 
        item.time >= startDt && item.time <= endDt
      );
      
      // Apply count_back limit
      let resultData = filteredData;
      if (countBack && resultData.length > countBack) {
        resultData = resultData.slice(-countBack);
      }
      
      // Remove volume column for currencies
      if (assetType === "currency") {
        resultData = resultData.map(item => {
          const { volume, ...rest } = item;
          return rest;
        });
      }
      
      // Sort by time
      resultData.sort((a, b) => a.time.getTime() - b.time.getTime());
      
      console.log(`Successfully fetched ${resultData.length} data points`);
      return resultData;
      
    } catch (e) {
      console.log(`Error processing response data: ${e.message}`);
      return null;
    }
  }
}

/**
 * Test the MSN client with various asset types.
 */
async function main() {
  const client = new MSNClient(true, 6);
  
  // Test different asset types
  const testCases = [
    ["SPX", "S&P 500 Index"],
    ["USDVND", "USD/VND Currency"],
    ["BTC", "Bitcoin"],
    ["EURUSD", "EUR/USD Currency"]
  ];
  
  for (const [symbol, description] of testCases) {
    console.log(`\n${"=".repeat(60)}`);
    console.log(`Testing ${symbol} (${description})`);
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
        
        // Show first few rows
        console.log(`\nFirst 3 rows:`);
        for (let i = 0; i < Math.min(3, data.length); i++) {
          const item = data[i];
          let row = `${item.time.toISOString().split('T')[0]}`;
          if (item.open !== undefined) row += ` ${item.open.toFixed(2)}`;
          if (item.high !== undefined) row += ` ${item.high.toFixed(2)}`;
          if (item.low !== undefined) row += ` ${item.low.toFixed(2)}`;
          if (item.close !== undefined) row += ` ${item.close.toFixed(2)}`;
          if (item.volume !== undefined) row += ` ${item.volume.toLocaleString()}`;
          console.log(row);
        }
        
        // Basic statistics
        console.log(`\nBasic Statistics:`);
        if (data[0]?.open !== undefined) {
          const opens = data.map(d => d.open).filter(v => v !== null);
          console.log(`Open: ${Math.min(...opens).toFixed(2)} - ${Math.max(...opens).toFixed(2)}`);
        }
        if (data[0]?.high !== undefined) {
          const highs = data.map(d => d.high).filter(v => v !== null);
          console.log(`High: ${Math.min(...highs).toFixed(2)} - ${Math.max(...highs).toFixed(2)}`);
        }
        if (data[0]?.low !== undefined) {
          const lows = data.map(d => d.low).filter(v => v !== null);
          console.log(`Low: ${Math.min(...lows).toFixed(2)} - ${Math.max(...lows).toFixed(2)}`);
        }
        if (data[0]?.close !== undefined) {
          const closes = data.map(d => d.close).filter(v => v !== null);
          console.log(`Close: ${Math.min(...closes).toFixed(2)} - ${Math.max(...closes).toFixed(2)}`);
        }
        if (data[0]?.volume !== undefined) {
          const volumes = data.map(d => d.volume).filter(v => v !== null);
          console.log(`Volume: ${Math.min(...volumes).toLocaleString()} - ${Math.max(...volumes).toLocaleString()}`);
        }
        
      } else {
        console.log(`\n❌ Failed to retrieve data for ${symbol}`);
      }
      
    } catch (e) {
      console.log(`\n💥 Exception occurred for ${symbol}: ${e.message}`);
    }
    
    // Add delay between requests
    if (symbol !== testCases[testCases.length - 1][0]) {
      console.log(`\nWaiting 3 seconds before next test...`);
      await new Promise(resolve => setTimeout(resolve, 3000));
    }
  }
}

// Export for use as module (works in both Node.js and modern bundlers)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MSNClient };
}

// Also support ES6 imports in browsers/bundlers
if (typeof window !== 'undefined') {
  window.MSNClient = MSNClient;
}

// Run main function if this file is executed directly
if (typeof require !== 'undefined' && require.main === module) {
  main().catch(console.error);
}