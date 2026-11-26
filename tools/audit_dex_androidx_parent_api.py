#!/usr/bin/env python3
"""Audit AndroidX references crossing the downloadable DEX -> host class-loader boundary."""
import hashlib
import json
import re
import sys
from pathlib import Path

DEX_MAGIC = b"dex\n"

def u32(data, offset):
    return int.from_bytes(data[offset:offset + 4], "little")

def uleb(data, offset):
    value = shift = 0
    while True:
        if offset >= len(data):
            raise ValueError("truncated ULEB128")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7f) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
        if shift > 35:
            raise ValueError("invalid ULEB128")

def parse_dex(path):
    data = path.read_bytes()
    if not data.startswith(DEX_MAGIC) or len(data) < 112:
        raise ValueError(f"not a valid DEX file: {path}")
    string_size, string_off = u32(data, 56), u32(data, 60)
    type_size, type_off = u32(data, 64), u32(data, 68)
    proto_size, proto_off = u32(data, 72), u32(data, 76)
    field_size, field_off = u32(data, 80), u32(data, 84)
    method_size, method_off = u32(data, 88), u32(data, 92)
    class_size, class_off = u32(data, 96), u32(data, 100)

    strings = []
    for index in range(string_size):
        offset = u32(data, string_off + 4 * index)
        _, cursor = uleb(data, offset)
        end = data.find(b"\0", cursor)
        if end < 0:
            raise ValueError(f"unterminated DEX string in {path}")
        strings.append(data[cursor:end].decode("utf-8", "replace"))

    types = [strings[u32(data, type_off + 4 * i)] for i in range(type_size)]
    protos = []
    for index in range(proto_size):
        _, return_type, parameters_off = (
            u32(data, proto_off + 12 * index),
            u32(data, proto_off + 12 * index + 4),
            u32(data, proto_off + 12 * index + 8),
        )
        args = []
        if parameters_off:
            count = u32(data, parameters_off)
            args = [
                types[int.from_bytes(data[parameters_off + 4 + 2 * i:
                                           parameters_off + 6 + 2 * i], "little")]
                for i in range(count)
            ]
        protos.append((types[return_type], args))

    defined = {
        types[u32(data, class_off + 32 * index)]
        for index in range(class_size)
    }
    method_refs = set()
    for index in range(method_size):
        base = method_off + 8 * index
        class_index = int.from_bytes(data[base:base + 2], "little")
        proto_index = int.from_bytes(data[base + 2:base + 4], "little")
        name_index = u32(data, base + 4)
        descriptor = types[class_index]
        if descriptor.startswith("Landroidx/") and descriptor not in defined:
            return_type, args = protos[proto_index]
            method_refs.add(
                f"{descriptor} -> {strings[name_index]}({''.join(args)}){return_type}"
            )

    field_refs = set()
    for index in range(field_size):
        base = field_off + 8 * index
        class_index = int.from_bytes(data[base:base + 2], "little")
        type_index = int.from_bytes(data[base + 2:base + 4], "little")
        name_index = u32(data, base + 4)
        descriptor = types[class_index]
        if descriptor.startswith("Landroidx/") and descriptor not in defined:
            field_refs.add(
                f"{descriptor} -> {strings[name_index]}:{types[type_index]}"
            )

    external_classes = {
        descriptor for descriptor in types
        if descriptor.startswith("Landroidx/") and descriptor not in defined
    }
    return external_classes, method_refs, field_refs, hashlib.sha256(data).hexdigest()

def descriptor_type(value):
    if value.startswith("["):
        return descriptor_type(value[1:]) + "[]"
    if value.startswith("L"):
        return value[1:-1].replace("/", ".")
    return {
        "V": "void", "Z": "boolean", "B": "byte", "S": "short",
        "C": "char", "I": "int", "J": "long", "F": "float", "D": "double",
    }[value]

def parse_arguments(descriptor):
    result = []
    cursor = 0
    while cursor < len(descriptor):
        start = cursor
        while descriptor[cursor] == "[":
            cursor += 1
        if descriptor[cursor] == "L":
            cursor = descriptor.index(";", cursor) + 1
        else:
            cursor += 1
        result.append(descriptor_type(descriptor[start:cursor]))
    return result

