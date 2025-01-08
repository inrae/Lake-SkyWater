import time
from threading import Thread

import pandas as pd
from rich import print
from rich.progress import track
from tinkerforge.ip_connection import IPConnection
from tinkerforge.bricklet_rs485 import BrickletRS485

from lsw.utils import addresses, process_data, set_configuration


HOST = "localhost"
PORT = 4223
UID_Ed = "24Ry"
UID_Lu = "28Dt"


# Global variables

rs485_Ed = None
Ed_address = None
Ed_byte = None
Ed_expected_request_id = None

rs485_Lu = None
Lu_address = None
Lu_byte = None
Lu_expected_request_id = None

n_Ed = 0
n_Lu = 0

path_Ed = None
path_Lu = None


# Callbacks

def cb_write_single_register_Ed(request_id, exception_code):
    global Ed_address, Ed_address_queue, Ed_byte, Ed_byte_queue, Ed_data, Ed_expected_request_id, n_Ed

    print(f"Ed Measurement (id: {request_id}, EC: {exception_code})")
    if request_id != Ed_expected_request_id:
        print(f"Ed Error: Unexpected request ID ({Ed_expected_request_id})")
        time.sleep(0.256)
        Ed_expected_request_id = rs485_Ed.modbus_master_write_single_register(2, 2, 1024)   # trigger measurement
    else:
        Ed_data = {"time": pd.Timestamp.now().isoformat(timespec="seconds")}
        Ed_address = 2006
        Ed_address_queue = [3109, 2985, 2861, 2737, 2613, 2016, 2014, 2010]
        Ed_byte = 1
        Ed_byte_queue = [14, 124, 124, 124, 124, 2, 2, 2]
        if n_Ed == 0:
            time.sleep(4.096)
            n_Ed += 1
        Ed_expected_request_id = rs485_Ed.modbus_master_read_holding_registers(2, Ed_address, Ed_byte)


def cb_write_single_register_Lu(request_id, exception_code):
    global Lu_address, Lu_address_queue, Lu_byte, Lu_byte_queue, Lu_data, Lu_expected_request_id, n_Lu

    print(f"Lu Measurement (id: {request_id}, EC: {exception_code})")
    if request_id != Lu_expected_request_id:
        print(f"Lu Error: Unexpected request ID ({Lu_expected_request_id})")
        time.sleep(0.256)
        Lu_expected_request_id = rs485_Lu.modbus_master_write_single_register(1, 2, 1024)   # trigger measurement
    else:
        Lu_data = {"time": pd.Timestamp.now().isoformat(timespec="seconds")}
        Lu_address = 2006
        Lu_address_queue = [3109, 2985, 2861, 2737, 2613, 2016, 2014, 2010]
        Lu_byte = 1
        Lu_byte_queue = [14, 124, 124, 124, 124, 2, 2, 2]
        if n_Lu == 0:
            time.sleep(4.096)
            n_Lu += 1
        Lu_expected_request_id = rs485_Lu.modbus_master_read_holding_registers(1, Lu_address, Lu_byte)


def cb_read_Ed(request_id, exception_code, holding_registers):
    global Ed_address, Ed_address_queue, Ed_busy, Ed_byte, Ed_byte_queue, Ed_data, Ed_expected_request_id, path_Ed

    print(f"Ed Measurement (id: {request_id}, EC: {exception_code}) ; {addresses[Ed_address]}")
    if exception_code == 0:     # success
        Ed_data[addresses[Ed_address]] = holding_registers
        if Ed_address == 3109:
            pd.DataFrame([process_data(Ed_data)]).set_index("time").to_csv(path_Ed, mode="a", header=False)  # Write Ed data on disk
            Ed_busy = False
        else:
            Ed_address = Ed_address_queue.pop()
            Ed_byte = Ed_byte_queue.pop()
            Ed_expected_request_id = rs485_Ed.modbus_master_read_holding_registers(2, Ed_address, Ed_byte)
    else:
        if request_id != Ed_expected_request_id:
            print(f"Ed Error: Unexpected request ID ({Ed_expected_request_id})")
        elif exception_code == 6:
            print("Ed sensor is busy")
        time.sleep(0.256)
        Ed_expected_request_id = rs485_Ed.modbus_master_read_holding_registers(2, Ed_address, Ed_byte)


