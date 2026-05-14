from src.consumer import ConsumerClient, ConsumerKafkaConfig
from src.producer import ProducerClient, ProducerKafkaConfig
from src.aggregator import OHLCVAggregator
from dotenv import load_dotenv
import asyncio

load_dotenv()
agg = OHLCVAggregator()
async def consume():
    consumer_config = ConsumerKafkaConfig.from_environment()
    consumer_client = ConsumerClient(consumer_config)
    print("start consuming")
    while True:
        item = consumer_client.poll(timeout=1.0)
        if item is not None:
            agg.process_tick(item["value"])
        await asyncio.sleep(0)
async def flusher():
    while True:
        finalized = agg.flush_finalized()
        for item in finalized:
            print(item, "time space:{}".format((item.last_ts-item.first_ts)/1000))
            print("========================================================================")

        await asyncio.sleep(5)

async def main():
    await asyncio.gather(consume(), flusher())
if __name__ == "__main__":
    asyncio.run(main())
