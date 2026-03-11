import os
import json
import time
import datetime
from datetime import timezone

class RotatingJSONLWriter:
    def __init__(self, base_dir, symbol, max_size_mb=50):
        self.base_dir = base_dir
        self.symbol = symbol
        self.max_size = max_size_mb * 1024 * 1024  # convert MB → bytes

        self.current_file = None
        self.current_path = None
        self.current_size = 0
        self.file_index = 1
        self.last_used_ts= time.time()
        self._open_new_file()

    def _get_today_dir(self):
        today = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = os.path.join(self.base_dir, self.symbol, today)
        os.makedirs(path, exist_ok=True)
        return path

    def _open_new_file(self):
        directory = self._get_today_dir()
        filename = f"part-{self.file_index:05d}.jsonl"
        self.current_path = os.path.join(directory, filename)

        self.current_file = open(self.current_path, "a", encoding="utf-8")
        self.current_size = os.path.getsize(self.current_path) if os.path.exists(self.current_path) else 0

    def _rotate(self):
        self.current_file.close()
        self.file_index += 1
        self._open_new_file()

    def write(self, record):
        """ record must be dict or JSON string """
        if isinstance(record, dict):
            line = json.dumps(record)
        else:
            line = record

        encoded = (line + "\n").encode("utf-8")
        size = len(encoded)

        # Rotate if enough size
        if self.current_size + size > self.max_size:
            self._rotate()

        self.current_file.write(line + "\n")
        self.current_file.flush()

        self.current_size += size
        self.last_used_ts = time.time()

    def close(self):
        if self.current_file:
            self.current_file.close()
