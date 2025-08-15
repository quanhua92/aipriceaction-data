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
    issue_shares: 'issue_shares',
    company_profile: 'company_profile',
    website: 'website',
    
    // Price Info
    match_price: 'current_price',
    price_change: 'price_change',
    percent_price_change: 'percent_price_change',
    total_volume: 'volume',
    high_52w: 'high_52w',
    low_52w: 'low_52w',
    
    // Financial Ratios
    pe_ratio: 'pe',
    pb_ratio: 'pb',
    roe: 'roe',
    roa: 'roa',
    eps: 'eps',
    revenue: 'revenue',
    net_profit: 'net_profit',
    dividend: 'dividend',
    
    // Shareholders (VCI format)
    shareholder_name: 'name',
    shareholder_percent: 'percentage',
    
    // Officers (VCI format)
    officer_name: 'fullName',
    officer_position: 'positionName',
    officer_percent: 'percentage',
    
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

  /**
   * Fetch historical stock data for multiple symbols in a single request.
   * 
   * @param {Array<string>} symbols - Array of stock symbols (e.g., ["VCI", "AAA", "ACB"])
   * @param {string} start - Start date in "YYYY-MM-DD" format
   * @param {string} end - End date in "YYYY-MM-DD" format (optional)
   * @param {string} interval - Time interval - 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M
   * @returns {Promise<Object|null>} Object mapping symbol -> Array of OHLCV data
   */
  async getBatchHistory(symbols, start, end, interval = "1D") {
    if (!(interval in this.intervalMap)) {
      throw new Error(`Invalid interval: ${interval}. Valid options: ${Object.keys(this.intervalMap).join(', ')}`);
    }
    
    if (!symbols || symbols.length === 0) {
      throw new Error("Symbols array cannot be empty");
    }
    
    // Prepare request parameters
    const endTimestamp = this.calculateTimestamp(end);
    const countBack = this.calculateCountBack(start, end, interval);
    const intervalValue = this.intervalMap[interval];
    
    const url = `${this.baseUrl}chart/OHLCChart/gap-chart`;
    const payload = {
      timeFrame: intervalValue,
      symbols: symbols,  // Pass all symbols at once
      to: endTimestamp,
      countBack: countBack
    };
    
    console.log(`Fetching batch data for ${symbols.length} symbols: ${symbols.join(', ')}`);
    console.log(`Date range: ${start} to ${end || 'now'} [${interval}] (count_back=${countBack})`);
    
    // Make the request
    const responseData = await this.makeRequest(url, payload);
    
    if (!responseData || !Array.isArray(responseData)) {
      console.log("No data received from API");
      return null;
    }
    
    if (responseData.length !== symbols.length) {
      console.log(`Warning: Expected ${symbols.length} responses, got ${responseData.length}`);
    }
    
    // Debug: Show VCI batch response structure
    console.log(`🔍 VCI BATCH DEBUG:`);
    console.log(`  Requested symbols: ${symbols.join(', ')}`);
    console.log(`  Response array length: ${responseData.length}`);
    
    // Debug: Check if response includes symbol identifiers
    for (let i = 0; i < responseData.length; i++) {
      const item = responseData[i];
      if (typeof item === 'object' && item !== null) {
        // Check for symbol field or any identifier
        const symbolFields = ['symbol', 'ticker', 'Symbol', 'Ticker', 's'];
        let foundSymbol = null;
        for (const field of symbolFields) {
          if (field in item) {
            foundSymbol = item[field];
            break;
          }
        }
        console.log(`    response[${i}] symbol field: ${foundSymbol}`);
        if ('c' in item && Array.isArray(item.c) && item.c.length > 0) {
          console.log(`    response[${i}] last close: ${item.c[item.c.length - 1]}`);
        }
      }
    }
    
    const results = {};
    const startDt = new Date(start + 'T00:00:00.000Z');
    
    // Create a mapping from response data using symbol field
    const responseMap = {};
    for (let i = 0; i < responseData.length; i++) {
      const dataItem = responseData[i];
      // Find symbol identifier in response
      const symbolFields = ['symbol', 'ticker', 'Symbol', 'Ticker', 's'];
      let responseSymbol = null;
      for (const field of symbolFields) {
        if (field in dataItem) {
          responseSymbol = dataItem[field];
          break;
        }
      }
      
      if (responseSymbol) {
        responseMap[responseSymbol.toUpperCase()] = dataItem;
        console.log(`  Mapped response[${i}] -> symbol: ${responseSymbol}`);
      } else {
        console.log(`  WARNING: No symbol field found in response[${i}]`);
      }
    }
    
    // Process each requested symbol using correct mapping
    for (const symbol of symbols) {
      const symbolUpper = symbol.toUpperCase();
      console.log(`  Processing symbol: ${symbol}`);
      
      if (!(symbolUpper in responseMap)) {
        console.log(`No data available for symbol: ${symbol}`);
        results[symbol] = null;
        continue;
      }
      
      const dataItem = responseMap[symbolUpper];
      
      // Check if we have the required OHLCV arrays
      const requiredKeys = ['o', 'h', 'l', 'c', 'v', 't'];
      if (!requiredKeys.every(key => key in dataItem)) {
        console.log(`Missing required keys for ${symbol}. Available: ${Object.keys(dataItem).join(', ')}`);
        results[symbol] = null;
        continue;
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
        console.log(`Inconsistent array lengths for ${symbol}: ${lengths.join(', ')}`);
        results[symbol] = null;
        continue;
      }
      
      if (lengths[0] === 0) {
        console.log(`Empty data arrays for ${symbol}`);
        results[symbol] = null;
        continue;
      }
      
      // Convert to array of OHLCV objects
      const ohlcvData = [];
      for (let j = 0; j < times.length; j++) {
        ohlcvData.push({
          time: new Date(times[j] * 1000), // Convert Unix timestamp to Date
          open: parseFloat(opens[j]),
          high: parseFloat(highs[j]),
          low: parseFloat(lows[j]),
          close: parseFloat(closes[j]),
          volume: volumes[j] !== null ? parseInt(volumes[j]) : 0
        });
      }
      
      // Filter by start date
      const filteredData = ohlcvData.filter(item => item.time >= startDt);
      
      // Sort by time
      filteredData.sort((a, b) => a.time.getTime() - b.time.getTime());
      
      // Add symbol property for identification
      filteredData.forEach(item => item.symbol = symbol);
      
      results[symbol] = filteredData;
      console.log(`✅ ${symbol}: ${filteredData.length} data points`);
    }
    
    const successfulCount = Object.values(results).filter(data => data !== null).length;
    console.log(`Successfully fetched data for ${successfulCount}/${symbols.length} symbols`);
    
    return results;
  }

  /**
   * Get company overview data using VCI GraphQL endpoint (same as vnstock).
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCB", "VCI")
   * @returns {Promise<Object|null>} Object with comprehensive company information
   */
  async overview(symbol) {
    // Use the same GraphQL endpoint as vnstock
    const url = this.baseUrl.replace('/api/', '/data-mt/') + 'graphql';
    
    // The EXACT same GraphQL query used by vnstock
    const graphqlQuery = `query Query($ticker: String!, $lang: String!) {
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
}`;
    
    const payload = {
      query: graphqlQuery,
      variables: { ticker: symbol.toUpperCase(), lang: "vi" }
    };
    
    console.log(`Fetching company overview for ${symbol}...`);
    
    const responseData = await this.makeRequest(url, payload);
    
    if (!responseData || !responseData.data) {
      console.log("No company data received from API");
      return null;
    }
    
    if (!responseData.data || !responseData.data.CompanyListingInfo) {
      console.log("No CompanyListingInfo found in response");
      return null;
    }
    
    // Extract company listing info (same as vnstock)
    const companyData = responseData.data.CompanyListingInfo;
    
    // Flatten the nested structure
    const overviewData = {
      symbol: symbol.toUpperCase(),
      issueShare: companyData.issueShare || 'N/A',
      companyProfile: companyData.companyProfile || 'N/A',
      en_CompanyProfile: companyData.en_CompanyProfile || 'N/A',
      history: companyData.history || 'N/A',
      en_History: companyData.en_History || 'N/A',
      icbName2: companyData.icbName2 || 'N/A',
      enIcbName2: companyData.enIcbName2 || 'N/A',
      icbName3: companyData.icbName3 || 'N/A',
      enIcbName3: companyData.enIcbName3 || 'N/A',
      icbName4: companyData.icbName4 || 'N/A',
      enIcbName4: companyData.enIcbName4 || 'N/A'
    };
    
    // Financial ratio data from company listing
    if (companyData.financialRatio) {
      overviewData.charterCapital = companyData.financialRatio.charterCapital || 'N/A';
    }
    
    console.log(`Successfully fetched company overview for ${symbol}`);
    return overviewData;
  }

  /**
   * Get financial ratio summary using VCI GraphQL endpoint (same as vnstock).
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCB", "VCI")
   * @returns {Promise<Array|null>} Array with comprehensive financial ratios
   */
  async ratioSummary(symbol) {
    // Use the same GraphQL approach as overview method
    const url = this.baseUrl.replace('/api/', '/data-mt/') + 'graphql';
    
    // Same GraphQL query as overview (reuse the comprehensive query)
    const graphqlQuery = `query Query($ticker: String!, $lang: String!) {
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
}`;
    
    const payload = {
      query: graphqlQuery,
      variables: { ticker: symbol.toUpperCase(), lang: "vi" }
    };
    
    console.log(`Fetching financial ratios for ${symbol}...`);
    
    const responseData = await this.makeRequest(url, payload);
    
    if (!responseData || !responseData.data) {
      console.log("No financial ratio data received from API");
      return null;
    }
    
    if (!responseData.data || !responseData.data.TickerPriceInfo) {
      console.log("No TickerPriceInfo found in response");
      return null;
    }
    
    // Extract financial ratio data (same as vnstock)
    const tickerInfo = responseData.data.TickerPriceInfo;
    if (!tickerInfo || !tickerInfo.financialRatio) {
      console.log("No financial ratios available for this symbol");
      return null;
    }
    
    const financialRatios = tickerInfo.financialRatio;
    
    // Convert to array format (same as vnstock)
    const ratioData = [];
    for (const [key, value] of Object.entries(financialRatios)) {
      if (key !== "__typename" && value !== null && value !== 'N/A') {
        ratioData.push({
          symbol: symbol.toUpperCase(),
          ratio_name: key,
          value: value
        });
      }
    }
    
    if (ratioData.length === 0) {
      console.log("No valid financial ratios found");
      return null;
    }
    
    console.log(`Successfully fetched ${ratioData.length} financial ratios for ${symbol}`);
    return ratioData;
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
      const normalizedKey = VCIClient.FIELD_MAPPING[key] || key;
      mappedData[normalizedKey] = value;
    }
    
    return mappedData;
  }

  /**
   * Normalize VCI-specific data structure to standard format.
   */
  normalizeVciData(companyData) {
    const normalized = {
      symbol: companyData.symbol,
      exchange: null,
      industry: null,
      company_type: null,
      established_year: null,
      employees: null,
      market_cap: companyData.market_cap,
      current_price: companyData.current_price,
      outstanding_shares: companyData.issue_shares,
      company_profile: null,
      website: null
    };

    // Extract from CompanyListingInfo
    if (companyData.CompanyListingInfo) {
      const listingInfo = companyData.CompanyListingInfo;
      Object.assign(normalized, {
        industry: listingInfo.icbName3,
        company_profile: listingInfo.companyProfile,
        outstanding_shares: listingInfo.issueShare
      });
    }

    // Extract from TickerPriceInfo
    if (companyData.TickerPriceInfo) {
      const priceInfo = companyData.TickerPriceInfo;
      Object.assign(normalized, {
        exchange: priceInfo.exchange,
        current_price: priceInfo.matchPrice,
        price_change: priceInfo.priceChange,
        percent_price_change: priceInfo.percentPriceChange,
        volume: priceInfo.totalVolume,
        high_52w: priceInfo.highestPrice1Year,
        low_52w: priceInfo.lowestPrice1Year
      });

      // Extract financial ratios
      if (priceInfo.financialRatio) {
        const ratios = priceInfo.financialRatio;
        Object.assign(normalized, {
          pe: ratios.pe,
          pb: ratios.pb,
          roe: ratios.roe,
          roa: ratios.roa,
          eps: ratios.eps,
          revenue: ratios.revenue,
          net_profit: ratios.netProfit,
          dividend: ratios.dividend
        });
      }
    }

    // Normalize shareholders
    if (companyData.OrganizationShareHolders) {
      normalized.shareholders = companyData.OrganizationShareHolders.map(shareholder => ({
        shareholder_name: shareholder.ownerFullName,
        shareholder_percent: shareholder.percentage
      }));
    }

    // Normalize officers
    if (companyData.OrganizationManagers) {
      normalized.officers = companyData.OrganizationManagers.map(manager => ({
        officer_name: manager.fullName,
        officer_position: manager.positionName,
        officer_percent: manager.percentage
      }));
    }

    return normalized;
  }

  /**
   * Get comprehensive company information in a single object (same as vnstock approach).
   * 
   * @param {string} symbol - Stock symbol (e.g., "VCB", "VCI")
   * @param {boolean} mapping - Whether to apply normalized field mapping for cross-platform consistency
   * @returns {Promise<Object|null>} Object containing all company data: overview, ratios, price info, shareholders, managers, etc.
   */
  async companyInfo(symbol, mapping = true) {
    const url = this.baseUrl.replace('/api/', '/data-mt/') + 'graphql';
    
    // Complete GraphQL query that fetches ALL company data at once
    const graphqlQuery = `query Query($ticker: String!, $lang: String!) {
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
}`;
    
    const payload = {
      query: graphqlQuery,
      variables: { ticker: symbol.toUpperCase(), lang: "vi" }
    };
    
    console.log(`Fetching comprehensive company information for ${symbol}...`);
    
    const responseData = await this.makeRequest(url, payload);
    
    if (!responseData || !responseData.data) {
      console.log("No company data received from API");
      return null;
    }
    
    // Return the complete data structure
    const companyData = responseData.data;
    
    // Add symbol to the root level for convenience
    companyData.symbol = symbol.toUpperCase();
    
    // Calculate market cap if we have the required data
    try {
      const tickerPriceInfo = companyData.TickerPriceInfo;
      const companyListingInfo = companyData.CompanyListingInfo;
      
      if (tickerPriceInfo && companyListingInfo) {
        const currentPrice = tickerPriceInfo.matchPrice;
        const issueShares = companyListingInfo.issueShare;
        
        if (currentPrice !== null && currentPrice !== undefined && 
            issueShares !== null && issueShares !== undefined) {
          // VCI returns actual share counts (not millions like TCBS)
          const marketCap = issueShares * currentPrice;
          companyData.market_cap = marketCap;
          companyData.current_price = currentPrice;
          companyData.issue_shares = issueShares;
          
          console.log(`Issue shares: ${issueShares.toLocaleString()}`);
          console.log(`Current price: ${currentPrice.toLocaleString()} VND`);
          console.log(`Calculated market cap: ${marketCap.toLocaleString()} VND`);
        } else {
          companyData.market_cap = null;
          companyData.current_price = currentPrice;
          companyData.issue_shares = issueShares;
        }
      } else {
        companyData.market_cap = null;
        companyData.current_price = null;
        companyData.issue_shares = null;
      }
    } catch (error) {
      console.log(`Could not calculate market cap: ${error.message}`);
      companyData.market_cap = null;
      companyData.current_price = null;
      companyData.issue_shares = null;
    }
    
    console.log(`Successfully fetched comprehensive company information for ${symbol}`);
    
    // Apply field mapping if requested
    if (mapping) {
      return this.normalizeVciData(companyData);
    } else {
      return companyData;
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
    
    const financialData = {
      symbol: symbol.toUpperCase(),
      period: period
    };
    
    try {
      // Get comprehensive financial ratios using VCI GraphQL API
      console.log(`Fetching financial ratios for ${symbol}...`);
      const ratiosData = await this.getVciFinancialRatios(symbol, period);
      
      if (ratiosData && ratiosData.length > 0) {
        financialData.ratios = ratiosData;
        
        // Extract balance sheet data from ratios (BSA codes)
        console.log(`Extracting balance sheet for ${symbol}...`);
        const balanceSheetData = this.extractBalanceSheetFromRatios(ratiosData);
        financialData.balance_sheet = balanceSheetData;
        
        // Extract income statement data from ratios (ISA, ISB codes)
        console.log(`Extracting income statement for ${symbol}...`);
        const incomeStatementData = this.extractIncomeStatementFromRatios(ratiosData);
        financialData.income_statement = incomeStatementData;
        
        // Extract cash flow data from ratios (CFA, CFB, CFS codes)
        console.log(`Extracting cash flow for ${symbol}...`);
        const cashFlowData = this.extractCashFlowFromRatios(ratiosData);
        financialData.cash_flow = cashFlowData;
      } else {
        financialData.balance_sheet = null;
        financialData.income_statement = null;
        financialData.cash_flow = null;
        financialData.ratios = null;
      }
      
      console.log(`Successfully fetched comprehensive financial information for ${symbol}`);
      
      // Apply field mapping if requested
      if (mapping) {
        return this.normalizeVciFinancialData(financialData);
      } else {
        return financialData;
      }
      
    } catch (error) {
      console.log(`Error fetching comprehensive financial data for ${symbol}: ${error.message}`);
      return null;
    }
  }

  /**
   * Get VCI financial ratios using GraphQL API.
   */
  async getVciFinancialRatios(symbol, period) {
    const periodMap = { "quarter": "Q", "year": "Y" };
    const vciPeriod = periodMap[period] || "Q";
    
    const graphqlQuery = `fragment Ratios on CompanyFinancialRatio {
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
}`;
    
    const payload = {
      query: graphqlQuery,
      variables: {
        ticker: symbol.toUpperCase(),
        period: vciPeriod
      }
    };
    
    try {
      const response = await this.makeRequest("https://trading.vietcap.com.vn/data-mt/graphql", payload);
      if (response && response.data && response.data.CompanyFinancialRatio) {
        const ratiosData = response.data.CompanyFinancialRatio.ratio;
        if (ratiosData && ratiosData.length > 0) {
          return ratiosData;
        }
      }
      return null;
    } catch (error) {
      console.log(`Error fetching VCI financial ratios: ${error.message}`);
      return null;
    }
  }
  
  /**
   * Extract balance sheet data from VCI ratios (BSA codes).
   */
  extractBalanceSheetFromRatios(ratiosData) {
    if (!ratiosData || ratiosData.length === 0) return null;
    
    const balanceSheetData = ratiosData.map(item => {
      const bsItem = { ticker: item.ticker, yearReport: item.yearReport, lengthReport: item.lengthReport };
      Object.keys(item).forEach(key => {
        if (key.startsWith('BSA')) {
          bsItem[key] = item[key];
        }
      });
      return bsItem;
    });
    
    return balanceSheetData;
  }
  
  /**
   * Extract income statement data from VCI ratios (ISA, ISB codes).
   */
  extractIncomeStatementFromRatios(ratiosData) {
    if (!ratiosData || ratiosData.length === 0) return null;
    
    const incomeStatementData = ratiosData.map(item => {
      const isItem = { ticker: item.ticker, yearReport: item.yearReport, lengthReport: item.lengthReport };
      Object.keys(item).forEach(key => {
        if (key.startsWith('ISA') || key.startsWith('ISB') || key.startsWith('ISS') || key.startsWith('ISI') || 
            ['revenue', 'netProfit', 'grossMargin', 'netProfitMargin'].includes(key)) {
          isItem[key] = item[key];
        }
      });
      return isItem;
    });
    
    return incomeStatementData;
  }
  
  /**
   * Extract cash flow data from VCI ratios (CFA, CFB, CFS codes).
   */
  extractCashFlowFromRatios(ratiosData) {
    if (!ratiosData || ratiosData.length === 0) return null;
    
    const cashFlowData = ratiosData.map(item => {
      const cfItem = { ticker: item.ticker, yearReport: item.yearReport, lengthReport: item.lengthReport };
      Object.keys(item).forEach(key => {
        if (key.startsWith('CFA') || key.startsWith('CFB') || key.startsWith('CFS')) {
          cfItem[key] = item[key];
        }
      });
      return cfItem;
    });
    
    
    return cashFlowData;
  }
  
  /**
   * Normalize VCI-specific financial data structure to standard format.
   */
  normalizeVciFinancialData(financialData) {
    const normalized = {
      symbol: financialData.symbol,
      period: financialData.period,
      balance_sheet: null,
      income_statement: null,
      cash_flow: null,
      ratios: null,
      
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
    if (financialData.balance_sheet && Array.isArray(financialData.balance_sheet) && financialData.balance_sheet.length > 0) {
      normalized.balance_sheet = financialData.balance_sheet;
      // Extract key balance sheet metrics from most recent period
      const latestBs = financialData.balance_sheet[0];
      // Map common balance sheet fields (VCI specific field names)
      normalized.total_assets = latestBs['Total assets'] || latestBs['Total Assets'];
      normalized.total_liabilities = latestBs['Total liabilities'] || latestBs['Total Liabilities'];
      normalized.shareholders_equity = latestBs['Shareholders\' equity'] || latestBs['Total Equity'];
    }

    if (financialData.income_statement && Array.isArray(financialData.income_statement) && financialData.income_statement.length > 0) {
      normalized.income_statement = financialData.income_statement;
      // Extract key income statement metrics from most recent period
      const latestIs = financialData.income_statement[0];
      // Map common income statement fields (VCI specific field names)
      normalized.total_revenue = latestIs['Net sales'] || latestIs['Revenue'];
      normalized.gross_profit = latestIs['Gross profit'];
      normalized.operating_profit = latestIs['Profit from business activities'] || latestIs['Operating Income'];
      normalized.net_income = latestIs['Profit after tax'] || latestIs['Net Income'];
    }

    if (financialData.cash_flow && Array.isArray(financialData.cash_flow) && financialData.cash_flow.length > 0) {
      normalized.cash_flow = financialData.cash_flow;
      // Extract key cash flow metrics from most recent period
      const latestCf = financialData.cash_flow[0];
      // Map common cash flow fields (VCI specific field names)
      normalized.cash_from_operations = latestCf['Net cash flows from operating activities'];
      normalized.cash_from_investing = latestCf['Net cash flows from investing activities'];
      normalized.cash_from_financing = latestCf['Net cash flows from financing activities'];
      // Calculate free cash flow if possible
      if (normalized.cash_from_operations && normalized.cash_from_investing) {
        normalized.free_cash_flow = normalized.cash_from_operations + normalized.cash_from_investing;
      }
    }

    if (financialData.ratios && Array.isArray(financialData.ratios) && financialData.ratios.length > 0) {
      normalized.ratios = financialData.ratios;
      // Extract key ratios from most recent period
      const latestRatios = financialData.ratios[0];
      // Map common ratio fields (VCI actual field names from API)
      normalized.pe = latestRatios.pe;
      normalized.pb = latestRatios.pb;
      normalized.roe = latestRatios.roe;
      normalized.roa = latestRatios.roa;
      normalized.debt_to_equity = latestRatios.de;
      normalized.current_ratio = latestRatios.currentRatio;
      normalized.quick_ratio = latestRatios.quickRatio;
      normalized.gross_margin = latestRatios.grossMargin;
      normalized.net_margin = latestRatios.netProfitMargin;
      
      // Extract key financial metrics from ratios data
      normalized.total_revenue = latestRatios.revenue;
      normalized.net_income = latestRatios.netProfit;
      normalized.total_assets = latestRatios.BSA1;  // Total assets from balance sheet code
      normalized.shareholders_equity = latestRatios.ae;  // Average equity
    }

    return normalized;
  }
}

/**
 * Test the VCI client with comprehensive company data and historical data.
 */
async function main() {
  console.log("\n" + "=".repeat(60));
  console.log("VCI CLIENT - COMPREHENSIVE TESTING");
  console.log("=".repeat(60));
  
  const client = new VCIClient(true, 6); // random_agent=true, rate_limit=6
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
      
      // Key metrics
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
      "1D"
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
      "1D"
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
  console.log("✅ VCI CLIENT TESTING COMPLETED");
  console.log("=".repeat(60));
}

// Run main function if this file is executed directly
if (typeof require !== 'undefined' && require.main === module) {
  main().catch(console.error);
}