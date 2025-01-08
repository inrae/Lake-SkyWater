import subprocess
import time
import warnings
warnings.simplefilter(action="ignore", category=FutureWarning)

import pandas as pd
from tinkerforge.ip_connection import IPConnection
from tinkerforge.bricklet_gps_v2 import BrickletGPSV2


HOST = "localhost"
PORT = 4223
UID_GPS = "PuF"


def main():
    ipcon = IPConnection() # Create IP connection
    gps = BrickletGPSV2(UID_GPS, ipcon)  # Create device object

    ipcon.connect(HOST, PORT) # Connect to brickd

    while not gps.get_status()[0]:
        time.sleep(1)
    _date, _time = gps.get_date_time()
    datetime = pd.to_datetime(f"{_date}{_time}", format="%d%m%y%H%M%S%f").isoformat(sep=" ", timespec="seconds")
    subprocess.run(["sudo", "timedatectl", "set-time", datetime])
    result = subprocess.run(["timedatectl", "status"], capture_output=True, text=True)
    print(result.stdout)


if __name__ == "__main__":
    main()
