#!/usr/bin/env python3
"""scripts/router_models.py — Print the smart router's routing table."""

import json
import urllib.request
import urllib.error
import sys

try:
    with urllib.request.urlopen("http://localhost:4001/models", timeout=5) as r:
        d = json.loads(r.read())
    print(f"{'ROUTE':<20} {'MODEL':<30} TRIGGER")
    print("-" * 80)
    for name, info in d["routing_table"].items():
        print(f"{name:<20} {info['model']:<30} {info['triggers']}")
except urllib.error.URLError as e:
    print(f"ERROR: Router not reachable — is the stack running? ({e.reason})")
    sys.exit(1)
