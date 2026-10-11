
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


import time
import threading
from dataclasses import dataclass, field

from rich.live import Live
from rich.table import Table


@dataclass
class SocketMetrics:
    connected: bool = False
    messages: int = 0
    last_message_at: float | None = None
    messages_last_second: int = 0

    # dùng để tính messages/sec
    _previous_messages: int = field(default=0, repr=False)

    def record_message(self):
        self.messages += 1
        self.last_message_at = time.time()

    def update_rate(self):
        self.messages_last_second = self.messages - self._previous_messages
        self._previous_messages = self.messages


class SocketMonitor:
    def __init__(self, socket_count: int):
        self.sockets = {
            i: SocketMetrics()
            for i in range(socket_count)
        }

        self.lock = threading.Lock()

    def set_connected(self, socket_id: int, connected: bool):
        with self.lock:
            self.sockets[socket_id].connected = connected

    def record_message(self, socket_id: int):
        with self.lock:
            self.sockets[socket_id].record_message()

    def update_rates(self):
        with self.lock:
            for socket in self.sockets.values():
                socket.update_rate()

    def render(self):
        table = Table(title="WebSocket Monitor")

        table.add_column("Socket")
        table.add_column("Status")
        table.add_column("Messages", justify="right")
        table.add_column("Msg/s", justify="right")
        table.add_column("Last Message")
        table.add_column("Silence", justify="right")

        now = time.time()

        with self.lock:
            for socket_id, metrics in self.sockets.items():

                if metrics.connected:
                    status = "CONNECTED"
                else:
                    status = "DISCONNECTED"

                if metrics.last_message_at is None:
                    last_message = "-"
                    silence = "-"
                else:
                    elapsed = now - metrics.last_message_at
                    last_message = time.strftime(
                        "%H:%M:%S",
                        time.localtime(metrics.last_message_at),
                    )
                    silence = f"{elapsed:.1f}s"

                table.add_row(
                    str(socket_id),
                    status,
                    str(metrics.messages),
                    str(metrics.messages_last_second),
                    last_message,
                    silence,
                )

        return table


def monitor_loop(monitor: SocketMonitor):
    with Live(monitor.render(), refresh_per_second=2) as live:
        while True:
            time.sleep(1)

            monitor.update_rates()
            live.update(monitor.render())
if __name__ == '__main__':
    print(asyncio.run(is_market_open()))
    assert asyncio.run(is_market_open()) == True