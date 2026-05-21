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

            # disable batching
            'linger.ms': 0,

            # disable compression
            'compression.type': 'none',

            # reduce internal queue
            'queue.buffering.max.messages': 1000,
            'queue.buffering.max.kbytes': 1024,

            # send immediately
            'batch.num.messages': 1,

            # network
            'socket.keepalive.enable': True,

            # delivery timeout
            'message.timeout.ms': 3000,

            # optional
            'acks': 1,

            # optional
            'enable.idempotence': False,
}
        self.producer = Producer(config)
    @classmethod
    def get_instance(cls, bootstrap_servers="192.168.2.100:29092"):
        if cls._instance is None:
            cls._instance = KafkaProducerSingleton(bootstrap_servers)
        return cls._instance.producer