import signal

running = True
from confluent_kafka import Consumer, KafkaException, KafkaError
from WriterPool import WriterPool
import json
import time
from config import settings

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
def worker():
    conf = {
        "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "group.id": settings.KAFKA_GROUP_ID,
        "enable.auto.commit": settings.AUTO_COMMIT,
        "auto.offset.reset": settings.AUTO_OFFSET_RESET,
        "session.timeout.ms": 10000,
        "max.poll.interval.ms": 300000,
        "fetch.max.bytes": 50 * 1024 * 1024,
    }
    # def on_assign(consumer, partitions):
    #     logging.info(f"Assigned partitions: {partitions}")
    #     consumer.assign(partitions)
    # def on_revoke(consumer, partitions):
    #     logging.warning("Partitions revoked, committing offsets")
    #     consumer.commit(offsets=partitions, asynchronous=False)
    writer = WriterPool(base_dir=settings.RAW_DATA_DIR, max_size_mb=500, idle_timeout_sec=300)
    def process_message(data: dict):



        logging.info(f"Processing order {data}")
        symbol = data["s"]
        writer.write(symbol, data)
        if data.get("force_fail"):
            raise RuntimeError("Temporary error")
    def shutdown(sig, frame):
        global running
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)


    def on_assign(consumer, partitions):
        logging.info(f"Assigned partitions: {partitions}")
        consumer.assign(partitions)
    def on_revoke(consumer, partitions):
        logging.warning("Partitions revoked, committing offsets")
        consumer.commit(offsets=partitions, asynchronous=False)
    consumer = Consumer({
        **conf,

    })
    def send_to_dlq(msg):
        # produce msg.value() sang topic orders.DLQ
        logging.log(level=logging.WARNING,msg=f"Sending to DLQ: {msg.value()}")
        # chưa có service sử lí DLQ nên tạm thời chỉ log ra thôi
        pass


    consumer.subscribe([settings.KAFKA_TOPIC])

    try:
        while running:
            msgs = consumer.consume(num_messages=10, timeout=1.0)

            if not msgs:
                continue

            for msg in msgs:
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise KafkaException(msg.error())

                try:
                    data = json.loads(msg.value())
                    process_message(data)

                    # commit SAU khi xử lý thành công
                    consumer.commit(message=msg, asynchronous=False)

                except json.JSONDecodeError:
                    logging.error("Invalid JSON → send to DLQ")
                    send_to_dlq(msg)
                    consumer.commit(message=msg, asynchronous=False)

                except Exception as e:
                    logging.exception("Processing failed")
                    # KHÔNG commit → message sẽ được retry
                    time.sleep(1)

    finally:
        logging.info("Closing consumer")
        consumer.close()
