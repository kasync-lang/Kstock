import time
from RotatingJsonWriter import RotatingJSONLWriter
class WriterPool:
    def __init__(self, base_dir, max_size_mb=50, idle_timeout_sec=30):
        self.base_dir = base_dir
        self.max_size_mb = max_size_mb
        self.idle_timeout_sec = idle_timeout_sec
        self.writers:dict[str, RotatingJSONLWriter] = {}
    def get_writer(self, symbol):
        if symbol not in self.writers:
            self.writers[symbol] = RotatingJSONLWriter(self.base_dir, symbol, max_size_mb=self.max_size_mb)
        return self.writers[symbol]

    def write(self, symbol, record):
        w = self.get_writer(symbol)
        w.write(record)
    def cleanup(self):
        now = time.time()
        to_close = []
        for sym, writer in self.writers.items():
            if now - writer.last_used_ts > self.idle_timeout_sec:
                writer.close()
                to_close.append(sym)
        for sym in to_close:
            del self.writers[sym]