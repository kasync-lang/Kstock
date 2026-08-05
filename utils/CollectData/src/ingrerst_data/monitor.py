
import aiohttp
import os
from collections import defaultdict
import logging
logger = logging.getLogger(__name__)
import asyncio
import time
import dotenv
from datetime import timedelta, datetime
stats = defaultdict(lambda :{
    "count": 0,
    "last_ts":None,
})

socket_stats = {
    1: {
        "last_receive": None,
        "count": 0,
    },
    2: {
        "last_receive": None,
        "count": 0,
    },
    3: {
        "last_receive": None,
        "count": 0,
    },
    4: {
        "last_receive": None,
        "count": 0,
    },
}
async def is_market_open() -> bool:
    url = os.getenv("MARKET_STATUS_URL")
    if not url:
        raise RuntimeError("MARKET_STATUS_URL is not configured")

    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json()

    try:
        return bool(data["isOpen"])
    except KeyError as exc:
        raise ValueError("Market-status response is missing 'isOpen'") from exc
# format message
# {
#      "p": 7296.89,
#      "s": "BINANCE:BTCUSDT",
#      "t": 1575526691134,
#      "v": 0.011467
# }
async def on_trade_monitor(message):
    s = stats[message["s"]]
    s['count'] += 1
    s['last_ts'] = time.time()

async def on_receive_socket(socket_id):
    socket_stats[socket_id]["count"] += 1
    socket_stats[socket_id]["last_receive"] = datetime.now()
async def report(list_symbol:list[int]):
    while True:
        await asyncio.sleep(300)
        try:
            market_open = await is_market_open()
        except (
                RuntimeError,
                aiohttp.ClientError,
                asyncio.TimeoutError,
                ValueError,
        ):
            logger.exception(
                "Cannot retrieve market status; skipping this monitoring cycle"
            )
            continue

        if not market_open:
            logger.info("Market is closed; skipping this monitoring cycle")
            continue
        logger.info("="*80)
        # clear stats
        missing_symbols = []
        #time in milisecond
        now = int(time.time() * 1000)
        for socket_id, stat1 in socket_stats.items():
            logger.info(
                "Socket %d count=%d last=%s",
                socket_id,
                stat1["count"],
                stat1["last_receive"],
            )

            stat1["count"] = 0
        for symbol in list_symbol:
            s = stats[symbol]
            count = s['count']
            last = s['last_ts']
            logger.info(
                "%-8s count=%-8d last=%s",
                symbol,
                count,
                last,
            )
            if last is None:

                missing_symbols.append((symbol, "Nerver received"))
            elif now - last > 300:
                missing_symbols.append(
                    (symbol, f"Last receive {timedelta(milliseconds=now - last)} ago")
                )
            s['count'] =0
        if missing_symbols:
            logger.warning("=" * 10 + " Missing data " + "=" * 10)
            for symbol, reason in missing_symbols:
                logger.warning("%-8s %s", symbol, reason)
        else:
            logger.info("All subscribed symbols are healthy")
if __name__ == '__main__':
    print(asyncio.run(is_market_open()))
    assert asyncio.run(is_market_open()) == True