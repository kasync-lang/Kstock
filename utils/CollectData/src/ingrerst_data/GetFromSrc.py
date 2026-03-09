import asyncio
import json
from ingrerst_data.KafkaProducerClient import KafkaProducerSingleton
import random
import os
import websockets
import time
import traceback
import dotenv
import logging
from confluent_kafka import Producer, KafkaException
dotenv.load_dotenv(os.getenv("ENV_PATH"))
MAX_RETRIES = 10

async def connect_ws(list_symbol:list[str], ws_url:str, socket_order = 1):
    retry = 0
    while True:
        try:
            print(f"Connecting to websocket server.....")
            async with websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
                max_queue=1000
            ) as ws:
                print(f"Connected to WebSocket: {socket_order}")
                retry = 0
                # Subscribe to symbols
                for symbol in list_symbol:
                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "symbol": symbol,
                    }))

                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=10)
                        await handle_message(msg)
                    except asyncio.TimeoutError:
                        print("No message received in 10 seconds, sending ping...")
                        await ws.ping()
                    except websockets.exceptions.ConnectionClosed:
                        print("Connection closed, reconnecting...")
                        break
        except Exception as e:
            print("WebSocket crashed:", e)
            traceback.print_exc()
            #reconnect with exponential backoff
            retry += 1
            wait_time = min(2**retry, 60)
            await asyncio.sleep(wait_time)
##############################

queue = asyncio.Queue()

async def handle_message(msg):
    try:

        await queue.put(msg)
    except Exception as e:
        print("Error processing message:", e)
        traceback.print_exc()

async def worker():
    producer = KafkaProducerSingleton.get_instance()
    while True:
        msg = await queue.get()
        #main work here
        msg = json.loads(msg)
        if msg["type"] == "ping":
            print("Worker: received ping")
            continue
        for record in msg["data"]:
            symbol = record["s"]
            send_data_with_retry(producer,topic="raw_data_trade", key=symbol, value=json.dumps(record))



def send_data_with_retry(producer:Producer, topic,key, value, max_retries=5):
    retry = 0
    while True:
        try:
            producer.produce(topic, key = key, value=value)
            producer.poll(0)
            return
        except Exception as e:
            delay = min(2**retry, 10) + random.random()
            time.sleep(delay)
            retry += 1
            if retry > max_retries:
                raise KafkaException("Max retries exceeded for sending data to Kafka")

async def main():
    logging.warning("Starting main function")
    dotenv.load_dotenv(os.getenv("ENV_PATH"))
    logging.warning(f"ENV_PATH: {type(os.getenv('ENV_PATH'))}")
    logging.warning(f"ENV_PATH value: {os.environ}")
    list_symbol = []
    ws_url1 = os.getenv("WS_URL1")
    logging.warning(f"WS_URL1: {ws_url1}")
    ws_url2 = os.getenv("WS_URL2")
    ws_url3 = os.getenv("WS_URL3")
    with open("list_symbol.txt", "r") as f:
        for line in f:
            ticker = line.strip()
            list_symbol.append(ticker)
            
    await asyncio.gather(
        connect_ws(list_symbol[:49], ws_url1,1),
        connect_ws(list_symbol[49:100], ws_url2,2),
        connect_ws(list_symbol[100:-1], ws_url3,3),
        worker()
    )
if __name__ == '__main__':

    asyncio.run(main())



