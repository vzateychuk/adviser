#!/usr/bin/env python3
"""Verify regex pattern for Windows path conversion."""
import re

# The regex pattern from our fix
pattern = r'"([^"]*\\[^"]*?)"'

test_cases = [
    # (input, expected_output, should_match)
    ('input: "docs\\medocs\\file.txt"', "input: 'docs\\medocs\\file.txt'", True),
    ('path: "C:\\Users\\admin"', "path: 'C:\\Users\\admin'", True),
    ('normal: "no backslash here"', 'normal: "no backslash here"', False),
    ('"C:\\path\\to\\file"', "'C:\\path\\to\\file'", True),
    ('field: "docs\\subdir\\file"', "field: 'docs\\subdir\\file'", True),
]

print("Testing regex pattern for Windows path fix:\n")
print(f"Pattern: {pattern}\n")
print("-" * 70)

all_passed = True
for input_str, expected, should_match in test_cases:
    # Apply the substitution
    result = re.sub(pattern, lambda m: f"'{m.group(1)}'", input_str)
    
    matched = result != input_str
    passed = (matched == should_match) and (result == expected if should_match else True)
    
    status = "✓ PASS" if passed else "✗ FAIL"
    all_passed = all_passed and passed
    
    print(f"{status}")
    print(f"  Input:    {input_str}")
    print(f"  Expected: {expected}")
    print(f"  Result:   {result}")
    print(f"  Matched:  {matched} (expected: {should_match})")
    print()

print("-" * 70)
if all_passed:
    print("\n✓ ALL REGEX TESTS PASSED\n")
else:
    print("\n✗ SOME TESTS FAILED\n")
