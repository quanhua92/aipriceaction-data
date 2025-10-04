#!/bin/bash
# Test all Python examples

echo "🧪 Testing AI Price Action Python Package"
echo "=========================================="
echo ""

# Test Example 01
echo "📊 Testing Example 01: Basic Data (VNINDEX + MA values)..."
uv run python examples/01_basic_data.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Example 01 passed"
else
    echo "❌ Example 01 failed"
    exit 1
fi
echo ""

# Test Example 02
echo "📊 Testing Example 02: Multi-ticker with MA scores..."
uv run python examples/02_multi_data.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Example 02 passed"
else
    echo "❌ Example 02 failed"
    exit 1
fi
echo ""

# Test Example 03
echo "📊 Testing Example 03: Money flow analysis..."
uv run python examples/03_money_flow.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Example 03 passed"
else
    echo "❌ Example 03 failed"
    exit 1
fi
echo ""

echo "=========================================="
echo "🎉 All tests passed successfully!"
echo ""
echo "Package is ready for use. Run individual examples with:"
echo "  uv run python examples/01_basic_data.py"
echo "  uv run python examples/02_multi_data.py"
echo "  uv run python examples/03_money_flow.py"
