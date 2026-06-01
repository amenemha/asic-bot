BLOCK_REWARD = 3.125

def calc(th, watts, kwh_price, asic_price, btc_usd_v, usd_rub_v, diff):
    btc_day = (th * 1e12 * 86400 / (diff * 2**32)) * BLOCK_REWARD
    usd_day = btc_day * btc_usd_v if btc_usd_v else 0
    rub_day = usd_day * usd_rub_v if usd_rub_v else 0
    elec_day = (watts / 1000) * 24 * kwh_price if kwh_price else 0
    profit_day = rub_day - elec_day
    payback_days = (asic_price / profit_day) if (asic_price and profit_day > 0) else None
    return {
        "btc_day": btc_day,
        "usd_day": usd_day,
        "rub_day": rub_day,
        "elec_day": elec_day,
        "profit_day": profit_day,
        "month": profit_day * 30,
        "year": profit_day * 365,
        "payback_days": payback_days,
    }
