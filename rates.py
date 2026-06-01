import aiohttp, asyncio

async def _get_json(session, url):
    try:
        async with session.get(url, timeout=10) as r:
            return await r.json()
    except Exception:
        return None

async def btc_usd():
    async with aiohttp.ClientSession() as s:
        vals = []
        j = await _get_json(s, "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
        if j and "bitcoin" in j: vals.append(float(j["bitcoin"]["usd"]))
        j = await _get_json(s, "https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USD")
        if j and "USD" in j: vals.append(float(j["USD"]))
        j = await _get_json(s, "https://api.coinbase.com/v2/prices/BTC-USD/spot")
        if j and "data" in j:
            try: vals.append(float(j["data"]["amount"]))
            except: pass
    return sum(vals)/len(vals) if vals else None

async def usd_rub():
    async with aiohttp.ClientSession() as s:
        j = await _get_json(s, "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=rub")
        if j and "tether" in j: return float(j["tether"]["rub"])
        j = await _get_json(s, "https://www.cbr-xml-daily.ru/daily_json.js")
        if j and "Valute" in j: return float(j["Valute"]["USD"]["Value"])
    return None

async def difficulty():
    async with aiohttp.ClientSession() as s:
        j = await _get_json(s, "https://mempool.space/api/v1/difficulty-adjustment")
        if j and "difficulty" in j: return float(j["difficulty"])
        try:
            async with s.get("https://blockchain.info/q/getdifficulty", timeout=10) as r:
                return float(await r.text())
        except Exception:
            return None
