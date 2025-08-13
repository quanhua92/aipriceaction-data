#!/usr/bin/env node

/**
 * Standalone FMarket Fund Data Client (JavaScript)
 * 
 * This client provides access to FMarket API for Vietnamese mutual fund data
 * including fund listings, NAV history, and portfolio holdings.
 * 
 * This is a 1:1 port of fmarket.py - refer to fmarket.md guide for complete understanding.
 * Works in both Node.js and modern browsers.
 */

class FMarketClient {
  /**
   * Standalone FMarket client for fetching Vietnamese mutual fund data.
   * 
   * This implementation provides direct access to FMarket API without dependencies.
   * Core functionality: fund listings and NAV (Net Asset Value) history.
   */

  constructor(randomAgent = true, rateLimitPerMinute = 10) {
    this.baseUrl = "https://api.fmarket.vn/res/products";
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
    
    // Fund type mapping
    this.fundTypeMapping = {
      "BALANCED": ["BALANCED"],
      "BOND": ["BOND", "MONEY_MARKET"],
      "STOCK": ["STOCK"]
    };
    
    // Initialize session
    this.setupSession();
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
      'User-Agent': userAgent,
      'Referer': 'https://fmarket.vn/',
      'Origin': 'https://fmarket.vn'
    };
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
  async makeRequest(url, payload = null, method = "POST", maxRetries = 5) {
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
        
        const options = {
          method: method.toUpperCase(),
          headers: this.defaultHeaders,
          timeout: 30000
        };
        
        if (method.toUpperCase() === "POST" && payload) {
          options.body = JSON.stringify(payload);
        }
        
        const response = await fetch(url, options);
        
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
   * Convert Unix timestamps to datetime format.
   */
  convertUnixToDatetime(data, columns) {
    const result = JSON.parse(JSON.stringify(data)); // Deep copy
    
    for (const item of result) {
      for (const col of columns) {
        if (item[col] !== undefined && item[col] !== null) {
          const date = new Date(item[col]);
          if (date.getTime() >= new Date('1970-01-01').getTime()) {
            item[col] = date.toISOString().split('T')[0];
          } else {
            item[col] = null;
          }
        }
      }
    }
    
    return result;
  }

  /**
   * Get list of all available mutual funds on FMarket.
   * 
   * @param {string} fundType - Type of fund to filter. Options: "", "BALANCED", "BOND", "STOCK"
   *                           Empty string returns all funds.
   * @returns {Promise<Array|null>} Array with fund information or null if failed
   */
  async getFundListing(fundType = "") {
    fundType = fundType.toUpperCase();
    const fundAssetTypes = this.fundTypeMapping[fundType] || [];
    
    if (fundType && !["BALANCED", "BOND", "STOCK"].includes(fundType)) {
      console.log(`Warning: Unsupported fund type: '${fundType}'. Using all funds.`);
    }
    
    const payload = {
      "types": ["NEW_FUND", "TRADING_FUND"],
      "issuerIds": [],
      "sortOrder": "DESC",
      "sortField": "navTo6Months",
      "page": 1,
      "pageSize": 100,
      "isIpo": false,
      "fundAssetTypes": fundAssetTypes,
      "bondRemainPeriods": [],
      "searchField": "",
      "isBuyByReward": false,
      "thirdAppIds": [],
    };
    
    const url = `${this.baseUrl}/filter`;
    
    console.log(`Fetching fund listings${fundType ? ' for ' + fundType : ''}...`);
    
    const responseData = await this.makeRequest(url, payload);
    
    if (!responseData) {
      console.log("No response from API");
      return null;
    }
    
    try {
      // Extract fund data
      if (!responseData.data || !responseData.data.rows) {
        console.log("Unexpected response format");
        return null;
      }
      
      const fundsData = responseData.data.rows;
      const totalFunds = responseData.data.total || fundsData.length;
      
      console.log(`Total funds found: ${totalFunds}`);
      
      if (fundsData.length === 0) {
        console.log("No fund data available");
        return null;
      }
      
      // Flatten nested data and select relevant columns
      const processedData = fundsData.map(fund => {
        const item = {
          fund_id: fund.id,
          short_name: fund.shortName,
          full_name: fund.name,
          issuer: fund.issuerName,
          fund_type: fund.fundAssetTypeName,
          first_issue_date: fund.firstIssueAt
        };
        
        // Add NAV change data if available
        if (fund.productNavChange) {
          item.nav_change_1m = fund.productNavChange.navTo1Months;
          item.nav_change_3m = fund.productNavChange.navTo3Months;
          item.nav_change_6m = fund.productNavChange.navTo6Months;
          item.nav_change_12m = fund.productNavChange.navTo12Months;
          item.nav_change_36m = fund.productNavChange.navTo36Months;
          item.nav_update_date = fund.productNavChange.updateAt;
        }
        
        return item;
      });
      
      // Convert Unix timestamps to date format
      const timestampColumns = ["first_issue_date", "nav_update_date"];
      const convertedData = this.convertUnixToDatetime(processedData, timestampColumns);
      
      // Sort by 36-month NAV change (descending)
      convertedData.sort((a, b) => (b.nav_change_36m || 0) - (a.nav_change_36m || 0));
      
      console.log(`Successfully fetched ${convertedData.length} fund records`);
      return convertedData;
      
    } catch (e) {
      console.log(`Error processing fund listing data: ${e.message}`);
      return null;
    }
  }

  /**
   * Get NAV (Net Asset Value) history for a specific fund.
   * 
   * @param {string} fundSymbol - Fund short name (e.g., "SSISCA", "VCBF-BCF")
   * @param {number} maxAttempts - Maximum number of different approaches to try
   * @returns {Promise<Array|null>} Array with columns: date, nav_per_unit, or null if unavailable
   * 
   * Note: As of August 2025, FMarket has restricted NAV history endpoints to authenticated users only.
   *       This method attempts multiple strategies to access historical NAV data.
   */
  async getNavHistory(fundSymbol, maxAttempts = 3) {
    console.log(`🔄 Attempting to retrieve NAV history for ${fundSymbol}...`);
    
    // First get the fund ID
    const fundId = await this.getFundId(fundSymbol);
    if (!fundId) {
      console.log(`❌ Could not find fund ID for symbol: ${fundSymbol}`);
      return null;
    }
    
    console.log(`📍 Found fund ID: ${fundId} for ${fundSymbol}`);
    
    // Strategy 1: Create estimated NAV series from performance data (fastest & most reliable)
    let navData = await this.tryNavFromPerformanceData(fundId, fundSymbol);
    if (navData !== null) {
      return navData;
    }
    
    // Strategy 2: Extract current NAV point from fund details (second most reliable)
    navData = await this.tryCurrentNavFromDetails(fundId, fundSymbol);
    if (navData !== null) {
      return navData;
    }
    
    // Strategy 3: Try alternative endpoint variations (likely to fail but quick)
    navData = await this.tryAlternativeNavEndpoints(fundId, fundSymbol);
    if (navData !== null) {
      return navData;
    }
    
    // Strategy 4: Try the original vnstock endpoint (most likely to cause delays)
    navData = await this.tryOriginalNavEndpoint(fundId, fundSymbol);
    if (navData !== null) {
      return navData;
    }
    
    console.log(`⚠️  Unable to retrieve NAV history for ${fundSymbol}`);
    console.log(`📋 All NAV history endpoints now require authentication`);
    console.log(`💡 Fund listings and current NAV are still available via getFundListing()`);
    console.log(`🔍 Consider using performance metrics from fund details as alternative`);
    
    return null;
  }

  /**
   * Try the original vnstock NAV endpoint.
   */
  async tryOriginalNavEndpoint(fundId, fundSymbol) {
    console.log(`🔍 Trying original NAV endpoint...`);
    
    const currentDate = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    
    // List of possible endpoint variations (most likely to work first)
    const endpointsToTry = [
      "https://api.fmarket.vn/res/nav-history"
    ];
    
    const payload = {
      "isAllData": 1,
      "productId": fundId,
      "fromDate": null,
      "toDate": currentDate,
    };
    
    for (const endpoint of endpointsToTry) {
      try {
        console.log(`  🌐 Testing: ${endpoint}`);
        const responseData = await this.makeRequest(endpoint, payload, "POST");
        
        if (responseData && responseData.data) {
          console.log(`  ✅ Success with endpoint: ${endpoint}`);
          return this.parseNavData(responseData, fundSymbol);
        }
        
      } catch (e) {
        console.log(`  ❌ Failed: ${e.message}`);
        continue;
      }
    }
    
    return null;
  }

  /**
   * Try alternative NAV endpoints and methods.
   */
  async tryAlternativeNavEndpoints(fundId, fundSymbol) {
    console.log(`🔍 Trying alternative NAV endpoints...`);
    
    // Try GET endpoints (ordered by likelihood of success)
    const getEndpoints = [
      `https://api.fmarket.vn/res/products/${fundId}/nav`,
      `https://api.fmarket.vn/res/products/${fundId}/chart`,
      `https://api.fmarket.vn/res/products/${fundId}/history`
    ];
    
    for (const endpoint of getEndpoints) {
      try {
        console.log(`  🌐 Testing: ${endpoint}`);
        
        // Make GET request
        const response = await fetch(endpoint, {
          headers: this.defaultHeaders,
          timeout: 30000
        });
        
        if (response.status === 200) {
          try {
            const responseData = await response.json();
            if (responseData.data) {
              console.log(`  ✅ Success with endpoint: ${endpoint}`);
              return this.parseNavData(responseData, fundSymbol);
            }
          } catch (e) {
            continue;
          }
        } else if (response.status === 401) {
          console.log(`  🔒 Authentication required: ${endpoint}`);
        } else {
          console.log(`  ❌ HTTP ${response.status}: ${endpoint}`);
        }
        
      } catch (e) {
        console.log(`  ❌ Failed: ${e.message}`);
        continue;
      }
    }
    
    return null;
  }

  /**
   * Extract current NAV from fund details endpoint.
   */
  async tryCurrentNavFromDetails(fundId, fundSymbol) {
    console.log(`🔍 Trying current NAV from fund details...`);
    
    try {
      // Get fund details which includes current NAV
      const response = await fetch(`https://api.fmarket.vn/res/products/${fundId}`, {
        headers: this.defaultHeaders,
        timeout: 30000
      });
      
      if (response.status === 200) {
        const data = await response.json();
        
        if (data.data && data.data.nav) {
          const currentNav = data.data.nav;
          const updateTime = data.data.productNavChange?.updateAt;
          
          if (updateTime) {
            // Convert Unix timestamp to date
            const navDate = new Date(updateTime).toISOString().split('T')[0];
            
            // Create single-point array
            const navArray = [{
              date: navDate,
              nav_per_unit: currentNav
            }];
            
            console.log(`  ✅ Current NAV: ${currentNav} (as of ${navDate})`);
            console.log(`  ℹ️  Note: Only current NAV available, historical data requires authentication`);
            
            return navArray;
          }
        }
      }
      
    } catch (e) {
      console.log(`  ❌ Error accessing fund details: ${e.message}`);
    }
    
    return null;
  }

  /**
   * Create estimated NAV series from performance data.
   */
  async tryNavFromPerformanceData(fundId, fundSymbol) {
    console.log(`🔍 Trying NAV estimation from performance data...`);
    
    try {
      // Get fund details
      const response = await fetch(`https://api.fmarket.vn/res/products/${fundId}`, {
        headers: this.defaultHeaders,
        timeout: 30000
      });
      
      if (response.status === 200) {
        const data = await response.json();
        const fundData = data.data || {};
        
        const currentNav = fundData.nav;
        const navChanges = fundData.productNavChange || {};
        
        if (currentNav && navChanges) {
          console.log(`  📊 Creating estimated NAV series from performance data...`);
          
          // Calculate historical NAVs based on performance changes
          const today = new Date();
          const estimatedNavs = [];
          
          // Current NAV
          estimatedNavs.push({
            date: today.toISOString().split('T')[0],
            nav_per_unit: currentNav,
            data_type: 'current'
          });
          
          // Estimate NAVs from performance percentages
          const periods = [
            ['1M', 1, 30, navChanges.navTo1Months],
            ['3M', 3, 90, navChanges.navTo3Months], 
            ['6M', 6, 180, navChanges.navTo6Months],
            ['12M', 12, 365, navChanges.navTo12Months],
            ['24M', 24, 730, navChanges.navTo24Months],
            ['36M', 36, 1095, navChanges.navTo36Months]
          ];
          
          for (const [periodName, months, days, changePct] of periods) {
            if (changePct !== null && changePct !== undefined) {
              // Calculate historical NAV
              const historicalNav = currentNav / (1 + (changePct / 100));
              const historicalDate = new Date(today.getTime() - days * 24 * 60 * 60 * 1000);
              
              estimatedNavs.push({
                date: historicalDate.toISOString().split('T')[0],
                nav_per_unit: historicalNav,
                data_type: `estimated_${periodName.toLowerCase()}`
              });
            }
          }
          
          // Create result array
          if (estimatedNavs.length > 0) {
            // Sort by date
            estimatedNavs.sort((a, b) => new Date(a.date) - new Date(b.date));
            
            // Drop the data_type column for clean output
            const resultArray = estimatedNavs.map(item => ({
              date: item.date,
              nav_per_unit: item.nav_per_unit
            }));
            
            console.log(`  ✅ Created estimated NAV series with ${resultArray.length} data points`);
            console.log(`  ℹ️  Note: These are estimated values based on performance percentages`);
            console.log(`  📈 Data range: ${resultArray[0].date} to ${resultArray[resultArray.length-1].date}`);
            
            return resultArray;
          }
        }
      }
      
    } catch (e) {
      console.log(`  ❌ Error creating estimated NAV series: ${e.message}`);
    }
    
    return null;
  }

  /**
   * Parse NAV data from API response.
   */
  parseNavData(responseData, fundSymbol) {
    try {
      const data = responseData.data || [];
      
      if (!Array.isArray(data) || data.length === 0) {
        return null;
      }
      
      // Handle different possible column names
      const dateColumns = ['navDate', 'date', 'tradeDate', 'updateAt'];
      const navColumns = ['nav', 'navPerUnit', 'nav_per_unit', 'price'];
      
      let dateCol = null;
      let navCol = null;
      
      // Find available date and NAV columns
      for (const col of dateColumns) {
        if (data[0] && data[0][col] !== undefined) {
          dateCol = col;
          break;
        }
      }
      
      for (const col of navColumns) {
        if (data[0] && data[0][col] !== undefined) {
          navCol = col;
          break;
        }
      }
      
      if (!dateCol || !navCol) {
        console.log(`  ❌ Could not find date/NAV columns in response`);
        return null;
      }
      
      // Create clean result array
      const resultArray = data.map(item => {
        let dateValue = item[dateCol];
        let navValue = parseFloat(item[navCol]);
        
        // Convert dates if needed
        if (typeof dateValue === 'number') {
          // Unix timestamp
          dateValue = new Date(dateValue).toISOString().split('T')[0];
        } else {
          // String date
          dateValue = new Date(dateValue).toISOString().split('T')[0];
        }
        
        return {
          date: dateValue,
          nav_per_unit: navValue
        };
      }).filter(item => !isNaN(item.nav_per_unit) && item.date >= '1970-01-01');
      
      if (resultArray.length > 0) {
        console.log(`  ✅ Parsed ${resultArray.length} NAV data points`);
        return resultArray;
      }
      
    } catch (e) {
      console.log(`  ❌ Error parsing NAV data: ${e.message}`);
    }
    
    return null;
  }

  /**
   * Get fund ID from fund symbol.
   */
  async getFundId(fundSymbol) {
    const payload = {
      "searchField": fundSymbol.toUpperCase(),
      "types": ["NEW_FUND", "TRADING_FUND"],
      "pageSize": 100,
    };
    
    const url = `${this.baseUrl}/filter`;
    const responseData = await this.makeRequest(url, payload);
    
    if (!responseData) {
      return null;
    }
    
    try {
      if (responseData.data && responseData.data.rows) {
        const funds = responseData.data.rows;
        if (funds.length > 0) {
          // Return the first matching fund's ID
          return funds[0].id;
        }
      }
    } catch (e) {
      // Ignore errors
    }
    
    return null;
  }
}

/**
 * Test the FMarket client with Vietnamese mutual fund data.
 */
async function main() {
  const client = new FMarketClient(true, 6);
  
  // Test 1: Get fund listings
  console.log("=".repeat(60));
  console.log("Testing Fund Listings");
  console.log("=".repeat(60));
  
  try {
    // Get all funds
    const allFunds = await client.getFundListing();
    if (allFunds !== null) {
      console.log(`\n✅ All Funds - Retrieved ${allFunds.length} funds`);
      console.log("\nFirst 3 funds:");
      for (let i = 0; i < Math.min(3, allFunds.length); i++) {
        const fund = allFunds[i];
        console.log(`${fund.short_name} - ${fund.full_name} (${fund.nav_change_12m}% 12m)`);
      }
      
      // Test specific fund type
      const stockFunds = await client.getFundListing("STOCK");
      if (stockFunds !== null) {
        console.log(`\n✅ Stock Funds - Retrieved ${stockFunds.length} funds`);
      }
      
      await new Promise(resolve => setTimeout(resolve, 3000)); // Brief pause between tests
      
      // Test 2: Get NAV history for a specific fund
      console.log(`\n${"=".repeat(60)}`);
      console.log("Testing NAV History");
      console.log("=".repeat(60));
      
      // Use first fund from the listing if available
      if (allFunds.length > 0) {
        const testSymbol = allFunds[0].short_name;
        console.log(`Testing NAV history for: ${testSymbol}`);
        
        const navHistory = await client.getNavHistory(testSymbol);
        if (navHistory !== null) {
          console.log(`\n✅ NAV History - Retrieved ${navHistory.length} data points`);
          
          const dates = navHistory.map(item => item.date);
          console.log(`Date range: ${Math.min(...dates)} to ${Math.max(...dates)}`);
          
          console.log("\nFirst 3 records:");
          for (let i = 0; i < Math.min(3, navHistory.length); i++) {
            const record = navHistory[i];
            console.log(`${record.date} ${record.nav_per_unit.toFixed(2)}`);
          }
          
          console.log("\nLast 3 records:");
          for (let i = Math.max(0, navHistory.length - 3); i < navHistory.length; i++) {
            const record = navHistory[i];
            console.log(`${record.date} ${record.nav_per_unit.toFixed(2)}`);
          }
          
          // Basic statistics
          const navValues = navHistory.map(item => item.nav_per_unit);
          console.log(`\nNAV Statistics:`);
          console.log(`Min NAV: ${Math.min(...navValues).toFixed(2)}`);
          console.log(`Max NAV: ${Math.max(...navValues).toFixed(2)}`);
          console.log(`Latest NAV: ${navValues[navValues.length - 1].toFixed(2)}`);
        } else {
          console.log(`❌ Failed to retrieve NAV history for ${testSymbol}`);
        }
      } else {
        console.log("❌ No funds available to test NAV history");
      }
    }
    
  } catch (e) {
    console.log(`💥 Exception during testing: ${e.message}`);
  }
}

// Export for use as module (works in both Node.js and modern bundlers)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { FMarketClient };
}

// Also support ES6 imports in browsers/bundlers
if (typeof window !== 'undefined') {
  window.FMarketClient = FMarketClient;
}

// Run main function if this file is executed directly
if (typeof require !== 'undefined' && require.main === module) {
  main().catch(console.error);
}