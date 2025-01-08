import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pvlib.solarposition import get_solarposition
from scipy.spatial.transform import Rotation as R


def load_rad_data(path):
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = df.columns.astype(float)
    new_index = pd.Index(range(math.ceil(df.columns[0]), math.floor(df.columns[-1]) + 1))
    df = df.transpose()
    df = df.reindex(df.index.union(new_index, sort=True)).interpolate(method="index", limit_direction="both").loc[new_index]
    df.index = df.index.astype(int)
    return df.loc[320:950].transpose()


def normalize_angle(theta):
    if theta < 180:
        return -theta
    else:
        return 360 - theta


def get_2Dtilt(vector):
    x, y, z = vector
    r = np.sqrt(x**2 + y**2 + z**2)
    theta = np.degrees(np.arccos(z / r))
    phi = np.degrees(np.arctan2(y, x))
    return theta, phi


def load_ori_data(path):
    path_pos = path.parent / path.name.replace("orientation", "position")

    df = pd.read_csv(path, index_col="date_time", parse_dates=True)
    df_pos = pd.read_csv(path_pos, index_col="date_time", parse_dates=True)
    latitude = df_pos.latitude.mean()
    longitude = df_pos.longitude.mean()
    try:
        altitude = df_pos.altitude.mean()
    except AttributeError:
        altitude = None
    SAA = get_solarposition(df.index, latitude, longitude, altitude=altitude)

    df["theta_sun"] = SAA.azimuth
    df["theta_sun_norm"] = df.theta_sun.apply(normalize_angle)
    df["r_Lu"] = df.apply(lambda row: R.from_quat((row.x, row.y, row.z, row.w)), axis=1)
    df["vect_z"] = df.apply(lambda row: np.dot(row.r_Lu.as_matrix(), np.array([0, 0, 1])), axis=1)
    df[["theta", "phi"]] = df.apply(lambda row: get_2Dtilt(row.vect_z), axis=1).tolist()
    return df


def draw_spectrum(fig, df):
    x = df.columns.tolist()
    x_rev = x[::-1]
    mean = df.mean()
    upper = (mean + df.std()).tolist()
    lower = (mean - df.std()).tolist()[::-1]
    fig.add_trace(
        go.Scatter(
            x=x+x_rev, y=upper+lower,
            fill="toself", fillcolor="rgb(228, 26, 28, 0.2)",
            mode="lines", line_color="rgba(102, 102, 102, 0)",
            name="\u00B1std", legendgroup=1, legendrank=2
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=x, y=mean,
            mode="lines", line_color="rgb(102, 102, 102)",
            name="mean spectra", legendgroup=1, legendrank=1
        ),
        row=1, col=1
    )
    fig.update_xaxes(col=1, title_text="wavelength [nm]")
    fig.update_yaxes(col=1, title_text="R<sub>rs</sub> [sr<sup>-1</sup>]")
    return fig


def draw_tilt(fig, df):
    df.phi -= 90
    fig.add_trace(
        go.Scatterpolar(
            r=df.theta, theta=df.phi,
            mode="markers", marker_color=df.theta_sun,
            name="tilt", legendgroup=2
        ),
        row=1, col=3
    )
    fig.add_trace(
        go.Scatterpolar(
            r=[8]*len(df),
            theta=df.apply(lambda row: row.r_Lu.as_euler("zyx", degrees=True)[0], axis=1),
            mode="markers", marker=dict(line=dict(color=df.theta_sun, width=1), size=6, symbol="x-thin"),
            name="heading", legendgroup=2
        ),
        row=1, col=3
    )
    fig.add_trace(
        go.Scatterpolar(
            r=[10]*len(df), theta=df.theta_sun_norm,
            mode="markers", marker=dict(color=df.theta_sun, size=24, symbol="star", showscale=True, colorbar_title="SAA"),
            name="Sun", legendgroup=2
        ),
        row=1, col=3
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0, 10], showgrid=True, side="counterclockwise"),
                   angularaxis=dict(direction="counterclockwise", rotation=90,
                   tickmode="array",
                   tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                   ticktext=["N", "NW", "W", "SW", "S", "SE", "E", "NE"]))
    )
    return fig


def create_fig(df_rad, df_ori, name):
    fig = make_subplots(rows=3, cols=3,
                        specs=[[{"type": "xy", "colspan": 2, "rowspan": 3}, None, {"type": "polar", "rowspan": 2}],
                               [None, None, None],
                               [None, None, None]])
    fig = draw_tilt(fig, df_ori)
    fig = draw_spectrum(fig, df_rad)
    fig.update_layout(title_text=name, template="simple_white",
                      width=1600, height=900,
                      legend=dict(x=0.7, y=0.3, yanchor="top"))
    return fig


def main(path_Es, path_Lw, path_ori, out_dir):
    name = path_ori.stem.split("_")[1]
    df_Es = load_rad_data(path_Es)
    df_Lw = load_rad_data(path_Lw)
    df_ori = load_ori_data(path_ori)
    fig = create_fig(df_Lw / df_Es, df_ori, name)
    fig.write_image(out_dir / f"{'_'.join(path_ori.stem.split('_')[1:])}.png")
