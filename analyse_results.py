"""
STEP 8 — Analyse solved PyPSA / PyPSA-Earth networks (Ethiopia, Aim 1)
======================================================================
Loads one or more solved .nc networks, extracts the key Aim-1 metrics
(installed capacity, annual generation, system cost, CO2 emissions,
geothermal capacity & share), builds a cross-scenario comparison table,
and saves plots.

USAGE
-----
    python analyse_results.py path/to/network1.nc path/to/network2.nc ...
    # or point it at a folder of .nc files:
    python analyse_results.py results/networks/

The scenario name is taken from each file name, so name your runs clearly
(e.g. ET_baseline.nc, ET_co2-50.nc, ET_geo-frozen.nc, ET_dryhydro.nc).
"""

import sys
import glob
import os
import pandas as pd
import numpy as np
import pypsa
import matplotlib
matplotlib.use("Agg")          # no display needed; saves figures to file
import matplotlib.pyplot as plt


# ── helpers ──────────────────────────────────────────────────────────────────
def find_networks(args):
    """Accept a mix of .nc files and folders, return list of .nc paths."""
    paths = []
    for a in args:
        if os.path.isdir(a):
            paths += sorted(glob.glob(os.path.join(a, "*.nc")))
        elif a.endswith(".nc"):
            paths.append(a)
    return paths


def scenario_name(path):
    return os.path.splitext(os.path.basename(path))[0]


def generation_by_carrier(n):
    """Annual energy [MWh] per carrier, summing generators AND storage units
    (hydro is often a StorageUnit in PyPSA-Earth). Weighted by snapshot length."""
    # snapshot weighting (hours represented by each time step)
    try:
        w = n.snapshot_weightings.generators
    except Exception:
        w = n.snapshot_weightings.iloc[:, 0]

    energy = {}

    # generators
    if len(n.generators):
        gen = n.generators_t.p.multiply(w, axis=0).sum()          # MWh per generator
        by_c = gen.groupby(n.generators.carrier).sum()
        for c, v in by_c.items():
            energy[c] = energy.get(c, 0.0) + v

    # storage units (e.g. hydro reservoir) — count net positive dispatch
    if len(n.storage_units):
        sto = n.storage_units_t.p.clip(lower=0).multiply(w, axis=0).sum()
        by_c = sto.groupby(n.storage_units.carrier).sum()
        for c, v in by_c.items():
            energy[c] = energy.get(c, 0.0) + v

    return pd.Series(energy, name="MWh").sort_values(ascending=False)


def capacity_by_carrier(n):
    """Optimal installed capacity [MW] per carrier (generators + storage units)."""
    cap = {}
    if len(n.generators):
        col = "p_nom_opt" if "p_nom_opt" in n.generators else "p_nom"
        by_c = n.generators.groupby("carrier")[col].sum()
        for c, v in by_c.items():
            cap[c] = cap.get(c, 0.0) + v
    if len(n.storage_units):
        col = "p_nom_opt" if "p_nom_opt" in n.storage_units else "p_nom"
        by_c = n.storage_units.groupby("carrier")[col].sum()
        for c, v in by_c.items():
            cap[c] = cap.get(c, 0.0) + v
    return pd.Series(cap, name="MW").sort_values(ascending=False)


def co2_emissions(n):
    """Annual CO2 [tonnes]. Uses carrier co2_emissions [t/MWh_thermal] and
    generator efficiency: thermal_input = electrical_output / efficiency."""
    if not len(n.generators):
        return 0.0
    try:
        w = n.snapshot_weightings.generators
    except Exception:
        w = n.snapshot_weightings.iloc[:, 0]

    elec = n.generators_t.p.multiply(w, axis=0).sum()              # MWh_el per gen
    eff = n.generators.efficiency.reindex(elec.index).fillna(1.0)
    carrier = n.generators.carrier.reindex(elec.index)
    co2_factor = n.carriers.co2_emissions.reindex(carrier.values).fillna(0.0)
    co2_factor.index = elec.index
    thermal = elec / eff.replace(0, np.nan)
    emissions = (thermal * co2_factor).fillna(0.0).sum()
    return float(emissions)


