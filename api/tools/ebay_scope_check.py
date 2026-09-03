"""Can this eBay keyset see sold listings?

    set EBAY_CLIENT_ID=...          (Windows)   export EBAY_CLIENT_ID=...   (Mac/Linux)
    set EBAY_CLIENT_SECRET=...                  export EBAY_CLIENT_SECRET=...
    python api/tools/ebay_scope_check.py

Asks eBay for a token under each scope in turn and reports which it grants.
The only one that matters is `buy.marketplace.insights` — the Marketplace
Insights API, which is the sole official source of completed-sale prices and
is granted per keyset by eBay, not by ticking a box. If it comes back with a
token, this also makes one real call and shows a sold price, so there is no
doubt left about what the token can do.

Standard library only, so it runs anywhere Python does. It prints verdicts
and never prints the secret or a token. Pass --sandbox for a sandbox keyset.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SANDBOX = "--sandbox" in sys.argv
HOST = "api.sandbox.ebay.com" if SANDBOX else "api.ebay.com"
TOKEN_URL = f"https://{HOST}/identity/v1/oauth2/token"

SCOPES = [
    ("public data (Browse API — active listings only)",
     "https://api.ebay.com/oauth/api_scope"),
    ("SOLD LISTINGS (Marketplace Insights API — the one that matters)",
     "https://api.ebay.com/oauth/api_scope/buy.marketplace.insights"),
]


def token_for(scope: str, basic: str):
    body = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": scope}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST", headers={
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("access_token"), None
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e)
        except Exception:
            err = {"error": f"http {e.code}"}
        return None, f"{err.get('error')}: {err.get('error_description', '')}".strip(": ")
    except urllib.error.URLError as e:
        return None, f"could not reach eBay: {e.reason}"


def one_sold_price(token: str):
    q = urllib.parse.urlencode({"q": "charizard base set", "limit": "3"})
    req = urllib.request.Request(
        f"https://{HOST}/buy/marketplace_insights/v1_beta/item_sales/search?{q}",
        headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        return f"token granted but the call failed: http {e.code} {e.read()[:200]!r}"
    sales = d.get("itemSales") or []
    if not sales:
        return "token granted; the call worked but returned no sales for the test query"
    s = sales[0]
    price = (s.get("lastSoldPrice") or {})
    return (f"WORKS — e.g. {s.get('title', '?')[:60]!r} sold for "
            f"{price.get('value')} {price.get('currency')} on {s.get('lastSoldDate', '?')[:10]}")


def main() -> int:
    cid = os.environ.get("EBAY_CLIENT_ID", "").strip()
    secret = os.environ.get("EBAY_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        print("set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in the environment first (see the top of this file)")
        return 2
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    print(f"keyset ...{cid[-6:]} against {HOST}\n")

    insights = None
    for label, scope in SCOPES:
        tok, err = token_for(scope, basic)
        print(f"  {'GRANTED' if tok else 'refused'}  {label}")
        if err:
            print(f"           {err}")
        if tok and "marketplace.insights" in scope:
            insights = tok

    print()
    if insights:
        print("Sold listings: YES.", one_sold_price(insights))
        print("Tell Claude 'the insights scope works' — nothing else is needed.")
    else:
        print("Sold listings: NO. This keyset has not been granted buy.marketplace.insights.")
        print("That is the expected answer without eBay business approval; the credentials")
        print("themselves are fine if the public-data line above says GRANTED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
