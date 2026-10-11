# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
from src.ingrerst_data.GetFromSrc import main
import asyncio
import time
import os
import threading




# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    def auto_restart_timer(interval_seconds=1200):
        time.sleep(interval_seconds)
        os._exit(1)
    timer_thread = threading.Thread(target=auto_restart_timer, daemon=True)
    timer_thread.start()
    asyncio.run(main())

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
