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

  // Normalized field mapping for cross-platform consistency
  static FIELD_MAPPING = {
    // Company Overview
    symbol: 'symbol',
    exchange: 'exchange',
    industry: 'industry',
    company_type: 'company_type',
    established_year: 'established_year',
    employees: 'employees',
    market_cap: 'market_cap',
    current_price: 'current_price',
    outstanding_shares: 'outstanding_shares',
    company_profile: 'company_profile',
    website: 'website',
    
    // TCBS-specific mappings
    no_employees: 'employees',
    outstanding_share: 'outstanding_shares',
    short_name: 'company_name',
    
    // Shareholders (TCBS format)
    share_holder: 'shareholder_name',
    share_own_percent: 'shareholder_percent',
    
    // Officers (TCBS format)
    officer_name: 'officer_name',
    officer_position: 'officer_position',
    officer_own_percent: 'officer_percent',
    
    // Financial Statements (normalized keys)
    total_assets: 'total_assets',
    total_liabilities: 'total_liabilities',
    shareholders_equity: 'shareholders_equity',
    total_revenue: 'total_revenue',
    gross_profit: 'gross_profit',
    operating_profit: 'operating_profit',
    net_income: 'net_income',
    cash_from_operations: 'cash_from_operations',
    cash_from_investing: 'cash_from_investing',
    cash_from_financing: 'cash_from_financing',
    free_cash_flow: 'free_cash_flow'
  };

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

  /**
   * Fetch historical stock data for multiple symbols using sequential requests.
   * 
   * Note: Unlike VCI, TCBS doesn't support true batch requests, so this method
   * makes efficient sequential individual requests for each symbol.
   * 
   * @param {Array<string>} symbols - Array of stock symbols (e.g., ["VCI", "AAA", "ACB"])
   * @param {string} start - Start date in "YYYY-MM-DD" format
   * @param {string} end - End date in "YYYY-MM-DD" format (optional)
   * @param {string} interval - Time interval - 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M
   * @param {number} countBack - Number of data points to return
   * @returns {Promise<Object|null>} Object mapping symbol -> Array of OHLCV data
   */
  async getBatchHistory(symbols, start, end, interval = "1D", countBack = 365) {
    if (!(interval in this.intervalMap)) {
      throw new Error(`Invalid interval: ${interval}. Valid options: ${Object.keys(this.intervalMap).join(', ')}`);
    }
    
    if (!symbols || symbols.length === 0) {
      throw new Error("Symbols array cannot be empty");
    }
    
    console.log(`Fetching batch data for ${symbols.length} symbols: ${symbols.join(', ')}`);
    console.log(`Date range: ${start} to ${end || 'now'} [${interval}] (count_back=${countBack})`);
    
    const results = {};
    let successfulCount = 0;
    
    // Process each symbol sequentially with rate limiting
    for (let i = 0; i < symbols.length; i++) {
      const symbol = symbols[i];
      
      try {
        console.log(`Processing ${symbol} (${i+1}/${symbols.length})...`);
        
        // Add small delay between requests to respect rate limits
        if (i > 0) {
          await this.sleep(500); // 0.5s delay
        }
        
        // Fetch individual symbol data
        const data = await this.getHistory(symbol, start, end, interval, countBack);
        
        if (data && data.length > 0) {
          // Add symbol property for identification
          data.forEach(item => item.symbol = symbol);
          results[symbol] = data;
          successfulCount++;
          console.log(`✅ ${symbol}: ${data.length} data points`);
        } else {
          results[symbol] = null;
          console.log(`❌ ${symbol}: No data`);
        }
        
      } catch (error) {
        results[symbol] = null;
        console.log(`❌ ${symbol}: Error - ${error.message}`);
      }
    }
    
    console.log(`Successfully fetched data for ${successfulCount}/${symbols.length} symbols`);
    
    return results;
  }

  /**
   * Convert camelCase to snake_case.
   * @param {string} name - The camelCase string to convert
   * @returns {string} The snake_case string
   */
  camelToSnake(name) {
    return name.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase();
  }

  /**
   * Get company overview data from TCBS API.
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCI", "FPT")
   * @returns {Promise<Object|null>} Company overview data or null if failed
   */
  async overview(symbol) {
    // Use TCBS analysis API
    const url = `${this.baseUrl}/tcanalysis/v1/ticker/${symbol.toUpperCase()}/overview`;
    
    console.log(`Fetching company overview for ${symbol}...`);
    
    const responseData = await this.makeRequest(url);
    
    if (!responseData) {
      console.log("No company overview data received from API");
      return null;
    }
    
    // Convert to structured data
    const overview = { ...responseData };
    
    // Select relevant columns (same as vnstock)
    const relevantColumns = [
      'ticker', 'exchange', 'industry', 'companyType',
      'noShareholders', 'foreignPercent', 'outstandingShare', 'issueShare',
      'establishedYear', 'noEmployees',
      'stockRating', 'deltaInWeek', 'deltaInMonth', 'deltaInYear',
      'shortName', 'website', 'industryID', 'industryIDv2'
    ];
    
    // Filter to relevant columns only
    const filteredOverview = {};
    relevantColumns.forEach(col => {
      if (overview.hasOwnProperty(col)) {
        // Convert column names to snake_case
        const snakeCol = this.camelToSnake(col);
        filteredOverview[snakeCol] = overview[col];
      }
    });
    
    // Rename specific columns
    if (filteredOverview.industry_i_dv2) {
      filteredOverview.industry_id_v2 = filteredOverview.industry_i_dv2;
      delete filteredOverview.industry_i_dv2;
    }
    if (filteredOverview.ticker) {
      filteredOverview.symbol = filteredOverview.ticker;
      delete filteredOverview.ticker;
    }
    
    console.log(`Successfully fetched company overview for ${symbol}`);
    return filteredOverview;
  }

  /**
   * Get detailed company profile from TCBS API.
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCI", "FPT")
   * @returns {Promise<Object|null>} Company profile data or null if failed
   */
  async profile(symbol) {
    const url = `${this.baseUrl}/tcanalysis/v1/company/${symbol.toUpperCase()}/overview`;
    
    console.log(`Fetching company profile for ${symbol}...`);
    
    const responseData = await this.makeRequest(url);
    
    if (!responseData) {
      console.log("No company profile data received from API");
      return null;
    }
    
    // Convert to structured data
    const profile = { ...responseData };
    
    // Clean HTML content in text fields (same as vnstock)
    Object.keys(profile).forEach(key => {
      if (typeof profile[key] === 'string') {
        // Simple HTML cleaning - remove tags and normalize whitespace
        profile[key] = profile[key]
          .replace(/<[^>]*>/g, '') // Remove HTML tags
          .replace(/\s+/g, ' ') // Normalize whitespace
          .trim();
      }
    });
    
    // Add symbol column
    profile.symbol = symbol.toUpperCase();
    
    // Drop unnecessary columns
    delete profile.id;
    delete profile.ticker;
    
    // Convert column names to snake_case
    const snakeCaseProfile = {};
    Object.keys(profile).forEach(key => {
      const snakeKey = this.camelToSnake(key);
      snakeCaseProfile[snakeKey] = profile[key];
    });
    
    // Reorder to put symbol first
    const orderedProfile = { symbol: snakeCaseProfile.symbol };
    Object.keys(snakeCaseProfile).forEach(key => {
      if (key !== 'symbol') {
        orderedProfile[key] = snakeCaseProfile[key];
      }
    });
    
    console.log(`Successfully fetched company profile for ${symbol}`);
    return orderedProfile;
  }

  /**
   * Get major shareholders information from TCBS API.
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCI", "FPT")
   * @returns {Promise<Array|null>} Array of shareholders data or null if failed
   */
  async shareholders(symbol) {
    const url = `${this.baseUrl}/tcanalysis/v1/company/${symbol.toUpperCase()}/large-share-holders`;
    
    console.log(`Fetching shareholders for ${symbol}...`);
    
    const responseData = await this.makeRequest(url);
    
    if (!responseData || !responseData.listShareHolder) {
      console.log("No shareholders data received from API");
      return null;
    }
    
    const shareholders = responseData.listShareHolder;
    
    if (!Array.isArray(shareholders) || shareholders.length === 0) {
      console.log("No shareholders data available");
      return null;
    }
    
    // Process shareholders data
    const processedShareholders = shareholders.map(shareholder => {
      const processed = { ...shareholder };
      
      // Rename columns for clarity (same as vnstock)
      if (processed.name) {
        processed.shareHolder = processed.name;
        delete processed.name;
      }
      if (processed.ownPercent !== undefined) {
        processed.shareOwnPercent = processed.ownPercent;
        delete processed.ownPercent;
      }
      
      // Drop unnecessary columns
      delete processed.no;
      delete processed.ticker;
      
      // Convert column names to snake_case
      const snakeCaseShareholder = {};
      Object.keys(processed).forEach(key => {
        const snakeKey = this.camelToSnake(key);
        snakeCaseShareholder[snakeKey] = processed[key];
      });
      
      return snakeCaseShareholder;
    });
    
    console.log(`Successfully fetched ${processedShareholders.length} shareholders for ${symbol}`);
    return processedShareholders;
  }

  /**
   * Get key officers information from TCBS API.
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCI", "FPT")
   * @returns {Promise<Array|null>} Array of officers data or null if failed
   */
  async officers(symbol) {
    const url = `${this.baseUrl}/tcanalysis/v1/company/${symbol.toUpperCase()}/key-officers`;
    
    console.log(`Fetching officers for ${symbol}...`);
    
    const responseData = await this.makeRequest(url);
    
    if (!responseData || !responseData.listKeyOfficer) {
      console.log("No officers data received from API");
      return null;
    }
    
    const officers = responseData.listKeyOfficer;
    
    if (!Array.isArray(officers) || officers.length === 0) {
      console.log("No officers data available");
      return null;
    }
    
    // Process officers data
    const processedOfficers = officers.map(officer => {
      const processed = { ...officer };
      
      // Rename columns for clarity (same as vnstock)
      if (processed.name) {
        processed.officerName = processed.name;
        delete processed.name;
      }
      if (processed.position) {
        processed.officerPosition = processed.position;
        delete processed.position;
      }
      if (processed.ownPercent !== undefined) {
        processed.officerOwnPercent = processed.ownPercent;
        delete processed.ownPercent;
      }
      
      // Drop unnecessary columns
      delete processed.no;
      delete processed.ticker;
      
      // Convert column names to snake_case
      const snakeCaseOfficer = {};
      Object.keys(processed).forEach(key => {
        const snakeKey = this.camelToSnake(key);
        snakeCaseOfficer[snakeKey] = processed[key];
      });
      
      return snakeCaseOfficer;
    });
    
    // Sort by ownership percentage (same as vnstock)
    processedOfficers.sort((a, b) => {
      const aPercent = a.officer_own_percent || 0;
      const bPercent = b.officer_own_percent || 0;
      return bPercent - aPercent;
    });
    
    console.log(`Successfully fetched ${processedOfficers.length} officers for ${symbol}`);
    return processedOfficers;
  }

  /**
   * Get current trading price for market cap calculation.
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCI", "FPT")
   * @returns {Promise<number|null>} Current price or null if failed
   */
  async getCurrentPrice(symbol) {
    const url = `${this.baseUrl}/stock-insight/v1/stock/second-tc-price`;
    
    const params = { "tickers": symbol.toUpperCase() };
    
    const responseData = await this.makeRequest(url, params);
    
    if (!responseData || !responseData.data) {
      return null;
    }
    
    const data = responseData.data;
    if (!Array.isArray(data) || data.length === 0) {
      return null;
    }
    
    // Get current price (cp field)
    const currentPrice = data[0].cp;
    return currentPrice !== null ? parseFloat(currentPrice) : null;
  }

  /**
   * Apply normalized field mapping to company data.
   */
  applyFieldMapping(data, mappingType = 'company') {
    if (typeof data !== 'object' || data === null) {
      return data;
    }
    
    const mappedData = {};
    for (const [key, value] of Object.entries(data)) {
      // Use direct key mapping if available, otherwise keep original
      const normalizedKey = TCBSClient.FIELD_MAPPING[key] || key;
      mappedData[normalizedKey] = value;
    }
    
    return mappedData;
  }

  /**
   * Normalize TCBS-specific data structure to standard format.
   */
  normalizeTcbsData(companyData) {
    const normalized = {
      symbol: companyData.symbol,
      exchange: null,
      industry: null,
      company_type: null,
      established_year: null,
      employees: null,
      market_cap: companyData.market_cap,
      current_price: companyData.current_price,
      outstanding_shares: null,
      company_profile: null,
      website: null
    };

    // Extract from overview
    if (companyData.overview) {
      const overview = companyData.overview;
      Object.assign(normalized, {
        exchange: overview.exchange,
        industry: overview.industry,
        company_type: overview.company_type,
        established_year: overview.established_year,
        employees: overview.no_employees,
        outstanding_shares: overview.outstanding_share,
        website: overview.website
      });
    }

    // Extract from profile
    if (companyData.profile) {
      const profile = companyData.profile;
      // Find a profile field that contains company description
      for (const [key, value] of Object.entries(profile)) {
        if (typeof value === 'string' && value.length > 100) { // Assume longer text is profile
          normalized.company_profile = value;
          break;
        }
      }
    }

    // Normalize shareholders
    if (companyData.shareholders) {
      normalized.shareholders = companyData.shareholders.map(shareholder => ({
        shareholder_name: shareholder.share_holder,
        shareholder_percent: shareholder.share_own_percent
      }));
    }

    // Normalize officers
    if (companyData.officers) {
      normalized.officers = companyData.officers.map(officer => ({
        officer_name: officer.officer_name,
        officer_position: officer.officer_position,
        officer_percent: officer.officer_own_percent
      }));
    }

    return normalized;
  }

  /**
   * Get comprehensive company information in a single object.
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCI", "FPT")
   * @param {boolean} mapping - Whether to apply normalized field mapping for cross-platform consistency
   * @returns {Promise<Object|null>} Dictionary containing all company data or null if failed
   */
  async companyInfo(symbol, mapping = true) {
    console.log(`Fetching comprehensive company information for ${symbol}...`);
    
    const companyData = {
      symbol: symbol.toUpperCase()
    };
    
    try {
      // Get company overview
      companyData.overview = await this.overview(symbol);
      
      // Small delay between requests
      await this.sleep(500);
      
      // Get company profile
      companyData.profile = await this.profile(symbol);
      
      // Small delay between requests
      await this.sleep(500);
      
      // Get shareholders
      companyData.shareholders = await this.shareholders(symbol);
      
      // Small delay between requests
      await this.sleep(500);
      
      // Get officers
      companyData.officers = await this.officers(symbol);
      
      // Calculate market cap if we have the data
      if (companyData.overview && companyData.overview.outstanding_share) {
        try {
          // Get current price
          const currentPrice = await this.getCurrentPrice(symbol);
          const outstandingShares = companyData.overview.outstanding_share;
          
          if (currentPrice !== null && outstandingShares !== null) {
            // TCBS returns outstanding shares in millions, convert to actual shares
            const sharesInUnits = outstandingShares * 1_000_000;
            const marketCap = sharesInUnits * currentPrice;
            
            companyData.market_cap = marketCap;
            companyData.current_price = currentPrice;
            companyData.outstanding_shares_millions = outstandingShares;
            companyData.outstanding_shares_actual = sharesInUnits;
            
            console.log(`Outstanding shares (millions): ${outstandingShares.toFixed(1)}`);
            console.log(`Outstanding shares (actual): ${sharesInUnits.toLocaleString()}`);
            console.log(`Current price: ${currentPrice.toLocaleString()} VND`);
            console.log(`Calculated market cap: ${marketCap.toLocaleString()} VND`);
          } else {
            companyData.market_cap = null;
            companyData.current_price = currentPrice;
          }
        } catch (error) {
          console.log(`Could not calculate market cap: ${error.message}`);
          companyData.market_cap = null;
          companyData.current_price = null;
        }
      } else {
        companyData.market_cap = null;
        companyData.current_price = null;
      }
      
      console.log(`Successfully fetched comprehensive company information for ${symbol}`);
      
      // Apply field mapping if requested
      if (mapping) {
        return this.normalizeTcbsData(companyData);
      } else {
        return companyData;
      }
      
    } catch (error) {
      console.log(`Error fetching comprehensive company data for ${symbol}: ${error.message}`);
      return null;
    }
  }

  /**
   * Get comprehensive financial information in a single object.
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCI", "FPT")
   * @param {string} period - Financial reporting period - "quarter" or "year"
   * @param {boolean} mapping - Whether to apply normalized field mapping for cross-platform consistency
   * @returns {Promise<Object|null>} Dictionary containing all financial data or null if failed
   */
  async financialInfo(symbol, period = "quarter", mapping = true) {
    console.log(`Fetching comprehensive financial information for ${symbol} (period: ${period})...`);
    
    // Match Python implementation - try to import Finance class but fall back gracefully
    console.log(`Warning: Could not import TCBS Finance class. Financial data may be limited.`);
    
    const financialData = {
      symbol: symbol.toUpperCase(),
      period: period
    };
    
    try {
      // Get balance sheet data
      console.log(`Fetching balance sheet for ${symbol}...`);
      const balanceSheetData = await this.getFinancialStatement(symbol, 'balance_sheet', period);
      financialData.balance_sheet = balanceSheetData;
      
      // Small delay between requests
      await this.sleep(500);
      
      // Get income statement data
      console.log(`Fetching income statement for ${symbol}...`);
      const incomeStatementData = await this.getFinancialStatement(symbol, 'income_statement', period);
      financialData.income_statement = incomeStatementData;
      
      // Small delay between requests
      await this.sleep(500);
      
      // Get cash flow data
      console.log(`Fetching cash flow for ${symbol}...`);
      const cashFlowData = await this.getFinancialStatement(symbol, 'cash_flow', period);
      financialData.cash_flow = cashFlowData;
      
      // Small delay between requests  
      await this.sleep(500);
      
      // Get financial ratios data
      console.log(`Fetching financial ratios for ${symbol}...`);
      const ratiosData = await this.getFinancialRatios(symbol, period);
      financialData.ratios = ratiosData;
      
      console.log(`Successfully fetched comprehensive financial information for ${symbol}`);
      
      // Apply field mapping if requested
      if (mapping) {
        return this.normalizeTcbsFinancialData(financialData);
      } else {
        return financialData;
      }
      
    } catch (error) {
      console.log(`Error fetching comprehensive financial data for ${symbol}: ${error.message}`);
      return null;
    }
  }

  /**
   * Get financial statement data from TCBS API (generic method).
   */
  async getFinancialStatement(symbol, statementType, period) {
    const periodMap = { "quarter": 1, "year": 0 };
    const tcbsPeriod = periodMap[period] || 1;
    
    const url = `${this.baseUrl}/tcanalysis/v1/finance/${symbol.toUpperCase()}/${statementType}`;
    const params = new URLSearchParams({ yearly: tcbsPeriod, isAll: true });
    
    try {
      const response = await fetch(`${url}?${params}`, {
        method: 'GET',
        headers: this.getHeaders(),
        timeout: 30000
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data && data.length > 0) {
          return this.processFinancialData(data, period, statementType);
        }
      }
      return null;
    } catch (error) {
      console.log(`Error fetching TCBS ${statementType}: ${error.message}`);
      return null;
    }
  }

  /**
   * Get financial ratios data from TCBS API.
   */
  async getFinancialRatios(symbol, period) {
    const periodMap = { "quarter": 1, "year": 0 };
    const tcbsPeriod = periodMap[period] || 1;
    
    const url = `${this.baseUrl}/tcanalysis/v1/finance/${symbol.toUpperCase()}/financialratio`;
    const params = new URLSearchParams({ yearly: tcbsPeriod, isAll: true });
    
    try {
      const response = await fetch(`${url}?${params}`, {
        method: 'GET',
        headers: this.getHeaders(),
        timeout: 30000
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data && data.length > 0) {
          return this.processFinancialData(data, period, 'ratios');
        }
      }
      return null;
    } catch (error) {
      console.log(`Error fetching TCBS financial ratios: ${error.message}`);
      return null;
    }
  }
  
  /**
   * Process financial data from TCBS API into period-indexed format.
   */
  processFinancialData(data, period, type) {
    const result = {};
    
    data.forEach(item => {
      let periodKey;
      if (period === 'quarter' && item.quarter) {
        periodKey = `${item.year}-Q${item.quarter}`;
      } else {
        periodKey = item.year.toString();
      }
      
      // Convert camelCase to snake_case for field names
      const processedItem = {};
      for (const [key, value] of Object.entries(item)) {
        if (key !== 'year' && key !== 'quarter' && key !== 'ticker') {
          const snakeKey = this.camelToSnake(key);
          processedItem[snakeKey] = value;
        }
      }
      
      result[periodKey] = processedItem;
    });
    
    return result;
  }

  /**
   * Convert camelCase object keys to snake_case.
   */
  camelToSnakeKeys(obj) {
    if (!obj || typeof obj !== 'object') {
      return obj;
    }
    
    const result = {};
    for (const [key, value] of Object.entries(obj)) {
      const snakeKey = this.camelToSnake(key);
      result[snakeKey] = value;
    }
    return result;
  }

  /**
   * Normalize TCBS-specific financial data structure to standard format.
   */
  normalizeTcbsFinancialData(financialData) {
    const normalized = {
      symbol: financialData.symbol,
      period: financialData.period,
      balance_sheet: financialData.balance_sheet,
      income_statement: financialData.income_statement,
      cash_flow: financialData.cash_flow,
      ratios: financialData.ratios,
      
      // Key financial metrics (extracted from statements)
      total_assets: null,
      total_liabilities: null,
      shareholders_equity: null,
      total_revenue: null,
      gross_profit: null,
      operating_profit: null,
      net_income: null,
      cash_from_operations: null,
      cash_from_investing: null,
      cash_from_financing: null,
      free_cash_flow: null,
      
      // Key ratios
      pe: null,
      pb: null,
      roe: null,
      roa: null,
      debt_to_equity: null,
      current_ratio: null,
      quick_ratio: null,
      gross_margin: null,
      net_margin: null,
      asset_turnover: null
    };

    // Normalize raw financial statement data while preserving structure
    if (financialData.balance_sheet) {
      normalized.balance_sheet = financialData.balance_sheet;
      // Extract key balance sheet metrics from most recent period
      const periods = Object.keys(financialData.balance_sheet);
      if (periods.length > 0) {
        const latestPeriod = periods[0]; // Most recent period
        const latestBs = financialData.balance_sheet[latestPeriod];
        // Map common balance sheet fields (TCBS specific field names)
        normalized.total_assets = latestBs.total_asset || latestBs.totalAsset;
        normalized.total_liabilities = latestBs.total_liability || latestBs.totalLiability;
        normalized.shareholders_equity = latestBs.total_equity || latestBs.totalEquity;
      }
    }

    if (financialData.income_statement) {
      normalized.income_statement = financialData.income_statement;
      // Extract key income statement metrics from most recent period
      const periods = Object.keys(financialData.income_statement);
      if (periods.length > 0) {
        const latestPeriod = periods[0]; // Most recent period
        const latestIs = financialData.income_statement[latestPeriod];
        // Map common income statement fields (TCBS specific field names)
        normalized.total_revenue = latestIs.net_sale || latestIs.revenue;
        normalized.gross_profit = latestIs.gross_profit;
        normalized.operating_profit = latestIs.profit_from_business_activities || latestIs.operating_profit;
        normalized.net_income = latestIs.profit_after_tax || latestIs.net_income;
      }
    }

    if (financialData.cash_flow) {
      normalized.cash_flow = financialData.cash_flow;
      // Extract key cash flow metrics from most recent period
      const periods = Object.keys(financialData.cash_flow);
      if (periods.length > 0) {
        const latestPeriod = periods[0]; // Most recent period
        const latestCf = financialData.cash_flow[latestPeriod];
        // Map common cash flow fields (TCBS specific field names)
        normalized.cash_from_operations = latestCf.net_cash_flow_from_operating_activities;
        normalized.cash_from_investing = latestCf.net_cash_flow_from_investing_activities;
        normalized.cash_from_financing = latestCf.net_cash_flow_from_financing_activities;
        // Calculate free cash flow if possible
        if (normalized.cash_from_operations && normalized.cash_from_investing) {
          normalized.free_cash_flow = normalized.cash_from_operations + normalized.cash_from_investing;
        }
      }
    }

    if (financialData.ratios) {
      normalized.ratios = financialData.ratios;
      // Extract key ratios from most recent period
      const periods = Object.keys(financialData.ratios);
      if (periods.length > 0) {
        const latestPeriod = periods[0]; // Most recent period
        const latestRatios = financialData.ratios[latestPeriod];
        // Map common ratio fields (TCBS specific field names)
        normalized.pe = latestRatios.price_to_earning || latestRatios.pe;
        normalized.pb = latestRatios.price_to_book || latestRatios.pb;
        normalized.roe = latestRatios.roe;
        normalized.roa = latestRatios.roa;
        normalized.debt_to_equity = latestRatios.debt_on_equity || latestRatios.debt_to_equity;
        normalized.current_ratio = latestRatios.current_ratio;
        normalized.quick_ratio = latestRatios.quick_ratio;
        normalized.gross_margin = latestRatios.gross_profit_margin || latestRatios.gross_margin;
        normalized.net_margin = latestRatios.net_profit_margin || latestRatios.net_margin;
      }
    }

    return normalized;
  }
}

