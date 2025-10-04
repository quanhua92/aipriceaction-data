# Multi-Language Packages

This folder contains implementations of AI Price Action analysis in multiple programming languages, all producing identical results.

## Structure

```
packages/
├── python/              # Python implementation (numpy/pandas)
│   ├── ✅ Example 01 - VNINDEX + MA values
│   ├── ✅ Example 02 - Multi-ticker with MA scores
│   └── ✅ Example 03 - Money flow analysis
└── rust/                # 🔮 Future: Rust implementation
```

## Python Package

High-performance vectorized stock market analysis using NumPy/Pandas.

**Status:** All 3 examples complete! 🎉

See [`python/README.md`](python/README.md) for details.

### Quick Start

```bash
cd packages/python
uv venv
uv pip install -r requirements.txt
uv run python examples/01_basic_data.py
```

## Future: Rust Package

Ultra-high performance implementation using Rust with SIMD optimizations.

## Design Goals

1. **Exact Match**: All implementations produce identical results (within floating-point precision)
2. **Performance**: Each language optimized for maximum speed
3. **Maintainability**: Clear code structure matching the original TypeScript
4. **Testability**: Comprehensive validation against TypeScript examples
