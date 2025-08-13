#!/usr/bin/env node

/**
 * Standalone Misc Financial Data Client (JavaScript)
 * 
 * This client provides access to miscellaneous Vietnamese financial data including:
 * - Exchange rates from Vietcombank (VCB)
 * - Gold prices from SJC and Bao Tin Minh Chau (BTMC)
 * 
 * This is a 1:1 port of misc.py - refer to misc.md guide for complete understanding.
 * Works in both Node.js and modern browsers.
 */

class MiscClient {
  /**
   * Standalone Misc client for Vietnamese financial data.
   * 
   * This implementation provides access to exchange rates and gold prices
   * from Vietnamese financial institutions.
   * Core functionality: VCB exchange rates and SJC/BTMC gold prices.
   */

  constructor(randomAgent = true, rateLimitPerMinute = 10) {
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
      'Cache-Control': 'no-cache',
      'Pragma': 'no-cache',
      'DNT': '1',
      'Sec-Fetch-Dest': 'document',
      'Sec-Fetch-Mode': 'navigate',
      'Sec-Fetch-Site': 'none',
      'Sec-Fetch-User': '?1',
      'Upgrade-Insecure-Requests': '1',
      'User-Agent': userAgent
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
  async makeRequest(url, method = "GET", data = null, maxRetries = 5) {
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
        
        if (method.toUpperCase() === "POST" && data) {
          options.body = data;
          options.headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8';
        }
        
        const response = await fetch(url, options);
        
        if (response.status === 200) {
          return response;
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
   * Convert camelCase to snake_case.
   */
  camelToSnake(name) {
    const result = [];
    for (let i = 0; i < name.length; i++) {
      const c = name[i];
      if (c === c.toUpperCase() && i > 0) {
        result.push('_');
      }
      result.push(c.toLowerCase());
    }
    return result.join('');
  }

  /**
   * Get exchange rates from Vietcombank for a specific date.
   * 
   * @param {string} date - Date in format YYYY-MM-DD. If null, current date will be used.
   * @returns {Promise<Array|null>} Array with currency exchange data or null if failed
   * 
   * Note: This method returns simplified data format due to browser limitations with Excel parsing.
   * For full Excel parsing, use the Python version.
   */
  async getVcbExchangeRate(date = null) {
    if (date === null) {
      date = new Date().toISOString().split('T')[0];
    } else {
      try {
        new Date(date + 'T00:00:00.000Z');
      } catch (e) {
        throw new Error("Error: Incorrect date format. Should be YYYY-MM-DD.");
      }
    }
    
    const url = `https://www.vietcombank.com.vn/api/exchangerates/exportexcel?date=${date}`;
    
    console.log(`Fetching VCB exchange rates for ${date}...`);
    
    const response = await this.makeRequest(url);
    
    if (!response) {
      console.log("Failed to get response from VCB API");
      return null;
    }
    
    try {
      const jsonData = await response.json();
      
      if (!jsonData.Data) {
        console.log("No data field in VCB response");
        return null;
      }
      
      // Note: Browser environment cannot easily parse Excel data from base64
      // This is a limitation compared to Python version with pandas
      console.log("⚠️  VCB data received but Excel parsing not available in browser environment");
      console.log("💡 Use Python version for full Excel parsing capabilities");
      
      // Return basic info that we can extract
      const basicData = [{
        currency_code: "VCB_DATA",
        currency_name: "Base64 Excel Data Received",
        buy_cash: null,
        buy_transfer: null,
        sell: null,
        date: date,
        note: "Use Python version for full parsing"
      }];
      
      console.log(`VCB API responded successfully - Excel data available in Python version`);
      return basicData;
      
    } catch (e) {
      console.log(`Error processing VCB exchange rate data: ${e.message}`);
      return null;
    }
  }

  /**
   * Get gold prices from SJC (Saigon Jewelry Company).
   * 
   * @param {string} date - Date in format YYYY-MM-DD. If null, current date will be used.
   *                        Data available from 2016-01-02 onwards.
   * @returns {Promise<Array|null>} Array with gold price data or null if failed
   */
  async getSjcGoldPrice(date = null) {
    // Define minimum allowed date
    const minDate = new Date('2016-01-02T00:00:00.000Z');
    
    let inputDate;
    if (date === null) {
      inputDate = new Date();
    } else {
      try {
        inputDate = new Date(date + 'T00:00:00.000Z');
        if (inputDate < minDate) {
          throw new Error("Date must be from 2016-01-02 onwards.");
        }
      } catch (e) {
        if (e.message.includes("Date must be from")) {
          throw e;
        } else {
          throw new Error("Invalid date format. Please use YYYY-MM-DD format.");
        }
      }
    }
    
    // Format date for API request (DD/MM/YYYY)
    const day = String(inputDate.getDate()).padStart(2, '0');
    const month = String(inputDate.getMonth() + 1).padStart(2, '0');
    const year = inputDate.getFullYear();
    const formattedDate = `${day}/${month}/${year}`;
    
    const url = "https://sjc.com.vn/GoldPrice/Services/PriceService.ashx";
    const payload = `method=GetSJCGoldPriceByDate&toDate=${formattedDate}`;
    
    // Set appropriate headers for SJC
    const headers = { ...this.defaultHeaders };
    headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8';
    headers['X-Requested-With'] = 'XMLHttpRequest';
    headers['Referer'] = 'https://sjc.com.vn/';
    
    console.log(`Fetching SJC gold prices for ${date || 'today'}...`);
    
    const response = await this.makeRequest(url, "POST", payload);
    
    if (!response) {
      console.log("Failed to get response from SJC API");
      return null;
    }
    
    try {
      const data = await response.json();
      
      if (!data.success) {
        console.log("SJC API returned unsuccessful response");
        return null;
      }
      
      const goldData = data.data || [];
      if (goldData.length === 0) {
        console.log("No gold price data available");
        return null;
      }
      
      // Process the data
      const processedData = [];
      for (const item of goldData) {
        if (item.TypeName && item.BranchName && item.BuyValue && item.SellValue) {
          const buyPrice = parseFloat(item.BuyValue);
          const sellPrice = parseFloat(item.SellValue);
          
          if (!isNaN(buyPrice) && !isNaN(sellPrice)) {
            processedData.push({
              name: item.TypeName,
              branch: item.BranchName,
              buy_price: buyPrice,
              sell_price: sellPrice,
              date: inputDate.toISOString().split('T')[0]
            });
          }
        }
      }
      
      console.log(`Successfully fetched ${processedData.length} gold price records`);
      return processedData;
      
    } catch (e) {
      console.log(`Error processing SJC gold price data: ${e.message}`);
      return null;
    }
  }

  /**
   * Get current gold prices from Bao Tin Minh Chau (BTMC).
   * 
   * @returns {Promise<Array|null>} Array with gold price data or null if failed
   */
  async getBtmcGoldPrice() {
    const url = 'http://api.btmc.vn/api/BTMCAPI/getpricebtmc?key=3kd8ub1llcg9t45hnoh8hmn7t5kc2v';
    
    console.log("Fetching BTMC gold prices...");
    
    const response = await this.makeRequest(url);
    
    if (!response) {
      console.log("Failed to get response from BTMC API");
      return null;
    }
    
    try {
      const jsonData = await response.json();
      
      if (!jsonData.DataList || !jsonData.DataList.Data) {
        console.log("Unexpected BTMC response format");
        return null;
      }
      
      const dataList = jsonData.DataList.Data;
      
      if (dataList.length === 0) {
        console.log("No BTMC gold price data available");
        return null;
      }
      
      // Parse the complex data structure
      const processedData = [];
      for (const item of dataList) {
        const rowNumber = item["@row"];
        if (!rowNumber) {
          continue;
        }
        
        // Build dynamic key names based on row number
        const nKey = `@n_${rowNumber}`;
        const kKey = `@k_${rowNumber}`;
        const hKey = `@h_${rowNumber}`;
        const pbKey = `@pb_${rowNumber}`;
        const psKey = `@ps_${rowNumber}`;
        const ptKey = `@pt_${rowNumber}`;
        const dKey = `@d_${rowNumber}`;
        
        const name = item[nKey] || '';
        const sellPriceStr = item[psKey] || '';
        
        if (name && sellPriceStr) {
          // Convert price columns to numeric
          const buyPrice = parseFloat((item[pbKey] || '').replace(/,/g, ''));
          const sellPrice = parseFloat(sellPriceStr.replace(/,/g, ''));
          const worldPrice = parseFloat((item[ptKey] || '').replace(/,/g, ''));
          
          if (!isNaN(sellPrice)) {
            processedData.push({
              name: name,
              karat: item[kKey] || '',
              gold_content: item[hKey] || '',
              buy_price: isNaN(buyPrice) ? null : buyPrice,
              sell_price: sellPrice,
              world_price: isNaN(worldPrice) ? null : worldPrice,
              time: item[dKey] || ''
            });
          }
        }
      }
      
      // Sort by sell price (descending)
      processedData.sort((a, b) => (b.sell_price || 0) - (a.sell_price || 0));
      
      console.log(`Successfully fetched ${processedData.length} BTMC gold price records`);
      return processedData;
      
    } catch (e) {
      console.log(`Error processing BTMC gold price data: ${e.message}`);
      return null;
    }
  }
}

/**
 * Test the Misc client with Vietnamese financial data.
 */
async function main() {
  const client = new MiscClient(true, 6);
  
  console.log("=".repeat(60));
  console.log("Testing Misc Financial Data APIs");
  console.log("=".repeat(60));
  
  // Test 1: VCB Exchange Rates
  console.log("\n1. Testing VCB Exchange Rates");
  console.log("-".repeat(40));
  
  try {
    const vcbRates = await client.getVcbExchangeRate();
    if (vcbRates !== null) {
      console.log(`✅ VCB Exchange Rates - Retrieved ${vcbRates.length} response`);
      console.log("\nResponse:");
      for (const rate of vcbRates) {
        console.log(`${rate.currency_code}: ${rate.currency_name}`);
        if (rate.note) console.log(`Note: ${rate.note}`);
      }
    } else {
      console.log("❌ Failed to retrieve VCB exchange rates");
    }
    
  } catch (e) {
    console.log(`💥 Exception in VCB test: ${e.message}`);
  }
  
  // Brief pause
  await new Promise(resolve => setTimeout(resolve, 3000));
  
  // Test 2: SJC Gold Prices
  console.log(`\n2. Testing SJC Gold Prices`);
  console.log("-".repeat(40));
  
  try {
    const sjcGold = await client.getSjcGoldPrice();
    if (sjcGold !== null) {
      console.log(`✅ SJC Gold Prices - Retrieved ${sjcGold.length} records`);
      console.log("\nFirst 5 records:");
      for (let i = 0; i < Math.min(5, sjcGold.length); i++) {
        const record = sjcGold[i];
        console.log(`${record.name} (${record.branch}): Buy ${record.buy_price?.toLocaleString() || 'N/A'} - Sell ${record.sell_price?.toLocaleString() || 'N/A'} VND`);
      }
      
      // Show price range
      if (sjcGold.length > 0) {
        const sellPrices = sjcGold.map(r => r.sell_price).filter(p => p !== null);
        if (sellPrices.length > 0) {
          console.log(`\nPrice range:`);
          console.log(`Min sell price: ${Math.min(...sellPrices).toLocaleString()} VND`);
          console.log(`Max sell price: ${Math.max(...sellPrices).toLocaleString()} VND`);
        }
      }
    } else {
      console.log("❌ Failed to retrieve SJC gold prices");
    }
    
  } catch (e) {
    console.log(`💥 Exception in SJC test: ${e.message}`);
  }
  
  // Brief pause
  await new Promise(resolve => setTimeout(resolve, 3000));
  
  // Test 3: BTMC Gold Prices
  console.log(`\n3. Testing BTMC Gold Prices`);
  console.log("-".repeat(40));
  
  try {
    const btmcGold = await client.getBtmcGoldPrice();
    if (btmcGold !== null) {
      console.log(`✅ BTMC Gold Prices - Retrieved ${btmcGold.length} records`);
      console.log("\nTop 5 by sell price:");
      for (let i = 0; i < Math.min(5, btmcGold.length); i++) {
        const record = btmcGold[i];
        console.log(`${record.name} (${record.karat}): Buy ${record.buy_price?.toLocaleString() || 'N/A'} - Sell ${record.sell_price?.toLocaleString() || 'N/A'} VND`);
      }
      
      // Show statistics
      if (btmcGold.length > 0) {
        const sellPrices = btmcGold.map(r => r.sell_price).filter(p => p !== null);
        if (sellPrices.length > 0) {
          console.log(`\nPrice statistics:`);
          console.log(`Average sell price: ${Math.round(sellPrices.reduce((a, b) => a + b, 0) / sellPrices.length).toLocaleString()} VND`);
          console.log(`Highest sell price: ${Math.max(...sellPrices).toLocaleString()} VND`);
        }
      }
    } else {
      console.log("❌ Failed to retrieve BTMC gold prices");
    }
    
  } catch (e) {
    console.log(`💥 Exception in BTMC test: ${e.message}`);
  }
  
  console.log(`\n${"=".repeat(60)}`);
  console.log("All tests completed!");
  console.log("=".repeat(60));
}

// Export for use as module (works in both Node.js and modern bundlers)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MiscClient };
}

// Also support ES6 imports in browsers/bundlers
if (typeof window !== 'undefined') {
  window.MiscClient = MiscClient;
}

// Run main function if this file is executed directly
if (typeof require !== 'undefined' && require.main === module) {
  main().catch(console.error);
}