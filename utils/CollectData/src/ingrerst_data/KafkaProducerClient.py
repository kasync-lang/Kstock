import socket
import time
import random
from confluent_kafka import Producer
class KafkaProducerSingleton:
    _instance = None

    def __init__(self, bootstrap_servers = "192.168.2.100:29092"):
        config = {
            'bootstrap.servers': bootstrap_servers,
            'client.id': socket.gethostname(),
            "queue.buffering.max.kbytes": 20480,   # buffer 20MB
            "queue.buffering.max.messages": 200000,
            "linger.ms": 5,                        # gom batch nhỏ
            "compression.type": "lz4",
            "socket.keepalive.enable": True,
            "message.timeout.ms": 10000,           # 10s
            "enable.idempotence": False,
        }
        self.producer = Producer(config)
    @classmethod
    def get_instance(cls, bootstrap_servers="192.168.2.100:29092"):
        if cls._instance is None:
            cls._instance = KafkaProducerSingleton(bootstrap_servers)
        return cls._instance.producer