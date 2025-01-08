import configparser

import pandas as pd
import xarray as xr

from lsw.utils import root


def load_background_data(path):
    return pd.read_csv(path, names=["Pixel", "B0", "B1", "Status"], sep=" ",
                       skiprows=39, skipfooter=3, dtype={"Pixel": int, "B0": float, "B1": float},
                       engine="python")[["Pixel", "B0", "B1"]].set_index("Pixel")


def load_calibration_data(path):
    return pd.read_csv(path, names=["Pixel", "Sn", "_", "Status"], sep=" ",
                       skiprows=39, skipfooter=3, dtype={"Pixel": int, "Sn": float},
                       engine="python")[["Pixel", "Sn"]].set_index("Pixel")


def load_ini(path):
    config = configparser.ConfigParser()
    config.read(path)
    return {coef: float(config["Attributes"][coef])
            for coef in ("c0s", "c1s", "c2s", "c3s", "c4s")}


def load_raw_data(path, df_back, df_cal, dict_ini):
    df = pd.read_csv(path, index_col="time", parse_dates=True)
    ds = xr.Dataset(
        {
            "integration_time": ("time", df["integration_time"]),
            "pre_inclination": ("time", df["pre_inclination"]),
            "post_inclination": ("time", df["post_inclination"]),
            "In": (["time", "Pixel"], [eval(e) for e in df["ordinate"].values])
        },
        coords = {
            "time": df.index,
            "Pixel": list(range(1, 256))
        }
    )
    ds["Mn"] = ds["In"] / 65535
    
    ds_back = xr.Dataset.from_dataframe(df_back)
    ds_back["Bn"] = ds_back.B0 + ds.integration_time / 8192 * ds_back.B1
    ds_back["Cn"] = ds.Mn - ds_back.Bn
    ds_back["offset"] = ds_back.Cn.sel(Pixel=slice(237, 254)).mean(dim="Pixel")
    ds_back["Dn"] = ds_back.Cn - ds_back.offset
    ds_back["En"] = ds_back.Dn * 8192 / ds.integration_time

    ds_cal = xr.Dataset.from_dataframe(df_cal)

    L = lambda n: dict_ini["c0s"] + dict_ini["c1s"] * (n+1) + dict_ini["c2s"] * (n+1)**2 + dict_ini["c3s"] * (n+1)**3 + dict_ini["c4s"] * (n+1)**4
    Fn = xr.DataArray(
        ds_back.En / ds_cal.Sn,
        coords=[ds.time, L(ds.Pixel.values)],
        dims=["time", "Ln"],
        name="Fn"
    )
    return Fn.to_dataframe()


def format_df(df):
    lst = []
    for datetime in df.index.levels[0]:
        df_ = df.loc[datetime]
        df_.columns = [datetime]
        lst.append(df_)
    return pd.concat(lst, axis=1).dropna().transpose()


def main(path, sensor_id, out_dir):
    df = load_raw_data(
        path,
        load_background_data(root / f"calibration_files/{sensor_id}/Back_SAM_{sensor_id}.dat"),
        load_calibration_data(root / f"calibration_files/{sensor_id}/Cal_SAM_{sensor_id}.dat"),
        load_ini(root / f"calibration_files/{sensor_id}/SAM_{sensor_id}.ini")
    )
    format_df(df).to_csv(out_dir / str(path.name).replace("__RAW", "__CALIBRATED"))
