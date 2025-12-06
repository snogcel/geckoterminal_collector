#!/usr/bin/env python3
"""
Test script to verify interval parsing with seconds support.
"""
import re

def validate_interval(interval: str) -> tuple[bool, str]:
    """
    Validate interval format.
    
    Returns:
        Tuple of (is_valid, message)
    """
    if not interval:
        return False, "Interval cannot be empty"
    
    pattern = r'^(\d+)([smhd])$'
    match = re.match(pattern, interval)
    if not match:
        return False, f"Invalid format: {interval}. Expected: number + unit (s/m/h/d)"
    
    number, unit = match.groups()
    number = int(number)
    
    # Validate reasonable ranges
    if unit == 's' and (number < 1 or number > 3600):
        return False, f"Second interval must be between 1 and 3600: {interval}"
    elif unit == 'm' and (number < 1 or number > 1440):
        return False, f"Minute interval must be between 1 and 1440: {interval}"
    elif unit == 'h' and (number < 1 or number > 168):
        return False, f"Hour interval must be between 1 and 168: {interval}"
    elif unit == 'd' and (number < 1 or number > 30):
        return False, f"Day interval must be between 1 and 30: {interval}"
    
    return True, f"Valid: {number} {unit}"

# Test cases
test_intervals = [
    # Valid seconds
    "1s", "15s", "30s", "45s", "60s", "120s", "3600s",
    # Valid minutes
    "1m", "5m", "15m", "30m", "60m",
    # Valid hours
    "1h", "4h", "12h", "24h",
    # Valid days
    "1d", "7d", "30d",
    # Invalid cases
    "0s", "3601s", "0m", "1441m", "0h", "169h", "0d", "31d",
    "abc", "1x", "s1", "1", ""
]

print("🧪 Testing Interval Validation\n")
print("=" * 60)

for interval in test_intervals:
    is_valid, message = validate_interval(interval)
    status = "✅" if is_valid else "❌"
    print(f"{status} '{interval:10s}' - {message}")

print("\n" + "=" * 60)
print("\n📊 Recommended intervals for 30 calls/minute API limit:")
print("   15s = 4 calls/min (13% of limit)")
print("   20s = 3 calls/min (10% of limit)")
print("   30s = 2 calls/min (7% of limit)")
print("   1m  = 1 call/min  (3% of limit)")
