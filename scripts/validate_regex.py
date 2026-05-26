#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Validate boot registry parser regexes against real show version output.

Usage:
    sccfm-cli inventory devices asa cli execute \
        -q "deviceType:ASA AND connectivityState:ONLINE" \
        -s "show version" --format json | python3 scripts/validate_regex.py
"""
import json
import re
import sys

# Same regexes as asa_boot_registry_parser.py
SYSTEM_IMAGE_RE = re.compile(r'System image file is\s+"([^"]+)"', re.IGNORECASE)
COMPILED_RE = re.compile(r"Compiled on\s+(.+?)(?:\s+by\s+\S+)?\s*$", re.IGNORECASE | re.MULTILINE)
CONFIG_REGISTER_RE = re.compile(r"Configuration register is\s+(0x[\da-fA-F]+)", re.IGNORECASE)
CONFIG_NOT_MODIFIED_RE = re.compile(
    r"Configuration has not been modified since last system restart",
    re.IGNORECASE,
)

data = json.load(sys.stdin)
print(f"Total devices: {len(data)}\n")

fails: list[tuple[str, list[str]]] = []
for d in data:
    uid = d["device_uid"]
    text = d["result"]

    img = SYSTEM_IMAGE_RE.search(text)
    comp = COMPILED_RE.search(text)
    reg = CONFIG_REGISTER_RE.search(text)
    notmod = CONFIG_NOT_MODIFIED_RE.search(text)

    issues: list[str] = []
    if not img:
        issues.append("SYSTEM_IMAGE")
    if not comp:
        issues.append("COMPILED")

    status = "FAIL" if issues else "OK"
    img_val = img.group(1) if img else "MISSING"
    comp_val = comp.group(1).strip() if comp else "MISSING"
    reg_val = reg.group(1) if reg else "N/A (expected for ASAv)"
    mod_val = "not modified" if notmod else "modified"

    print(f"[{status}] {uid}")
    print(f"  image={img_val}")
    print(f"  compiled={comp_val}")
    print(f"  register={reg_val}")
    print(f"  config={mod_val}")

    if issues:
        fails.append((uid, issues))
        for line in text.split("\n"):
            for kw in ["System image", "Compiled", "Configuration register"]:
                if kw.lower() in line.lower():
                    print(f"    RAW: {line.strip()}")

print()
if fails:
    print(f"FAILURES: {len(fails)}/{len(data)}")
    for uid, iss in fails:
        print(f"  {uid}: {', '.join(iss)}")
    sys.exit(1)
else:
    print(f"ALL {len(data)} DEVICES PASSED - all regexes matched")
