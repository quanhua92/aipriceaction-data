"""Validation utilities"""


def validate_with_tolerance(actual: float, expected: float, tolerance: float = 0.05, label: str = "") -> bool:
    """Validate value with tolerance"""
    diff = abs(actual - expected)
    allowed_diff = abs(expected) * tolerance
    is_valid = diff <= allowed_diff

    if is_valid:
        print(f"✅ {label}: {actual} (expected: {expected}) - PASS")
    else:
        print(f"❌ {label}: {actual} (expected: {expected}, diff: {diff:.2f}, max allowed: {allowed_diff:.2f}) - FAIL")

    return is_valid