def summarise(n, name):
    cap = capacity_by_carrier(n)
    gen = generation_by_carrier(n)
    total_gen = gen.sum()
    geo_cap = cap.get("geothermal", 0.0)
    geo_gen = gen.get("geothermal", 0.0)
    row = {
        "scenario": name,
        "system_cost_total": getattr(n, "objective", np.nan),
        "geothermal_MW": round(geo_cap, 1),
        "geothermal_gen_GWh": round(geo_gen / 1e3, 1),
        "geothermal_share_%": round(100 * geo_gen / total_gen, 1) if total_gen else 0.0,
        "CO2_tonnes": round(co2_emissions(n), 1),
        "total_gen_GWh": round(total_gen / 1e3, 1),
    }
    return row, cap, gen


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    paths = find_networks(args)
    if not paths:
        print("No .nc networks found at:", args)
        sys.exit(1)

    print(f"Found {len(paths)} network(s):")
    for p in paths:
        print("  -", p)
    print()

    rows = []
    caps = {}     # scenario -> capacity series
    gens = {}     # scenario -> generation series

    for p in paths:
        name = scenario_name(p)
        n = pypsa.Network(p)
        row, cap, gen = summarise(n, name)
        rows.append(row)
        caps[name] = cap
        gens[name] = gen
        print(f"── {name} ──")
        print(f"   total system cost : {row['system_cost_total']:,.0f}")
        print(f"   geothermal        : {row['geothermal_MW']} MW  "
              f"({row['geothermal_share_%']}% of generation)")
        print(f"   CO2 emissions     : {row['CO2_tonnes']:,.0f} t")
        print()

    # cross-scenario comparison table
    comp = pd.DataFrame(rows).set_index("scenario")
    comp.to_csv("scenario_comparison.csv")
    print("═" * 60)
    print("SCENARIO COMPARISON")
    print("═" * 60)
    print(comp.to_string())
    print("\nSaved -> scenario_comparison.csv")

    # ── Plot 1: installed capacity by carrier, per scenario (stacked bar) ──
    cap_df = pd.DataFrame(caps).fillna(0.0).T            # rows=scenarios, cols=carriers
    ax = cap_df.plot(kind="bar", stacked=True, figsize=(10, 6))
    ax.set_ylabel("Installed capacity [MW]")
    ax.set_title("Installed capacity by technology across scenarios")
    ax.legend(title="carrier", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig("capacity_by_scenario.png", dpi=150)
    plt.close()
    print("Saved -> capacity_by_scenario.png")

    # ── Plot 2: annual generation mix by carrier, per scenario ──
    gen_df = (pd.DataFrame(gens).fillna(0.0).T) / 1e3   # GWh
    ax = gen_df.plot(kind="bar", stacked=True, figsize=(10, 6))
    ax.set_ylabel("Annual generation [GWh]")
    ax.set_title("Generation mix by technology across scenarios")
    ax.legend(title="carrier", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig("generation_by_scenario.png", dpi=150)
    plt.close()
    print("Saved -> generation_by_scenario.png")

    # ── Plot 3: dispatch time series for the FIRST scenario (a sample week) ──
    n0 = pypsa.Network(paths[0])
    try:
        w = n0.snapshot_weightings.generators
    except Exception:
        w = None
    # build a carrier-aggregated dispatch frame
    disp = pd.DataFrame(index=n0.snapshots)
    if len(n0.generators):
        g = n0.generators_t.p.T.groupby(n0.generators.carrier).sum().T
        for c in g.columns:
            disp[c] = g[c]
    if len(n0.storage_units):
        s = n0.storage_units_t.p.clip(lower=0).T.groupby(n0.storage_units.carrier).sum().T
        for c in s.columns:
            disp[c] = disp.get(c, 0) + s[c]
    sample = disp.iloc[: min(168, len(disp))]            # first ~week
    ax = sample.plot.area(figsize=(12, 6), linewidth=0)
    ax.set_ylabel("Dispatch [MW]")
    ax.set_title(f"Hourly dispatch (first week) — {scenario_name(paths[0])}")
    ax.legend(title="carrier", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig("dispatch_sample_week.png", dpi=150)
    plt.close()
    print("Saved -> dispatch_sample_week.png")

    print("\nDone.")


if __name__ == "__main__":
    main()
