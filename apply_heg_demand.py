#!/usr/bin/env python
"""
Raise a prepared network's demand from GEGIS (low) to Gebremeskel HEG (high),
MODELING_PLAN.md §3b.

The high demand case is NOT a uniform rescale of the peaky GEGIS profile — that
would keep a residential/temperature shape for what is really *industrial*
growth. Instead:

    High demand = GEGIS base  +  flat industrial increment

The network already carries the GEGIS profile for its build year (set via
`load_options.prediction_year` in the config). This script keeps that base
untouched and adds the remainder `(HEG_target − GEGIS_total)` as a
**constant, round-the-clock block** — industrial parks run ~24/7 baseload, not
on a population demand curve. The increment is distributed across buses in
proportion to each bus's existing load share (a defensible first pass; a
refinement would place it only on designated industrial-park buses — see §3b).

Because the added block is time-flat, this is *conservative* for the thesis: a
peakier profile would understate the value of firm baseload geothermal.

HEG targets (TWh/yr, Gebremeskel 2021 High-Economic-Growth, §3b):
    2030 = 112 · 2040 = 201 · 2050 = 289

Chain this BEFORE the drought / geothermal transforms:

    prepared.nc --[apply_heg_demand]--> --[apply_drought]--> --[inject_geothermal]--> solve

USAGE
-----
    python apply_heg_demand.py prepared_2030.nc ET_2030_heg.nc --year 2030
    python apply_heg_demand.py prepared.nc out.nc --target-twh 250   # explicit override
"""
import argparse
import pypsa

HEG_TARGET_TWH = {2030: 112.0, 2040: 201.0, 2050: 289.0}


def load_matrix(n):
    """Return the (snapshot x load) demand dataframe, from loads_t.p_set,
    filling any static-only loads from loads.p_set."""
    df = n.loads_t.p_set.copy()
    static_only = n.loads.index.difference(df.columns)
    for ld in static_only:
        df[ld] = n.loads.at[ld, "p_set"]
    return df[n.loads.index]


def apply_heg(n, target_twh):
    w = n.snapshot_weightings.objective
    total_hours = float(w.sum())

    base = load_matrix(n)
    base_energy_mwh = base.mul(w, axis=0).sum()               # per load, MWh/yr
    base_total_twh = base_energy_mwh.sum() / 1e6

    increment_twh = target_twh - base_total_twh
    if increment_twh <= 0:
        raise SystemExit(
            f"HEG target {target_twh:.0f} TWh <= GEGIS base {base_total_twh:.1f} TWh; "
            "nothing to add (is the network's prediction_year the one you meant?).")

    # flat block, distributed by each load's share of base energy
    share = base_energy_mwh / base_energy_mwh.sum()
    flat_total_mw = increment_twh * 1e6 / total_hours          # constant MW over the year
    add_mw = flat_total_mw * share                             # per load, constant MW

    # write the time-flat increment onto every snapshot
    for ld in n.loads.index:
        col = base[ld] + add_mw[ld]
        n.loads_t.p_set[ld] = col
    # any load that was static-only is now time-varying; clear its scalar p_set
    n.loads.loc[:, "p_set"] = 0.0

    new_total_twh = load_matrix(n).mul(w, axis=0).sum().sum() / 1e6
    print(f"   GEGIS base demand : {base_total_twh:6.1f} TWh/yr")
    print(f"   HEG target        : {target_twh:6.1f} TWh/yr")
    print(f"   flat increment    : +{increment_twh:6.1f} TWh/yr "
          f"= {flat_total_mw:,.0f} MW constant, spread over {len(n.loads.index)} bus load(s)")
    print(f"   realized new total: {new_total_twh:6.1f} TWh/yr")
    return n


def main():
    p = argparse.ArgumentParser(description="Raise demand GEGIS -> HEG (flat industrial increment).")
    p.add_argument("in_path")
    p.add_argument("out_path")
    p.add_argument("--year", type=int, choices=sorted(HEG_TARGET_TWH),
                   help="horizon year -> HEG target (2030/2040/2050)")
    p.add_argument("--target-twh", type=float,
                   help="explicit HEG total TWh/yr (overrides --year)")
    args = p.parse_args()

    if args.target_twh is None and args.year is None:
        p.error("give --year or --target-twh")
    target = args.target_twh if args.target_twh is not None else HEG_TARGET_TWH[args.year]

    print(f"Loading {args.in_path} ...")
    n = pypsa.Network(args.in_path)
    apply_heg(n, target)
    n.export_to_netcdf(args.out_path)
    print(f"Saved -> {args.out_path}")


if __name__ == "__main__":
    main()
