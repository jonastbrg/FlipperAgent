#!/usr/bin/env python3
"""Validate YAML frontmatter in OpenCode agent definition files."""
import sys, yaml, glob, re
from pathlib import Path

REQUIRED_FIELDS = ["description", "mode"]
VALID_MODES = ["primary", "subagent", "all"]

def validate_agent(path):
    text = Path(path).read_text()
    # Extract YAML between first two ---
    match = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
    if not match:
        return f"FAIL: {path} — no YAML frontmatter found"
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        return f"FAIL: {path} — invalid YAML: {e}"
    if not isinstance(data, dict):
        return f"FAIL: {path} — frontmatter is not a dict"
    for field in REQUIRED_FIELDS:
        if field not in data:
            return f"FAIL: {path} — missing required field: {field}"
    if "mode" in data and data["mode"] not in VALID_MODES:
        return f"FAIL: {path} — invalid mode: {data['mode']} (must be {VALID_MODES})"
    return f"OK: {path}"

def main():
    files = sorted(glob.glob(".opencode/agents/*.md"))
    if not files:
        print("No agent files found in .opencode/agents/")
        sys.exit(1)
    errors = 0
    for f in files:
        result = validate_agent(f)
        print(result)
        if result.startswith("FAIL"):
            errors += 1
    print(f"\n{len(files)} files checked, {errors} errors")
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
