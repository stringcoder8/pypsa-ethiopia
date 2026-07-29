#!/usr/bin/env python
"""
Raise a prepared network's demand from GEGIS (low) to Gebremeskel HEG (high),
MODELING_PLAN.md §3b.

    High demand = GEGIS profile, uniformly rescaled to the HEG annual total.

Every load is multiplied by the same factor (HEG_target / GEGIS_total), so both
the temporal shape and the spatial distribution across buses are preserved
exactly; only the level changes.

WHY A UNIFORM RESCALE (and not a flat industrial block)
-------------------------------------------------------
An earlier version of this script added the increment as a constant,
round-the-clock block, reasoning that HEG growth is industrial and industry
runs ~24/7. That was withdrawn:

  - The increment is ~87% of the HEG total (2050: 34 TWh GEGIS + 255 TWh
    increment), so the flat block did not modify the profile — it *became* the
    profile, giving a national load factor of 0.98 and a diurnal swing of 1.03.
    No real grid is that flat; even Iceland, which is ~80% aluminium smelters,
    is around 0.94.
  - It also tilted the study toward its own hypothesis. Flat demand is the
    shape that firm baseload serves best, and it is simultaneously the worst
    case for solar, so assuming it quietly pre-loaded the conclusion that
    geothermal is valuable.

A uniform rescale makes no claim about the composition of demand growth, which
is the more neutral assumption to defend.

KNOWN LIMITATIONS — state these in the write-up
------------------------------------------------
1. The rescale inherits the GEGIS shape, which is flatter than Ethiopia's
   observed load curve. GEGIS (raw hourly) has a diurnal swing of 1.31, a night
   floor at 77% of peak, and peaks at 17:00. EEP's measured national curve
   swings ~2.6, drops to ~38% of peak overnight, and peaks at 19:00. GEGIS also
   shows no weekday/weekend structure (ratio 0.98).
2. Rescaling assumes demand composition is invariant while the system grows
   ~8x. Industrialisation would in reality raise the load factor somewhat, so
   the true 2050 shape likely sits between this profile and a flatter one.

Both are limitations of the demand data and of the scenario framing, not of the
rescale itself. Neither is resolved here.

Chain this BEFORE the drought / geothermal transforms:

    prepared.nc --[apply_heg_demand]--> --[apply_drought]--> --[inject_geothermal]--> solve

HEG targets (TWh/yr, Gebremeskel 2021 High-Economic-Growth, §3b):
    2030 = 112 · 2040 = 201 · 2050 = 289

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

    base = load_matrix(n)
    base_energy_mwh = base.mul(w, axis=0).sum()               # per load, MWh/yr
    base_total_twh = base_energy_mwh.sum() / 1e6

    if target_twh <= base_total_twh:
        raise SystemExit(
            f"HEG target {target_twh:.0f} TWh <= GEGIS base {base_total_twh:.1f} TWh; "
            "nothing to add (is the network's prediction_year the one you meant?).")

    factor = target_twh / base_total_twh

    # uniform multiplicative rescale: shape and bus shares both preserved
    for ld in n.loads.index:
        n.loads_t.p_set[ld] = base[ld] * factor
    # any load that was static-only is now time-varying; clear its scalar p_set
    n.loads.loc[:, "p_set"] = 0.0

    new = load_matrix(n)
    new_total_twh = new.mul(w, axis=0).sum().sum() / 1e6
    nat = new.sum(axis=1)
    peak, mean = nat.max(), (nat * w).sum() / w.sum()
    print(f"   GEGIS base demand : {base_total_twh:6.1f} TWh/yr")
    print(f"   HEG target        : {target_twh:6.1f} TWh/yr")
    print(f"   rescale factor    : x{factor:.3f} (uniform, shape preserved)")
    print(f"   realized new total: {new_total_twh:6.1f} TWh/yr")
    print(f"   national peak {peak/1e3:.2f} GW | mean {mean/1e3:.2f} GW "
          f"| load factor {mean/peak:.3f}")
    return n


def main():
    p = argparse.ArgumentParser(
        description="Raise demand GEGIS -> HEG (uniform rescale, shape preserved).")
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
