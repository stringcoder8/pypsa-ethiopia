#!/usr/bin/env python
"""
Apply a drought shock to a prepared PyPSA-Earth network (MODELING_PLAN.md §3c).

Scales hydro availability down by a single calibrated factor representing a
severe, documented drought (default −50% = ×0.50, per Tegenu et al. 2022 and the
2022–23 event). Two things are scaled:

  * reservoir/dam hydro  -> `storage_units_t.inflow`   (carrier "hydro")
  * run-of-river hydro   -> `generators_t.p_max_pu`    (carrier "ror")

Pumped storage (PHS) is NOT touched — it is not rainfall-fed. The scaling is
uniform in time, so it preserves the year's seasonal shape (a known
simplification: real droughts also distort the shape — see §10 caveats).

This is a scenario transform on the ALREADY-PREPARED (post-cluster, pre-solve)
network. Chain it before `inject_geothermal.py`:

    prepared.nc --[apply_heg_demand]--> --[apply_drought]--> --[inject_geothermal]--> solve

USAGE
-----
    python apply_drought.py prepared.nc ET_dry.nc                 # default ×0.50
    python apply_drought.py prepared.nc ET_dry30.nc --factor 0.70 # −30% variant
"""
import argparse
import pypsa


def annual_energy_gwh(series_df, weights):
    """MWh->GWh annual energy of a (snapshot x asset) MW dataframe, weighted."""
    if series_df is None or series_df.empty:
        return 0.0
    return float(series_df.mul(weights, axis=0).sum().sum()) / 1e3


def apply_drought(n, factor):
    w = n.snapshot_weightings.objective

    # 1. reservoir hydro inflow (carrier "hydro")
    hydro = n.storage_units.index[n.storage_units.carrier == "hydro"]
    inflow_cols = n.storage_units_t.inflow.columns.intersection(hydro)
    inflow_before = annual_energy_gwh(n.storage_units_t.inflow[inflow_cols], w)
    n.storage_units_t.inflow[inflow_cols] = n.storage_units_t.inflow[inflow_cols] * factor
    inflow_after = annual_energy_gwh(n.storage_units_t.inflow[inflow_cols], w)

    # 2. run-of-river availability (carrier "ror")
    ror = n.generators.index[n.generators.carrier == "ror"]
    ror_cols = n.generators_t.p_max_pu.columns.intersection(ror)
    n.generators_t.p_max_pu[ror_cols] = n.generators_t.p_max_pu[ror_cols] * factor

    print(f"   drought factor ×{factor:.2f} (−{(1 - factor) * 100:.0f}%)")
    print(f"   reservoir hydro: {len(inflow_cols)} unit(s), "
          f"inflow {inflow_before:.0f} -> {inflow_after:.0f} GWh/yr")
    print(f"   run-of-river:    {len(ror_cols)} generator(s) scaled")
    if not len(inflow_cols) and not len(ror_cols):
        print("   WARNING: no hydro/ror time series found — nothing scaled. "
              "Check carrier names in the prepared network.")
    return n


def main():
    p = argparse.ArgumentParser(description="Apply a −X% hydro drought to a prepared network.")
    p.add_argument("in_path")
    p.add_argument("out_path")
    p.add_argument("--factor", type=float, default=0.50,
                   help="multiplier on hydro inflow / ror availability (default 0.50 = −50%%)")
    args = p.parse_args()

    print(f"Loading {args.in_path} ...")
    n = pypsa.Network(args.in_path)
    apply_drought(n, args.factor)
    n.export_to_netcdf(args.out_path)
    print(f"Saved -> {args.out_path}")


if __name__ == "__main__":
    main()