def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: audit_dex_androidx_parent_api.py <dex-dir> <baseline.json> <output-dir>")
    dex_dir, baseline_path, output_dir = map(Path, sys.argv[1:])
    dex_files = sorted(dex_dir.glob("classes*.dex"),
                       key=lambda p: int(re.search(r"(\d+)?\.dex$", p.name).group(1) or 1))
    if not dex_files:
        raise SystemExit("AndroidX parent API audit found no DEX files")

    classes, methods, fields, dex_hashes = set(), set(), set(), {}
    for dex in dex_files:
        found_classes, found_methods, found_fields, digest = parse_dex(dex)
        classes.update(found_classes)
        methods.update(found_methods)
        fields.update(found_fields)
        dex_hashes[dex.name] = digest

    classes, methods, fields = sorted(classes), sorted(methods), sorted(fields)
    canonical = "\n".join(["CLASSES", *classes, "METHODS", *methods, "FIELDS", *fields]) + "\n"
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    baseline = None if str(baseline_path) == "-" else json.loads(
        baseline_path.read_text(encoding="utf-8")
    )
    expected = baseline["api_fingerprint_sha256"] if baseline else None

    # Always write a reviewable report and generated rules, including on drift.
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "dex_sha256": dex_hashes,
        "external_androidx_classes": classes,
        "method_references": methods,
        "field_references": fields,
        "api_fingerprint_sha256": fingerprint,
        "baseline_fingerprint_sha256": expected,
        "baseline_matches": fingerprint == expected if expected else None,
        "audit_mode": "baseline-guarded" if expected else "report-only",
    }
    (output_dir / "androidx-parent-api-audit.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )

    methods_by_class, fields_by_class = {}, {}
    for item in methods:
        owner, signature = item.split(" -> ", 1)
        name = signature.split("(", 1)[0]
        args = signature.split("(", 1)[1].split(")", 1)[0]
        methods_by_class.setdefault(owner, []).append((name, args))
    for item in fields:
        owner, signature = item.split(" -> ", 1)
        fields_by_class.setdefault(owner, []).append(signature.split(":", 1)[0])

    rules = [
        "# Generated by tools/audit_dex_androidx_parent_api.py.",
        "# Review this file before copying changes into the Android host ProGuard rules.",
    ]
    for descriptor in classes:
        owner = descriptor[1:-1].replace("/", ".")
        members = []
        for name, args in sorted(methods_by_class.get(descriptor, [])):
            params = ", ".join(parse_arguments(args))
            members.append(f"    <init>({params});" if name == "<init>"
                           else f"    *** {name}({params});")
        for name in sorted(fields_by_class.get(descriptor, [])):
            members.append(f"    *** {name};")
        if not members:
            members.append("    *;")
        # The DEX type_ids table does not encode whether an external type is a
        # class, interface or annotation. Emit all legal owner forms; ProGuard
        # applies only the matching form, avoiding a false class-only rule for
        # AndroidX interfaces and lifecycle annotations.
        for kind in ("class", "interface", "@interface"):
            rules.append(f"-keep {kind} {owner} {{")
            rules.extend(members)
            rules.append("}")
    (output_dir / "androidx-parent-api-keep-rules.pro").write_text(
        "\n".join(rules) + "\n", encoding="utf-8"
    )

    print(
        "ANDROIDX_PARENT_API_AUDIT "
        f"classes={len(classes)} methods={len(methods)} fields={len(fields)} "
        f"fingerprint={fingerprint}"
    )
    if expected and fingerprint != expected:
        raise SystemExit(
            "Unreviewed AndroidX parent-classloader API drift detected. "
            "Review provenance/androidx-parent-api-audit.json and the generated "
            "androidx-parent-api-keep-rules.pro, update host ProGuard rules, then "
            "intentionally refresh tools/mlkit-androidx-parent-api-baseline.json."
        )

if __name__ == "__main__":
    main()