/**
 * Test the TCBS client with comprehensive company data and historical data.
 */
async function main() {
  console.log("\n" + "=".repeat(60));
  console.log("TCBS CLIENT - COMPREHENSIVE TESTING");
  console.log("=".repeat(60));
  
  const client = new TCBSClient(true, 6); // random_agent=true, rate_limit=6
  const testSymbol = "VCI";
  
  // 1. COMPANY INFO
  console.log(`\n🏢 Step 1: Company Information for ${testSymbol}`);
  console.log("-".repeat(40));
  try {
    const companyData = await client.companyInfo(testSymbol);
    if (companyData) {
      console.log("✅ Success! Company data retrieved");
      console.log(`📊 Exchange: ${companyData.exchange || 'N/A'}`);
      console.log(`🏭 Industry: ${companyData.industry || 'N/A'}`);
      if (companyData.market_cap) {
        const marketCapB = companyData.market_cap / 1_000_000_000;
        console.log(`💰 Market Cap: ${marketCapB.toFixed(1)}B VND`);
      }
      if (companyData.outstanding_shares) {
        console.log(`📈 Outstanding Shares: ${companyData.outstanding_shares.toLocaleString()}`);
      }
      console.log(`👥 Shareholders: ${(companyData.shareholders || []).length} major`);
      console.log(`👔 Officers: ${(companyData.officers || []).length} management`);
    } else {
      console.log("❌ Failed to retrieve company data");
    }
  } catch (error) {
    console.log(`💥 Error in company info: ${error.message}`);
  }
  
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // 2. FINANCIAL INFO
  console.log(`\n💹 Step 2: Financial Information for ${testSymbol}`);
  console.log("-".repeat(40));
  try {
    const financialData = await client.financialInfo(testSymbol, "quarter");
    if (financialData) {
      console.log("✅ Success! Financial data retrieved");
      
      // Key metrics (TCBS may not have revenue/income in ratios)
      if (financialData.total_revenue) {
        console.log(`💵 Revenue: ${financialData.total_revenue.toLocaleString()} VND`);
      }
      if (financialData.net_income) {
        console.log(`💰 Net Income: ${financialData.net_income.toLocaleString()} VND`);
      }
      if (financialData.total_assets) {
        console.log(`🏦 Total Assets: ${financialData.total_assets.toLocaleString()} VND`);
      }
      
      // Key ratios
      const ratios = [];
      if (financialData.pe) ratios.push(`PE: ${financialData.pe.toFixed(1)}`);
      if (financialData.pb) ratios.push(`PB: ${financialData.pb.toFixed(1)}`);
      if (financialData.roe) ratios.push(`ROE: ${(financialData.roe * 100).toFixed(1)}%`);
      if (financialData.roa) ratios.push(`ROA: ${(financialData.roa * 100).toFixed(1)}%`);
      if (financialData.debt_to_equity) ratios.push(`D/E: ${financialData.debt_to_equity.toFixed(1)}`);
      
      if (ratios.length > 0) {
        console.log(`📊 Ratios: ${ratios.join(' | ')}`);
      }
    } else {
      console.log("❌ Failed to retrieve financial data");
    }
  } catch (error) {
    console.log(`💥 Error in financial info: ${error.message}`);
  }
  
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // 3. HISTORICAL DATA (Single Symbol)
  console.log(`\n📈 Step 3: Historical Data for ${testSymbol}`);
  console.log("-".repeat(40));
  try {
    const df = await client.getHistory(
      testSymbol,
      "2025-08-01",
      "2025-08-13", 
      "1D",
      365
    );
    
    if (df && df.length > 0) {
      console.log(`✅ Success! Retrieved ${df.length} data points`);
      console.log(`📅 Range: ${df[0].time} to ${df[df.length - 1].time}`);
      
      // Latest data
      const latest = df[df.length - 1];
      console.log(`💹 Latest: ${latest.close.toFixed(0)} VND (Vol: ${latest.volume.toLocaleString()})`);
      
      // Price change
      if (df.length > 1) {
        const firstPrice = df[0].open;
        const lastPrice = df[df.length - 1].close;
        const changePct = ((lastPrice - firstPrice) / firstPrice) * 100;
        const minLow = Math.min(...df.map(d => d.low));
        const maxHigh = Math.max(...df.map(d => d.high));
        console.log(`📊 Change: ${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}% | Range: ${minLow.toFixed(0)}-${maxHigh.toFixed(0)}`);
      }
    } else {
      console.log("❌ Failed to retrieve historical data");
    }
  } catch (error) {
    console.log(`💥 Error in historical data: ${error.message}`);
  }
  
  await new Promise(resolve => setTimeout(resolve, 3000));
  
  // 4. BATCH HISTORICAL DATA (2025-08-14 only)
  console.log(`\n📊 Step 4: Batch Historical Data (10 symbols - 2025-08-14)`);
  console.log("-".repeat(40));
  try {
    const testSymbols = ["AAA", "ACB", "ACV", "ANV", "BCM", "BIC", "BID", "BMP", "BSI", "BSR"];
    const batchData = await client.getBatchHistory(
      testSymbols,
      "2025-08-14",
      "2025-08-14",
      "1D",
      365
    );
    
    if (batchData) {
      console.log(`✅ Batch request successful for ${testSymbols.length} symbols!`);
      console.log("📈 2025-08-14 closing prices:");
      console.log("-".repeat(40));
      
      for (const [symbol, data] of Object.entries(batchData)) {
        if (data && data.length > 0) {
          const closePrice = data[data.length - 1].close;
          console.log(`  ${symbol}: ${closePrice.toFixed(0)} VND`);
        } else {
          console.log(`  ${symbol}: ❌ No data`);
        }
      }
    } else {
      console.log("❌ Batch request failed - no data received");
    }
  } catch (error) {
    console.log(`💥 Error in batch history: ${error.message}`);
  }
  
  console.log(`\n${"=".repeat(60)}`);
  console.log("✅ TCBS CLIENT TESTING COMPLETED");
  console.log("=".repeat(60));
}

// Run main function if this file is executed directly
if (typeof require !== 'undefined' && require.main === module) {
  main().catch(console.error);
}