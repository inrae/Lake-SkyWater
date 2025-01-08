import struct
from pathlib import Path

root = Path(__file__).resolve().parent

# GEO

dict_ns = {"N": 1, "S": -1}
dict_ew = {"E": 1, "W": -1}


def lnle2ll(latitude, ns, longitude, ew):
    return dict_ns[ns] * latitude / 1000000, dict_ew[ew] * longitude / 1000000


def tfq2spq(w, x, y, z):
    return x/16383, y/16383, z/16383, w/16383


def normalize_angle(theta):
    if theta < 180:
        return -theta
    else:
        return 360 - theta


# RAD

addresses = {
    2006: "integration_time",
    2010: "length",
    2014: "pre_inclination",
    2016: "post_inclination",
    2101: "abscissa1",
    2225: "abscissa2",
    2349: "abscissa3",
    2473: "abscissa4",
    2597: "abscissa5",
    2613: "ordinate1",
    2737: "ordinate2",
    2861: "ordinate3",
    2985: "ordinate4",
    3109: "ordinate5",
}


def process_data(data):
    res = {
        "time": data["time"],
        "integration_time": data["integration_time"][0],
        "length": data["length"][0],
        "pre_inclination": struct.unpack("!f", bytes.fromhex("".join("%.4x" %i for i in data["pre_inclination"])))[0],
        "post_inclination": struct.unpack("!f", bytes.fromhex("".join("%.4x" %i for i in data["post_inclination"])))[0],
        "ordinate": data["ordinate1"] + data["ordinate2"] + data["ordinate3"] + data["ordinate4"] + data["ordinate5"],
    }
    lst = []
    for b1, b2 in zip(res["ordinate"][::2], res["ordinate"][1::2]):
        lst.append(struct.unpack("!f", bytes.fromhex("".join("%.4x" %i for i in (b1, b2))))[0])
    res["ordinate"] = lst
    return res


def set_configuration(rs485):
    rs485.set_rs485_configuration(
        baudrate=9600,
        parity=0,   # none
        stopbits=1,
        wordlength=8,
        duplex=0    # half duplex
    )
    rs485.set_mode(rs485.MODE_MODBUS_MASTER_RTU)
    # Modbus specific configuration:
    # - slave address = 1 (unused in master mode)
    # - master request timeout = 12000ms
    rs485.set_modbus_configuration(1, 12000)
