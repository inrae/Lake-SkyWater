import signal
import time

import numpy as np
import pandas as pd
from pvlib.solarposition import get_solarposition
from scipy.spatial.transform import Rotation as R
from tinkerforge.ip_connection import IPConnection
from tinkerforge.brick_silent_stepper import BrickSilentStepper
from tinkerforge.bricklet_gps_v2 import BrickletGPSV2
from tinkerforge.bricklet_imu_v3 import BrickletIMUV3

from lsw.utils import lnle2ll, tfq2spq, normalize_angle


HOST = "localhost"
PORT = 4223
UID_GPS = "PuF"
UID_IMU = "ZH8"
UID_SS = "68wJ5h"   # silent stepper

# global variables
gps = None
ss = None
r_sun = None
f_pos = None
f_ori = None

# buoy specs
dtheta = -109

# stepper specs
step_angle = 1.8 / 50
Z = 128 / 48


class GracefulKiller:
    """from https://stackoverflow.com/questions/18499497/how-to-process-sigterm-signal-gracefully"""
    kill_now = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
    
    def exit_gracefully(self, signum, frame):
        self.kill_now = True


def _get_solar_azimuth(latitude, ns, longitude, ew):
    ttime = pd.Timestamp.now()
    altitude = gps.get_altitude()[0]/100
    res = get_solarposition(ttime, *lnle2ll(latitude, ns, longitude, ew), altitude=altitude)
    return res.azimuth.iloc[0], ttime, altitude


def get_solar_azimuth():
    while not gps.get_status()[0]:
        print("No fix available\n")
        time.sleep(1)
    
    return _get_solar_azimuth(*gps.get_coordinates())[0]


def cb_coordinates(latitude, ns, longitude, ew):
    global r_sun

    SAA, ttime, altitude = _get_solar_azimuth(latitude, ns, longitude, ew)
    r_sun = R.from_euler("z", normalize_angle(SAA), degrees=True)

    f_pos.write(f"{','.join((ttime.isoformat(), *(str(e) for e in lnle2ll(latitude, ns, longitude, ew)), altitude))}\n")


def cb_quaternion(w, x, y, z):
    r_Lu = R.from_quat(tfq2spq(w, x, y, z)) * R.from_euler("z", dtheta, degrees=True)
    r = r_Lu.inv() * r_sun
    # print("\nAngles:")
    # print("r_sun", r_sun.as_euler("zyx", degrees=True)[0])
    # print("r_imu", R.from_quat(tfq2spq(w, x, y, z)).as_euler("zyx", degrees=True)[0])
    # print("r_Lu", r_Lu.as_euler("zyx", degrees=True)[0])
    # print("-r_Lu", r_Lu.inv().as_euler("zyx", degrees=True)[0])
    # print("r", r.as_euler("zyx", degrees=True)[0])
    if np.abs(r.as_euler("zyx", degrees=True)[0]) > 5:  # threshold of 5°
        nb_steps = int(r.as_euler("zyx", degrees=True)[0] / step_angle * Z)    # anticlockwise rotation
        ss.set_steps(nb_steps)

    f_ori.write(f"{','.join((pd.Timestamp.now().isoformat(), *(str(e) for e in r_Lu.as_quat())))}\n")


def main(station, out_dir):
    global gps, ss, r_sun, f_pos, f_ori
    
    killer = GracefulKiller()

    ipcon = IPConnection() # Create IP connection
    gps = BrickletGPSV2(UID_GPS, ipcon)  # Create device object
    imu = BrickletIMUV3(UID_IMU, ipcon) # Create device object
    ss = BrickSilentStepper(UID_SS, ipcon)  # Create device object

    ipcon.connect(HOST, PORT) # Connect to brickd
    # Don't use device before ipcon is connected

    ss.set_motor_current(1580) # 1.58 A
    ss.set_step_configuration(ss.STEP_RESOLUTION_1, False) # 1 step (not interpolated)
    ss.set_max_velocity(1000) # Velocity 1000 steps/s

    # Slow acceleration (500 steps/s^2),
    # Fast deacceleration (2000 steps/s^2)
    ss.set_speed_ramping(500, 2000)

    # Get current coordinates
    r_sun = R.from_euler("z", normalize_angle(get_solar_azimuth()), degrees=True)

    # Initialisation
    ss.enable() # Enable motor power

    gps.register_callback(gps.CALLBACK_COORDINATES, cb_coordinates)
    imu.register_callback(imu.CALLBACK_QUATERNION, cb_quaternion)

    with open(out_dir / f"position_{station}_{pd.Timestamp.now().strftime('%Y%m%dT%H%M')}.csv", "a") as f_pos, open(out_dir / f"orientation_{station}_{pd.Timestamp.now().strftime('%Y%m%dT%H%M')}.csv", "a") as f_ori:
        f_pos.write("date_time,latitude,longitude,altitude\n")
        f_ori.write("date_time,x,y,z,w\n")
        gps.set_coordinates_callback_period(60000)  # set callback period to 1 m (60*1000 ms)
        imu.set_quaternion_callback_configuration(400, False)    # set callback period to 400 ms
        while not killer.kill_now:
            time.sleep(1)
        imu.set_quaternion_callback_configuration(0, False)   # turns the callback off
        gps.set_coordinates_callback_period(0)  # turns the callback off
        cb_coordinates(*gps.get_coordinates())

    # Stop motor before disabling motor power
    ss.stop() # Request motor stop
    ss.set_speed_ramping(500, 5000) # Fast deacceleration (5000 steps/s^2) for stopping
    time.sleep(0.4) # Wait for motor to actually stop: max velocity (2000 steps/s) / decceleration (5000 steps/s^2) = 0.4 s
    ss.disable() # Disable motor power

    ipcon.disconnect()
