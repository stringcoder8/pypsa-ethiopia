#!/usr/bin/env python
"""
Drive the 18-run main factorial (MODELING_PLAN.md §6): for each horizon year,
build the calibrated per-year base network once, then produce and solve every
factorial cell (hydro x demand x geothermal) from it.

WHAT ONE CELL IS (chain, matches the smoke tests in MODELING_PLAN.md §9):
    base elec_s_<N>_ec_lcopt_<opts>.nc (per year, calibrated)
      -> apply_heg_demand.py   (only if demand == HEG)
      -> apply_drought.py      (only if hydro  == dry)
      -> inject_geothermal.py  (--year Y, or --frozen if geo == nogeo)
      -> solve_scenario.py     (adds load-shedding backstop, then optimises)

Output naming matches results_analysis.ipynb's auto-discovery pattern:
    scenarios/<year>_<hydro>_<demand>_<geo>.nc

CELL SET (§6): all 12 geo-available cells (year x hydro x demand) + the 6
geo-excluded twins for the DRY cells only = 18 runs. Pass --all-excluded to
also run the 6 normal-year excluded twins (24 runs, optional per §6).

USAGE
    # one year, dry-run (print the plan, do nothing):
    python run_factorial.py --year 2050 --dry-run

    # one year, for real, on the server:
    python run_factorial.py --year 2050 --solver highs

    # everything:
    python run_factorial.py --all --solver highs

    # resume: already-solved cells are skipped unless --force
    python run_factorial.py --all --solver highs

Each step's own script does the real work; this file only sequences them and
handles per-year base-network preparation (including the hydro calibration,
which is easy to forget and silently wrong if skipped — see RUNBOOK §6b).
"""
import argparse
import itertools
import subprocess
import sys
import time
from pathlib import Path

YEARS = [2030, 2040, 2050]
HYDRO = ["normal", "dry"]
DEMAND = ["GEGIS", "HEG"]

SCENARIOS_DIR = Path("scenarios")
TMP_DIR = SCENARIOS_DIR / "_tmp"


def run(cmd, log=None):
    print(f"   $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if log is not None:
        log.write(f"$ {' '.join(cmd)}\n{result.stdout}\n{result.stderr}\n")
    if result.returncode != 0:
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
        raise SystemExit(f"FAILED: {' '.join(cmd)}")
    return result.stdout


def base_network_path(year, clusters, opts):
    return Path(f"networks/ET_{year}/elec_s_{clusters}_ec_lcopt_{opts}.nc")


def ensure_base_network(year, clusters, opts, python, snakemake, force=False):
    """Build the per-year namespaced base network and calibrate its hydro
    inflow. Idempotent: skipped if the calibrated marker file already exists,
    unless --force."""
    configfile = f"config.ET_{year}.yaml"
    marker = Path(f"networks/ET_{year}/.calibrated")
    target = base_network_path(year, clusters, opts)

    if marker.exists() and target.exists() and not force:
        print(f"[{year}] base network + calibration already done, skipping "
              f"(delete {marker} to force a rebuild)")
        return target

    print(f"[{year}] building base network to elec.nc ...")
    run([snakemake, f"networks/ET_{year}/elec.nc",
         "-j1", "--rerun-triggers", "mtime", "--configfile", configfile])

    print(f"[{year}] calibrating hydro inflow (RUNBOOK §6b) ...")
    run([python, "calibrate_hydro_inflow.py", f"networks/ET_{year}/elec.nc"])

    print(f"[{year}] deleting stale downstream networks so they rebuild "
          f"from the calibrated elec.nc ...")
    for p in Path(f"networks/ET_{year}").glob("elec_s*.nc"):
        p.unlink()
    result_net = Path(f"results/ET_{year}/networks/elec_s_{clusters}_ec_lcopt_{opts}.nc")
    if result_net.exists():
        result_net.unlink()

    print(f"[{year}] building calibrated {target} ...")
    run([snakemake, str(target), "-j1", "--rerun-triggers", "mtime",
         "--configfile", configfile])

    marker.touch()
    return target


def cell_name(year, hydro, demand, geo):
    return f"{year}_{hydro}_{demand}_{geo}"


def build_cell(base_net, year, hydro, demand, geo, python, solver, force):
    name = cell_name(year, hydro, demand, geo)
    out_path = SCENARIOS_DIR / f"{name}.nc"
    if out_path.exists() and not force:
        print(f"  [{name}] already solved, skipping (use --force to redo)")
        return

    print(f"  [{name}] building ...")
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    current = base_net

    if demand == "HEG":
        step = TMP_DIR / f"{name}_step_heg.nc"
        run([python, "apply_heg_demand.py", str(current), str(step), "--year", str(year)])
        current = step

    if hydro == "dry":
        step = TMP_DIR / f"{name}_step_dry.nc"
        run([python, "apply_drought.py", str(current), str(step)])
        current = step

    unsolved = TMP_DIR / f"{name}_unsolved.nc"
    geo_args = ["--frozen"] if geo == "nogeo" else ["--year", str(year)]
    run([python, "inject_geothermal.py", str(current), str(unsolved)] + geo_args)

    t0 = time.time()
    run([python, "solve_scenario.py", str(unsolved), str(out_path), "--solver", solver])
    print(f"  [{name}] solved in {time.time() - t0:.0f}s -> {out_path}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--year", type=int, choices=YEARS, help="run a single horizon year")
    p.add_argument("--all", action="store_true", help="run all three years")
    p.add_argument("--all-excluded", action="store_true",
                   help="also run the 6 normal-year geo-excluded twins (24 runs total)")
    p.add_argument("--clusters", type=int, default=12)
    p.add_argument("--opts", default="4H")
    p.add_argument("--solver", default="gurobi", choices=["gurobi", "highs"],
                   help="gurobi (laptop) or highs (server, default there)")
    p.add_argument("--force", action="store_true",
                   help="rebuild/re-solve even if outputs already exist")
    p.add_argument("--dry-run", action="store_true", help="print the plan, run nothing")
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--snakemake", default="snakemake")
    args = p.parse_args()

    if not args.year and not args.all:
        p.error("give --year YYYY or --all")
    years = YEARS if args.all else [args.year]

    cells = []
    for year, hydro, demand in itertools.product(years, HYDRO, DEMAND):
        cells.append((year, hydro, demand, "geo"))
        if hydro == "dry" or args.all_excluded:
            cells.append((year, hydro, demand, "nogeo"))

    print(f"Plan: {len(years)} base network(s), {len(cells)} cell(s), "
          f"clusters={args.clusters}, opts={args.opts}, solver={args.solver}")
    for c in cells:
        print(f"   {cell_name(*c)}")
    if args.dry_run:
        print("\n--dry-run: stopping here.")
        return

    SCENARIOS_DIR.mkdir(exist_ok=True)
    for year in years:
        base_net = ensure_base_network(year, args.clusters, args.opts,
                                        args.python, args.snakemake, args.force)
        for (y, hydro, demand, geo) in [c for c in cells if c[0] == year]:
            build_cell(base_net, y, hydro, demand, geo, args.python, args.solver, args.force)

    print(f"\nDone. Solved cells are in {SCENARIOS_DIR}/ "
          "-- paste their paths into results_analysis.ipynb.")


if __name__ == "__main__":
    main()
