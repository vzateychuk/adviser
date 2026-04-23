#!/usr/bin/env python
"""Quick test for Windows path YAML fix."""
from flows.pec.yaml_utils import sanitize_llm_yaml, load_llm_yaml

# Test case: Windows path that caused the original error
problematic_yaml = '''goal: Triage and extract
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
      - Preserve all values
'''

print("Original YAML:")
print(problematic_yaml)
print("\n" + "="*60)

print("\nSanitized YAML:")
sanitized = sanitize_llm_yaml(problematic_yaml)
print(sanitized)
print("\n" + "="*60)

print("\nParsing...")
try:
    data = load_llm_yaml(problematic_yaml)
    print("✓ SUCCESS! Parsed without error")
    print(f"Schema: {data['schema_name']}")
    print(f"Input path: {data['steps'][0]['input']}")
except ValueError as e:
    print(f"✗ FAILED: {e}")
