#!/usr/bin/env python
"""
Per-plant hydro inflow calibration (run on networks/elec.nc, BEFORE clustering).

WHY. atlite/hydrobasins allocates runoff by the basin a plant sits in, which
starves plants whose real water comes from a huge upstream catchment. For
Ethiopia this hits GERD hardest: 46% of fleet capacity but only ~15% of modeled
inflow (CF 0.10 vs design 0.35). A national normalization multiplier cannot fix
this distribution problem — extra water lands at small plants that spill it.

WHAT. Rescale each hydro storage unit's inflow time series so its ANNUAL total
matches a defensible per-plant target, keeping the ERA5 seasonal SHAPE:

  * GERD (p_nom ~5,150 MW): 15,759 GWh/yr — official design annual output.
  * every other reservoir:  p_nom x CF 0.42 x 8760 h — the pre-GERD fleet's
    actual capacity factor (IRENA 2021: 14,943 GWh from 4,071 MW).
  * run-of-river generators: p_max_pu scaled toward CF 0.42, clipped at 1.0
    (ror availability can never exceed nameplate).

National total lands at ~38.6 TWh/yr, consistent with the config.yaml
normalization target (rest-of-fleet 2021 actual + GERD design + Koysha est.).

USAGE (in place, then force the downstream rules to rebuild):
    python calibrate_hydro_inflow.py networks/elec.nc
    # then: delete networks/elec_s*.nc + results, snakemake solve_all_networks
"""
import sys
import pypsa

GERD_DESIGN_GWH = 15759.0   # official GERD design annual output
FLEET_CF = 0.42             # IRENA 2021 Ethiopia fleet actual (14,943 GWh / 4,071 MW)


def calibrate(n):
    w = n.snapshot_weightings.objective  # -> hours represented by each snapshot

    # ── reservoir hydro: scale inflow to per-plant annual targets ────────────
    su = n.storage_units[n.storage_units.carrier == "hydro"]
    print(f"reservoir units: {len(su)}")
    for name, row in su.iterrows():
        if name not in n.storage_units_t.inflow.columns:
            print(f"  {name:35s} NO INFLOW SERIES — skipped")
            continue
        series = n.storage_units_t.inflow[name]
        current_gwh = float((series * w).sum()) / 1e3
        is_gerd = round(row.p_nom) == 5150
        target_gwh = GERD_DESIGN_GWH if is_gerd else row.p_nom * FLEET_CF * 8760 / 1e3
        if current_gwh <= 0:
            print(f"  {name:35s} zero inflow — cannot scale, left as-is")
            continue
        factor = target_gwh / current_gwh
        n.storage_units_t.inflow[name] = series * factor
        tag = "GERD (design)" if is_gerd else f"CF {FLEET_CF}"
        print(f"  {name:35s} {current_gwh:8.0f} -> {target_gwh:8.0f} GWh/yr "
              f"(x{factor:5.2f}, {tag})")

    # ── run-of-river: scale availability toward fleet CF, clipped at 1 ──────
    ror = n.generators[n.generators.carrier == "ror"]
    for name, row in ror.iterrows():
        if name not in n.generators_t.p_max_pu.columns:
            continue
        series = n.generators_t.p_max_pu[name]
        current_cf = float((series * w).sum()) / 8760.0
        if current_cf <= 0:
            print(f"  {name:35s} (ror) zero availability — left as-is")
            continue
        scaled = (series * (FLEET_CF / current_cf)).clip(upper=1.0)
        realized = float((scaled * w).sum()) / 8760.0
        n.generators_t.p_max_pu[name] = scaled
        print(f"  {name:35s} (ror) CF {current_cf:.2f} -> {realized:.2f} (clip at 1)")

    # ── summary ──────────────────────────────────────────────────────────────
    cols = n.storage_units_t.inflow.columns.intersection(su.index)
    total = float(n.storage_units_t.inflow[cols].mul(w, axis=0).sum().sum()) / 1e3
    print(f"\nnational reservoir inflow after calibration: {total:,.0f} GWh/yr "
          f"(target ~38,100 + ror)")
    return n


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else path  # default: in place
    print(f"Loading {path} ...")
    n = pypsa.Network(path)
    calibrate(n)
    n.export_to_netcdf(out)
    print(f"Saved -> {out}")


if __name__ == "__main__":
    main()
