#!/usr/bin/env python3
"""Test for Windows path YAML parsing fix."""
import sys
import yaml
from flows.pec.yaml_utils import sanitize_llm_yaml

def test_windows_path_conversion():
    """Test that Windows paths in double quotes are converted to single quotes."""
    
    # The problematic input that caused the error
    yaml_with_windows_path = '''goal: Triage document
action: PLAN
schema_name: lab
assumptions: []
steps:
  - id: 1
    title: Extract lab data
    type: ocr
    input: "docs\\medocs\\Затейчук В.Е. 2025.04.16"
    output: lab
    success_criteria:
      - Preserve all dates
'''

    print("=" * 70)
    print("TEST 1: Windows path with backslashes")
    print("=" * 70)
    print("\nOriginal YAML (problematic):")
    print(yaml_with_windows_path)
    
    sanitized = sanitize_llm_yaml(yaml_with_windows_path)
    print("\nSanitized YAML:")
    print(sanitized)
    
    print("\nParsing sanitized YAML...")
    try:
        data = yaml.safe_load(sanitized)
        input_value = data['steps'][0]['input']
        print(f"✓ SUCCESS! Parsed without error")
        print(f"  Input path: {input_value}")
        assert input_value == "docs\\medocs\\Затейчук В.Е. 2025.04.16"
        print(f"  Value preserved correctly!")
    except yaml.YAMLError as e:
        print(f"✗ FAILED: {e}")
        return False

    print("\n" + "=" * 70)
    print("TEST 2: Normal YAML without backslashes (should be unchanged)")
    print("=" * 70)
    
    normal_yaml = '''goal: Extract data
action: PLAN
schema_name: lab
input: "normal string without backslashes"
'''
    
    print("\nOriginal YAML:")
    print(normal_yaml)
    
    sanitized = sanitize_llm_yaml(normal_yaml)
    print("Sanitized YAML:")
    print(sanitized)
    
    try:
        data = yaml.safe_load(sanitized)
        print(f"✓ SUCCESS! Parsed normally")
        print(f"  Input: {data['input']}")
    except yaml.YAMLError as e:
        print(f"✗ FAILED: {e}")
        return False

    print("\n" + "=" * 70)
    print("TEST 3: Mixed quotes (double quotes with backslashes)")
    print("=" * 70)
    
    mixed_yaml = '''file1: "C:\\Users\\admin\\file.txt"
file2: "normal_value"
file3: 'already_single_quoted'
'''
    
    print("\nOriginal YAML:")
    print(mixed_yaml)
    
    sanitized = sanitize_llm_yaml(mixed_yaml)
    print("Sanitized YAML:")
    print(sanitized)
    
    try:
        data = yaml.safe_load(sanitized)
        print(f"✓ SUCCESS! Parsed correctly")
        print(f"  file1: {data['file1']}")
        print(f"  file2: {data['file2']}")
        print(f"  file3: {data['file3']}")
    except yaml.YAMLError as e:
        print(f"✗ FAILED: {e}")
        return False

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED ✓")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = test_windows_path_conversion()
    sys.exit(0 if success else 1)
