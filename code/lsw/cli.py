import subprocess
from multiprocessing import Process
from pathlib import Path

import typer
from typing_extensions import Annotated

from lsw.gps_time import main as set_time
from lsw.main_geo import main as main_g
from lsw.main_rad import main as main_r
from lsw.calibrate import main as main_c
from lsw.plot import main as main_p


def f1(_tuple):
    station, out_dir = _tuple
    main_g(station, out_dir / "geo")


def f2(_tuple):
    station, n_spectra, out_dir = _tuple
    main_r(station, n_spectra, out_dir / "rad/raw")


app = typer.Typer()


@app.command()
def start(
        station: Annotated[str, typer.Argument(help="The name of the sampling station")],
        n_spectra: Annotated[int, typer.Option("--nb-spectra", "-n", help="How many spectra to measure")] = 24,
        out_dir: Annotated[Path, typer.Option("--out-dir", "-o", exists=True, file_okay=False, dir_okay=True, resolve_path=True, help="Output directory")] = Path.home() / "LSW_data",
        rotate: Annotated[bool, typer.Option("--rotate/--no-rotation", "-r", help="Make Lw sensor face the Sun")] = True,
    ):
    """
    Start the Rrs measurements.

    If --no-rotation is used, the Lw radiometer won't automatically face the Sun.
    """
    set_time()
    if rotate:
        p1 = Process(target=f1, args=((station, out_dir),))
        p1.start()
    p2 = Process(target=f2, args=((station, n_spectra, out_dir),))
    p2.start()
    p2.join()
    if rotate:
        p1.terminate()  # SIGTERM
        p1.join()


@app.command()
def calibrate(
        in_dir: Annotated[Path, typer.Option("--in-dir", "-i", exists=True, file_okay=False, dir_okay=True, resolve_path=True, help="Input directory")] = Path.home() / "LSW_data/rad/raw",
        out_dir: Annotated[Path, typer.Option("--out-dir", "-o", exists=True, file_okay=False, dir_okay=True, resolve_path=True, help="Output directory")] = Path.home() / "LSW_data/rad/calibrated",
        force: Annotated[bool, typer.Option("--force/--no-force", "-f", help="Ignore existing (calibrated) files")] = False,
    ):
    """Apply sensor calibration to measured data."""
    path_Es = list(in_dir.glob("Es*__RAW.csv"))
    path_Lw = list(in_dir.glob("Lu*__RAW.csv"))
    if not force:
        existing_Es = [path.stem.split("__")[0] for path in out_dir.glob("Es*__CALIBRATED.csv")]
        existing_Lw = [path.stem.split("__")[0] for path in out_dir.glob("Lw*__CALIBRATED.csv")]
        path_Es = [path for path in path_Es if path.stem.split("__")[0] not in existing_Es]
        path_Lw = [path for path in path_Lw if path.stem.split("__")[0] not in existing_Lw]
    for path in path_Es:
        main_c(path, "8798", out_dir)
    for path in path_Lw:
        main_c(path, "8799", out_dir)


@app.command()
def draw(in_dir1: Annotated[Path, typer.Option(exists=True, file_okay=False, dir_okay=True, resolve_path=True, help="Input directory for radiometry")] = Path.home() / "LSW_data/rad/calibrated",
         in_dir2: Annotated[Path, typer.Option(exists=True, file_okay=False, dir_okay=True, resolve_path=True, help="Input directory for geometry")] = Path.home() / "LSW_data/geo",
         out_dir: Annotated[Path, typer.Option("--out-dir", "-o", exists=True, file_okay=False, dir_okay=True, resolve_path=True, help="Output directory")] = Path.home() / "LSW_data/figs",
         force: Annotated[bool, typer.Option("--force/--no-force", "-f", help="Ignore existing figures")] = False,
    ):
    """Plot measured data."""
    path_Es = sorted(list(in_dir1.glob("Es*__CALIBRATED.csv")))
    path_Lw = sorted(list(in_dir1.glob("Lw*__CALIBRATED.csv")))
    path_ori = sorted(list(in_dir2.glob("ori*.csv")))
    if not force:
        path_Es = [p1 for p1 in path_Es if p1.stem[3:].split("__")[0] not in [p2.stem for p2 in out_dir.glob("*.png")]]
        path_Lw = [p1 for p1 in path_Lw if p1.stem[3:].split("__")[0] not in [p2.stem for p2 in out_dir.glob("*.png")]]
        path_ori = [p1 for p1 in path_ori if "_".join(p1.stem.split("_")[1:]) not in [p2.stem for p2 in out_dir.glob("*.png")]]
    for path1, path2, path3 in zip(path_Es, path_Lw, path_ori):
        main_p(path1, path2, path3, out_dir)


@app.command()
def shutdown():
    """Stop and shut down the system."""
    subprocess.run(["sudo", "shutdown", "now"])


@app.command()
def visual():
    """TODO: Launch the dashboard for data post-processing and visualisation."""
    pass    # TODO
