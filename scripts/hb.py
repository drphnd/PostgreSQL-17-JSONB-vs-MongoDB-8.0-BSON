import time, sys
# kolom: wall_epoch monotonic  (tiap 0.2 s)
while True:
    print(f"{time.time():.3f} {time.monotonic():.3f}", flush=True)
    time.sleep(0.2)
