import threading
import time


def sleeper():
    print("sleeper started")
    time.sleep(5)
    print("sleeper ended")


print("sleeper starting")
threading.Thread(target=sleeper).start()
print("sleeper called")
