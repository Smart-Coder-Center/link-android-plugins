#!/usr/bin/env python3
"""Verify that host R8 rules preserve every external AndroidX DEX reference."""
import argparse
import json
import re
import sys
from pathlib import Path

def descriptor_type(value):
    if value.startswith("["):
        return descriptor_type(value[1:]) + "[]"
    if value.startswith("L"):
        return value[1:-1].replace("/", ".")
    primitives = {
        "V": "void", "Z": "boolean", "B": "byte", "S": "short",
        "C": "char", "I": "int", "J": "long", "F": "float", "D": "double",
    }
    if value not in primitives:
        raise ValueError(f"Unknown DEX type descriptor: {value}")
    return primitives[value]

def parse_arguments(descriptor):
    result = []
    cursor = 0
    while cursor < len(descriptor):
        start = cursor
        while cursor < len(descriptor) and descriptor[cursor] == "[":
            cursor += 1
        if cursor >= len(descriptor):
            raise ValueError(f"Truncated argument descriptor: {descriptor}")
        if descriptor[cursor] == "L":
            end = descriptor.find(";", cursor)
            if end < 0:
                raise ValueError(f"Unterminated object descriptor: {descriptor}")
            cursor = end + 1
        else:
            cursor += 1
        result.append(descriptor_type(descriptor[start:cursor]))
    return ", ".join(result)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--rules", required=True, type=Path)
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    rules = args.rules.read_text(encoding="utf-8")
    if audit.get("audit_mode") != "baseline-guarded" or audit.get("baseline_matches") is not True:
        raise SystemExit("AndroidX DEX audit is not baseline-verified; refusing host integration check")

    blocks = {}
    pattern = re.compile(
        r"(?m)^\s*-keep\s+(?:class|interface|@interface)\s+"
        r"([A-Za-z_$][\w.$]*)\s*\{([^}]*)\}"
    )
    for match in pattern.finditer(rules):
        blocks.setdefault(match.group(1), []).append(match.group(2))

    missing_classes = []
    for descriptor in audit.get("external_androidx_classes", []):
        owner = descriptor[1:-1].replace("/", ".")
        if owner not in blocks:
            missing_classes.append(owner)

    missing_methods = []
    for item in audit.get("method_references", []):
        owner_descriptor, signature = item.split(" -> ", 1)
        owner = owner_descriptor[1:-1].replace("/", ".")
        name, rest = signature.split("(", 1)
        arguments, _return_type = rest.split(")", 1)
        expected = f"{name}({parse_arguments(arguments)});"
        owner_blocks = blocks.get(owner, [])
        if not any("*;" in block or expected in block for block in owner_blocks):
            missing_methods.append(f"{owner} -> {expected}")

    missing_fields = []
    for item in audit.get("field_references", []):
        owner_descriptor, signature = item.split(" -> ", 1)
        owner = owner_descriptor[1:-1].replace("/", ".")
        name = signature.split(":", 1)[0]
        owner_blocks = blocks.get(owner, [])
        if not any("*;" in block or re.search(rf"\b{re.escape(name)}\s*;", block)
                   for block in owner_blocks):
            missing_fields.append(f"{owner} -> {name}")

    errors = []
    if missing_classes:
        errors.append("Missing class/interface keep rules:\n  " + "\n  ".join(missing_classes))
    if missing_methods:
        errors.append("Missing externally referenced methods:\n  " + "\n  ".join(missing_methods))
    if missing_fields:
        errors.append("Missing externally referenced fields:\n  " + "\n  ".join(missing_fields))
    if errors:
        raise SystemExit("\n\n".join(errors))

    print(
        "ANDROIDX_KEEP_RULE_COVERAGE_OK "
        f"classes={len(audit.get('external_androidx_classes', []))} "
        f"methods={len(audit.get('method_references', []))} "
        f"fields={len(audit.get('field_references', []))}"
    )

if __name__ == "__main__":
    main()
