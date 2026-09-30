# ============================================================
# REAL BYBIT MAX LEVERAGE
# ============================================================

def get_real_leverage(symbol):

    symbol = normalize_symbol(symbol)

    try:
        url = (
            "https://api.bybit.com/v5/market/instruments-info"
            f"?category=linear&symbol={symbol}USDT"
        )

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        data = r.json()

        if data.get("retCode") != 0:
            return "N/A"

        items = data.get("result", {}).get("list", [])

        if not items:
            return "N/A"

        leverage_filter = items[0].get("leverageFilter", {})

        max_leverage = leverage_filter.get("maxLeverage")

        if max_leverage is None:
            return "N/A"

        return f"{float(max_leverage):g}x"

    except Exception:
        return "N/A"
