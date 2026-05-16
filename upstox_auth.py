"""
Upstox OAuth2 authentication helper.
Run this file directly to get a fresh access token.
"""
import requests
import webbrowser
from urllib.parse import urlencode
import config

AUTH_URL  = "https://api.upstox.com/v2/login/authorization/dialog"
TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"


def get_auth_url() -> str:
    params = {
        "client_id":     config.API_KEY,
        "redirect_uri":  config.REDIRECT_URI,
        "response_type": "code",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(auth_code: str) -> dict:
    payload = {
        "code":          auth_code,
        "client_id":     config.API_KEY,
        "client_secret": config.API_SECRET,
        "redirect_uri":  config.REDIRECT_URI,
        "grant_type":    "authorization_code",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    r = requests.post(TOKEN_URL, data=payload, headers=headers)
    if not r.ok:
        print(f"\n❌ Error {r.status_code}: {r.text}\n")
    r.raise_for_status()
    return r.json()


def get_headers(token: str = None) -> dict:
    t = token or config.ACCESS_TOKEN
    return {
        "Authorization": f"Bearer {t}",
        "Accept":        "application/json",
    }


if __name__ == "__main__":
    print("=" * 60)
    print("  Upstox Access Token Generator")
    print("=" * 60)
    url = get_auth_url()
    print(f"\nStep 1: Opening login URL in browser...\n{url}")
    webbrowser.open(url)
    print("\nStep 2: After login, copy the 'code' from the redirect URL")
    print("  Example redirect: http://localhost:8501?code=XXXXXXXX\n")
    code = input("Paste the code here: ").strip()
    tokens = exchange_code_for_token(code)
    access_token = tokens.get("access_token", "")
    print(f"\n✅ Access Token:\n{access_token}")
    print(f"\nCopy this into your .env file as:")
    print(f"UPSTOX_ACCESS_TOKEN={access_token}")
    print("\nNote: Token is valid for the current trading day only.")
