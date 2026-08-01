import asyncio
import json
from src.ingrerst_data.KafkaProducerClient import KafkaProducerSingleton
import random
import os
import websockets
import dotenv
import logging
from confluent_kafka import Producer, KafkaException
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone, time
import time
logger = logging.getLogger(__name__)
from src.ingrerst_data.monitor import *



# configure basic logging so warnings/exceptions are visible
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# load env file if provided
env_path = os.getenv("ENV_PATH")

dotenv.load_dotenv(env_path, override=False)

MAX_RETRIES = 10


async def connect_ws(list_symbol: list[str], ws_url: str | None, socket_order=1):
    retry = 0
    if not ws_url:
        logging.error("WebSocket url not provided for socket order %s", socket_order)
        return
    while True:
        try:
            logging.info("Connecting to websocket server (order=%s)...", socket_order)
            async with websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
                max_queue=10000,
            ) as ws:
                logging.info("Connected to WebSocket: %s", socket_order)
                retry = 0
                # Subscribe to symbols
                for symbol in list_symbol:
                    await ws.send(json.dumps({"type": "subscribe", "symbol": symbol}))

                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=30)
                        await handle_message(msg)
                    except asyncio.TimeoutError:
                        logging.debug("WebSocket timeout, sending ping (order=%s)", socket_order)
                        try:
                            await ws.ping()
                        except Exception:
                            logging.exception("Failed to ping WebSocket (order=%s)", socket_order)
                    except websockets.exceptions.ConnectionClosed:
                        logging.warning("Connection closed, reconnecting for socket order %s...", socket_order)
                        break
        except Exception:
            logging.exception("WebSocket crashed (order=%s), reconnecting...", socket_order)
            # reconnect with exponential backoff
            retry += 1
            wait_time = min(2 ** retry, 60)
            await asyncio.sleep(wait_time)


queue: asyncio.Queue = asyncio.Queue()

async def handle_message(msg):
    try:
        await queue.put(msg)
    except Exception:
        logging.exception("Error putting message into queue")
        return


async def worker():
    # get singleton instance (object) which contains .producer
    producer_instance = KafkaProducerSingleton.get_instance()
    producer: Producer = producer_instance.producer

    while True:
        msg = await queue.get()
        try:
            parsed = json.loads(msg)
        except Exception:
            logging.exception("Failed to parse incoming message, skipping. Raw message: %s", repr(msg))
            continue

        if parsed.get("type") == "ping":
            continue

        data = parsed.get("data")
        if not data:
            logging.debug("Message has no data field: %s", parsed)
            continue

        for record in data:
            try:
                if not isinstance(record, dict):
                    logging.warning("Record is not a dict, skipping: %s", repr(record))
                    continue
                symbol = record.get("s")
                if symbol is None:
                    logging.warning("Record missing symbol 's' field: %s", record)
                    continue

                topic = os.environ.get("KAFKA_TOPIC")
                # await per-record send so we can log failures per-symbol
                await send_data_with_retry(producer, topic=topic, key=symbol, value=json.dumps(record))
                await on_trade_monitor(record)
            except Exception:
                logging.exception("Failed to send record for symbol %s", record.get("s"))
                continue


async def send_data_with_retry(producer: Producer, topic, key, value, max_retries=5):
    """
    Async retry loop for producing messages. Uses producer.poll(0) to trigger delivery callbacks.
    Uses asyncio.sleep instead of time.sleep so it doesn't block the event loop.
    """
    retry = 0

    def _delivery_report(err, msg):
        try:
            if err is not None:
                logging.error("Delivery failed for key=%s: %s", msg.key(), err)
            else:
                logging.debug("Message delivered to %s [%s]", msg.topic(), msg.partition())
        except Exception:
            logging.exception("Error in delivery callback")

    while True:
        try:
            if topic is None:
                raise ValueError("Kafka topic is not set")

            producer.produce(topic, key=key, value=value, callback=_delivery_report)
            # trigger delivery callbacks
            producer.poll(0)
            return
        except BufferError:
            # local producer queue is full, backoff and retry
            delay = min(2 ** retry, 10) + random.random()
            logging.warning("Producer queue full, backing off for %.2fs (retry %d)", delay, retry)
            await asyncio.sleep(delay)
            retry += 1
        except Exception:
            logging.exception("Error producing message, retrying (attempt %d)", retry)
            delay = min(2 ** retry, 10) + random.random()
            await asyncio.sleep(delay)
            retry += 1

        if retry > max_retries:
            logging.error("Max retries exceeded for sending data to Kafka. topic=%s key=%s", topic, key)
            raise KafkaException("Max retries exceeded for sending data to Kafka")


async def main():
    logging.warning("Starting main function")

    # Try to locate symbol list relative to this file or CWD
    base = Path(__file__).resolve().parent
    candidates = [
        os.environ.get("LIST_SYMBOL_PATH"),
        base / "list_symbol.txt",
        Path.cwd() / "list_symbol.txt",
        base.parent / "list_symbol.txt",
    ]

    list_symbol = []
    found = False
    for c in candidates:
        if not c:
            continue
        p = Path(c)
        if p.exists():
            with p.open("r") as f:
                for line in f:
                    ticker = line.strip()
                    if ticker:
                        list_symbol.append(ticker)
            found = True
            break

    if not found:
        logging.error("list_symbol.txt not found in candidates: %s", candidates)
        raise FileNotFoundError("list_symbol.txt not found")

    list_symbol.sort(key=str.lower)
    logging.info("list_symbol: %s", list_symbol)

    # ensure safe slicing
    await asyncio.gather(
        connect_ws(list_symbol[:40], os.getenv("WS_URL1"), 1),
        connect_ws(list_symbol[40:80], os.getenv("WS_URL2"), 2),
        connect_ws(list_symbol[80:120], os.getenv("WS_URL3"), 3),
        connect_ws(list_symbol[120:], os.getenv("WS_URL4"), 4),
        worker(),
        report(list_symbol)
    )



if __name__ == '__main__':

    asyncio.run(main())