def cb_read_Lu(request_id, exception_code, holding_registers):
    global Lu_address, Lu_address_queue, Lu_busy, Lu_byte, Lu_byte_queue, Lu_data, Lu_expected_request_id, path_Lu

    print(f"Lu Measurement (id: {request_id}, EC: {exception_code}) ; {addresses[Lu_address]}")
    if exception_code == 0:     # success
        Lu_data[addresses[Lu_address]] = holding_registers
        if Lu_address == 3109:
            pd.DataFrame([process_data(Lu_data)]).set_index("time").to_csv(path_Lu, mode="a", header=False)  # Write Lu data on disk
            Lu_busy = False
        else:
            Lu_address = Lu_address_queue.pop()
            Lu_byte = Lu_byte_queue.pop()
            Lu_expected_request_id = rs485_Lu.modbus_master_read_holding_registers(1, Lu_address, Lu_byte)
    else:
        if request_id != Lu_expected_request_id:
            print(f"Lu Error: Unexpected request ID ({Lu_expected_request_id})")
        elif exception_code == 6:
            print("Lu sensor is busy")
        time.sleep(0.256)
        Lu_expected_request_id = rs485_Lu.modbus_master_read_holding_registers(1, Lu_address, Lu_byte)


# Thread workers

def get_Ed(slave_addr=2):
    global Ed_busy, Ed_expected_request_id
    
    Ed_busy = True
    Ed_expected_request_id = rs485_Ed.modbus_master_write_single_register(slave_addr, 2, 1024)     # trigger measurement
    while Ed_busy:
        time.sleep(1)


def get_Lu(slave_addr=1):
    global Lu_busy, Lu_expected_request_id
    
    Lu_busy = True
    Lu_expected_request_id = rs485_Lu.modbus_master_write_single_register(slave_addr, 2, 1024)     # trigger measurement
    while Lu_busy:
        time.sleep(1)


# Main function

def main(point_id, n, out_dir):
    global rs485_Ed, rs485_Lu, path_Ed, path_Lu

    ipcon = IPConnection() # Create IP connection
    rs485_Ed = BrickletRS485(UID_Ed, ipcon) # Create device object
    rs485_Lu = BrickletRS485(UID_Lu, ipcon) # Create device object

    ipcon.connect(HOST, PORT) # Connect to brickd
    # Don't use device before ipcon is connected

    set_configuration(rs485_Ed)     # Set rs485 configuration
    set_configuration(rs485_Lu)     # Set rs485 configuration

    # Register Modbus master read holding/multiple registers response callback
    # to function cb_modbus_master_read_holding_registers_response
    rs485_Ed.register_callback(rs485_Ed.CALLBACK_MODBUS_MASTER_READ_HOLDING_REGISTERS_RESPONSE,
                               cb_read_Ed)
    rs485_Lu.register_callback(rs485_Lu.CALLBACK_MODBUS_MASTER_READ_HOLDING_REGISTERS_RESPONSE,
                               cb_read_Lu)

    # Register Modbus master write single register response callback to function
    # cb_modbus_master_write_single_register_response
    rs485_Ed.register_callback(rs485_Ed.CALLBACK_MODBUS_MASTER_WRITE_SINGLE_REGISTER_RESPONSE,
                               cb_write_single_register_Ed)
    rs485_Lu.register_callback(rs485_Lu.CALLBACK_MODBUS_MASTER_WRITE_SINGLE_REGISTER_RESPONSE,
                               cb_write_single_register_Lu)
    
    # Write headers
    path_Ed = out_dir / f"Es_{point_id}_{pd.Timestamp.now().strftime('%Y%m%dT%H%M')}__RAW.csv"
    path_Lu = out_dir / f"Lw_{point_id}_{pd.Timestamp.now().strftime('%Y%m%dT%H%M')}__RAW.csv"
    with open(path_Ed, "w") as f:
        f.write("time,integration_time,length,pre_inclination,post_inclination,ordinate\n")
    with open(path_Lu, "w") as f:
        f.write("time,integration_time,length,pre_inclination,post_inclination,ordinate\n")

    for _ in track(range(n), description="Processing..."):
        t_Ed = Thread(target=get_Ed)
        t_Lu = Thread(target=get_Lu)
        t_Ed.start()
        t_Lu.start()
        t_Ed.join()
        t_Lu.join()
    print(f"Measured 2x{n} spectra.")

    ipcon.disconnect()
