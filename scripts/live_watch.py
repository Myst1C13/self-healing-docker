import sys
sys.path.insert(0, ".")

import time
from src.collector import collect_once, get_all_windows
from src.detector import detect_all

if __name__ == "__main__":
    print("Building window - collecting 5 rounds...\n")
    for i in range(5):
        collect_once()
        print(f"Round {i+1} collected")
        time.sleep(1)

    print("\nStarting detector loop. Trigger chaos to see incidents.\n")

    while True:
        collect_once()
        windows = get_all_windows()
        incidents = detect_all(windows)

        if incidents:
            for inc in incidents:
                print(f"INCIDENT: {inc['service']} | {inc['incident_type']} | {inc['reason']}")
        else:
            print("All services healthy")

        time.sleep(5)