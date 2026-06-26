#!/usr/bin/env python3
"""
Cloudflare Cache Purge Script
Usage: python3 scripts/purge_cf_cache.py [--zone-id ZONE_ID]
Env vars: CF_API_TOKEN (must have Zone.Cache.Purge permission)
          CF_ZONE_ID (default: 4a5e0a77d5483837f773bbe390fb2084)
"""
import os, sys, json, urllib.request, urllib.error

CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID", "4a5e0a77d5483837f773bbe390fb2084")

if not CF_API_TOKEN:
    print("❌ CF_API_TOKEN not set. Export it first:")
    print("   export CF_API_TOKEN='cfut_...'")
    sys.exit(1)

# If --zone-id arg provided, override
args = sys.argv[1:]
for i, a in enumerate(args):
    if a == "--zone-id" and i + 1 < len(args):
        CF_ZONE_ID = args[i + 1]

print(f"🧹 Purging ALL cache for Zone: {CF_ZONE_ID}")

url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/purge_cache"
data = json.dumps({"purge_everything": True}).encode("utf-8")

req = urllib.request.Request(url, data=data, method="POST")
req.add_header("Authorization", f"Bearer {CF_API_TOKEN}")
req.add_header("Content-Type", "application/json")

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())
        if result.get("success"):
            print("✅ Cache purged successfully!")
            print(f"   {json.dumps(result.get('result', {}), indent=2)}")
        else:
            errors = result.get("errors", [])
            for e in errors:
                print(f"❌ CF Error {e.get('code')}: {e.get('message')}")
            sys.exit(1)
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"❌ HTTP {e.code}: {body}")
    sys.exit(1)
