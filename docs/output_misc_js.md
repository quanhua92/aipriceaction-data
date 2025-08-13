============================================================
Testing Misc Financial Data APIs
============================================================

1. Testing VCB Exchange Rates
----------------------------------------
Fetching VCB exchange rates for 2025-08-13...
⚠️  VCB data received but Excel parsing not available in browser environment
💡 Use Python version for full Excel parsing capabilities
VCB API responded successfully - Excel data available in Python version
✅ VCB Exchange Rates - Retrieved 1 response

Response:
VCB_DATA: Base64 Excel Data Received
Note: Use Python version for full parsing

2. Testing SJC Gold Prices
----------------------------------------
Fetching SJC gold prices for today...
Request exception on attempt 1: fetch failed
Retry 1/4 after 1.5s delay...
Successfully fetched 12 gold price records
✅ SJC Gold Prices - Retrieved 12 records

First 5 records:
Vàng SJC 1L, 10L, 1KG (Hồ Chí Minh): Buy 123,000,000 - Sell 124,200,000 VND
Vàng SJC 1L, 10L, 1KG (Miền Bắc): Buy 123,000,000 - Sell 124,200,000 VND
Vàng SJC 1L, 10L, 1KG (Hạ Long): Buy 123,000,000 - Sell 124,200,000 VND
Vàng SJC 1L, 10L, 1KG (Hải Phòng): Buy 123,000,000 - Sell 124,200,000 VND
Vàng SJC 1L, 10L, 1KG (Miền Trung): Buy 123,000,000 - Sell 124,200,000 VND

Price range:
Min sell price: 124,200,000 VND
Max sell price: 124,200,000 VND

3. Testing BTMC Gold Prices
----------------------------------------
Fetching BTMC gold prices...
Successfully fetched 14 BTMC gold price records
✅ BTMC Gold Prices - Retrieved 14 records

Top 5 by sell price:
VÀNG MIẾNG SJC (Vàng SJC) (24k): Buy 12,300,000 - Sell 12,420,000 VND
VÀNG MIẾNG SJC (Vàng SJC) (24k): Buy 12,270,000 - Sell 12,390,000 VND
VÀNG MIẾNG VRTL (Vàng Rồng Thăng Long) (24k): Buy 11,700,000 - Sell 12,000,000 VND
QUÀ MỪNG BẢN VỊ VÀNG (Quà Mừng Bản Vị Vàng) (24k): Buy 11,700,000 - Sell 12,000,000 VND
NHẪN TRÒN TRƠN (Vàng Rồng Thăng Long) (24k): Buy 11,700,000 - Sell 12,000,000 VND

Price statistics:
Average sell price: 10,319,286 VND
Highest sell price: 12,420,000 VND

============================================================
All tests completed!
============================================================
