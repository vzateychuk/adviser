#!/usr/bin/env python3
"""Direct test of YAML parsing with Windows paths."""
import yaml

print("Testing YAML parsing with Windows paths:\n")
print("=" * 70)

# This is what fails before the fix
problematic_yaml = '''input: "docs\\medocs\\file.txt"'''

print("\nTest 1: Double-quoted string with backslashes (BEFORE FIX)")
print(f"YAML: {problematic_yaml}")
try:
    data = yaml.safe_load(problematic_yaml)
    print("✓ Parsed OK")
    print(f"  Value: {data}")
except yaml.YAMLError as e:
    print(f"✗ FAILED to parse: {e}")

# This is what works after the fix
fixed_yaml = '''input: 'docs\\medocs\\file.txt\''''

print("\n" + "=" * 70)
print("\nTest 2: Single-quoted string with backslashes (AFTER FIX)")
print(f"YAML: {fixed_yaml}")
try:
    data = yaml.safe_load(fixed_yaml)
    print("✓ Parsed OK")
    print(f"  Value: {data['input']}")
except yaml.YAMLError as e:
    print(f"✗ FAILED to parse: {e}")

# Show the character-by-character difference
print("\n" + "=" * 70)
print("\nKey difference:")
print(f"  Double-quoted: YAML interprets escape sequences like \\m, \\d → ERROR")
print(f"  Single-quoted: YAML treats backslash literally → OK ✓")
print("\nOur fix converts: \"path\\with\\backslashes\" → 'path\\with\\backslashes'")
