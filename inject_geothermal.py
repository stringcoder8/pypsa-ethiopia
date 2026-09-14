"""
STEP 6 — Inject Ethiopia geothermal into a PyPSA-Earth network (JICA sites, FLASH)
================================================================================
Core methodological contribution of the thesis. PyPSA-Earth's default geothermal
representation is thin, so here we add geothermal as *named, capped, extendable*
generators built from the JICA Master Plan site inventory:

  * one generator per JICA prospect (Corbetti, Tulu Moye, Tendaho-Dubti, ...),
  * attached to the nearest electrical (AC) bus of the clustered network,
  * capped at the site's JICA installed capacity (Table 5.3, most-probable),
  * FLASH technology for ALL sites (single-flash) — see note below,
  * baseload availability (`p_max_pu = capacity factor`),
  * cost = Zuffi FLASH LCOE ($/MWh, already levelised), converted USD->EUR and
    then to an annualised capital cost, so the optimiser sees exactly that
    levelised cost in the model's own currency:
        capital_cost [EUR/MW/yr] = LCOE[$/MWh] * USD_TO_EUR * 8760 * CF.

CURRENCY (fixed 2026-09-13, rate corrected 2026-09-14 -- see USD_TO_EUR below)
-------------------------------------------------------------------------------
PyPSA-Earth's cost base is **EUR in 2020 prices**: `config.default.yaml` sets
`output_currency: "EUR"`, `scripts/process_cost_data.py` fixes
`TECH_DATA_REFERENCE_YEAR = 2020`, and every row of the generated
`costs_<year>.csv` carries an explicit EUR unit (e.g.
`solar,investment,408.7174,EUR/kW_e`). The geothermal LCOEs from Zuffi and JICA
are in **USD**.

History of the bias:
  * until 2026-09-13 the USD figures went straight into `capital_cost` (factor
    1.0), so geothermal was ~14% too expensive against every other technology;
  * 2026-09-13 to 2026-09-14 the fix used 0.7532 (the 2013 rate, taken from
    `costs.default_exchange_rate`, which is only PyPSA-Earth's fallback), so
    geothermal was ~14% too cheap;
  * from 2026-09-14 it uses 0.8772, the 2020 reference-year rate PyPSA-Earth
    itself applies to USD inputs. Every run solved before this carries one of
    the two biases and must be re-solved.

DATA SOURCE (single source of truth): `_thesis_inputs/JICA_Geothermal_Sites_Ethiopia.xlsx`
— one row per prospect with JICA capacity, Zuffi FLASH LCOE and coordinates.
Capacity per site = JICA Table-5.3 installed value (falls back to the
Monte-Carlo mode where 5.3 is blank).

CAPACITY = a SINGLE value per site (JICA), NOT a scenario axis. The low/planned/
high capacity scenarios have been dropped to cut the number of runs; each site's
`p_nom_max` is its JICA capacity and the optimiser decides how much to build.

TECHNOLOGY = FLASH for every site, for simplicity. JICA's 200 °C rule would put
the two class-D sites (Gedemsa, Kone) on binary/ORC, but we standardise on flash
across the board; swap the cost column to ORC if a binary variant is needed.

Only geothermal is supplied by us; every other technology (PV, wind, hydro,
storage) keeps PyPSA-Earth's own costs and potentials.

USAGE
-----
    # geothermal allowed to expand up to each site's FULL JICA capacity (~4.1 GWe):
    python inject_geothermal.py prepared.nc ET_geo_on_unsolved.nc
    # year-phased ceiling (§3a): 2030 ~371 MWe, 2040 ~2.06 GWe, 2050 full:
    python inject_geothermal.py prepared.nc ET_geo_on_2030_unsolved.nc --year 2030
    # "frozen" reference (today's ~7 MW, no expansion):
    python inject_geothermal.py prepared.nc ET_geo_frozen_unsolved.nc --frozen
    # JICA-cost sensitivity (§7 bias check, ~2-4x higher than Zuffi FLASH):
    python inject_geothermal.py prepared.nc ET_geo_jica_unsolved.nc --year 2050 --lcoe jica
    # Middle cost scenario: 50% between Zuffi (Low) and JICA (High), per site:
    python inject_geothermal.py prepared.nc ET_geo_blend50_unsolved.nc --year 2050 --lcoe-blend 0.5
"""

import sys
import os
import numpy as np
import pandas as pd
import pypsa


# ── 1. ASSUMPTIONS — edit to match the thesis ────────────────────────────────
GEO_XLSX        = os.path.join("_thesis_inputs", "JICA_Geothermal_Sites_Ethiopia.xlsx")   # single source of truth
GEO_SHEET       = "Sheet1"
GEO_CAPACITY_FACTOR = 0.90              # baseload flash-plant availability
GEO_CARRIER     = "geothermal"

# USD -> EUR. The site LCOEs (Zuffi, JICA) are in USD; the rest of the model is
# in EUR of 2020 (see the CURRENCY note in the module docstring).
#
# 0.8772 is exactly what PyPSA-Earth uses for its own USD inputs: the 2020
# average ECB rate returned by
#   process_cost_data.get_yearly_currency_exchange_rate("USD", "EUR",
#       future_exchange_rate_strategy="reference")      # TECH_DATA_REFERENCE_YEAR = 2020
# Do NOT use `costs.default_exchange_rate` (0.7532) from config.default.yaml --
# that is the 2013 rate and only a fallback for when no 2020 data exists.
# A current rate would also be wrong: it would state geothermal in euros of a
# different year than every other technology (2025 avg 0.8865, only ~1% off).
#
# CAVEAT carried into the write-up: the source LCOEs are not deflated to 2020
# -- JICA's figures are USD of its 2015 Master Plan, Zuffi's come from the
# Geothermal Atlas for Africa (presented 2022). PyPSA-Earth treats its own cost
# data the same way (all rows *assumed* to be in 2020 prices, no inflation
# adjustment; its `currency_year` column is provenance only).
USD_TO_EUR = 0.8772

# "frozen" scenario: today's installed geothermal in Ethiopia (Aluto-Langano ~7 MW)
FROZEN_TODAY_MW = 7.0

# Year-phased ceiling (MODELING_PLAN.md §3a). The full ~4.1 GWe JICA resource is
# NOT buildable from year one (Ethiopia built 7 MW in 25 yr; the EEP plan targets
# ~370 MW geothermal by 2030). Each site's JICA cap is scaled uniformly by year:
#   2030 ×0.09 -> ~371 MWe  (EEP 2030 pipeline realism)
#   2040 ×0.50 -> ~2.06 GWe (interpolated mid-buildout)
#   2050 ×1.00 -> ~4.13 GWe (full JICA developable resource)
# No --year given -> ×1.0 (full resource), for backward compatibility.
YEAR_SCALE = {2030: 0.09, 2040: 0.50, 2050: 1.00}

# Optional grid-connection cost. The JICA sheet has no distance-to-substation
# column, so this is OFF by default (its effect is ~1-2% of geothermal capex).
# To re-enable, add a distance column to the sheet and set USE_CONNECTION_COST.
USE_CONNECTION_COST = False
LINE_USD_PER_MW_KM  = 1000.0            # overnight HV line + connection cost
LINE_LIFETIME       = 40                # years
CONN_WACC           = 0.10              # discount rate for the connection annuity

# Column matching (case-insensitive substring match; robust to minor renames)
COL_NAME   = ["JICA Site", "Site"]                      # site name
COL_CAP    = ["installed", "MW"]                         # JICA installed (T5.3)
COL_CAP_FB = ["mode", "MW"]                              # fallback: JICA mode
# LCOE source (§7 bias check): Zuffi FLASH is the central/default case; JICA's own
# LCOE is ~2-4x higher, used as a sensitivity to test whether geothermal is still
# chosen at a conservative national cost estimate. 2 sites (Kone, Gedemsa) have no
# JICA LCOE figure and are dropped when --lcoe jica is used (noted at read time).
COL_LCOE_BY_SOURCE = {
    "zuffi": ["Zuffi", "FLASH", "LCOE"],
    "jica":  ["JICA", "LCOE"],
}
COL_LCOE   = COL_LCOE_BY_SOURCE["zuffi"]                 # default; read_sites() picks per lcoe_source

# --- Middle cost scenario (--lcoe-blend ALPHA) --------------------------------
# Linear per-site interpolation  lcoe = zuffi + ALPHA * (jica - zuffi), giving a
# Low (Zuffi, ALPHA=0) / Middle (ALPHA=0.5) / High (JICA, ALPHA=1) scenario set.
#
# PROXY SUBSTITUTION: Gedemsa and Kone have NO JICA LCOE at all (which is why the
# pure --lcoe jica runs drop them). Dropping them from the blend too would change
# the site set between scenarios and make the Low/Middle/High comparison
# inconsistent, so each borrows the JICA LCOE of a comparable site instead:
#   Gedemsa <- Tulu Moye (103.7 $/MWh)   Kone <- Meteka (73.1 $/MWh)
# These are STAND-INS, not JICA estimates for those sites -- state this wherever
# blend results are reported. Both are small (37 + 14 MW of ~4.1 GW).
JICA_LCOE_PROXY = {
    "gedemsa": ("Tulu Moye", 103.7),
    "kone":    ("Meteka",     73.1),
}
COL_LAT    = ["Lat"]
COL_LON    = ["Lon"]
COL_DIST   = ["distance", "km"]                          # optional

# Side-car coordinates: used when the sheet has no Lat/Lon columns. Join on name.
COORDS_CSV  = os.path.join("_thesis_inputs", "geo_site_coords.csv")
COORDS_NAME = "JICA Site"
COORDS_LAT  = "lat"
COORDS_LON  = "lon"


# ── 2. Cost helpers ──────────────────────────────────────────────────────────
def annuity(rate, n):
    """Capital recovery factor."""
    return 1.0 / n if rate == 0 else rate / (1.0 - (1.0 + rate) ** (-n))


def lcoe_to_capital_cost(lcoe_usd_per_mwh, capacity_factor):
    """Annualised capital cost (EUR/MW/yr) such that a plant running at
    `capacity_factor` recovers exactly `lcoe_usd_per_mwh`. Geothermal is ~all
    capex / negligible fuel, so marginal_cost is ~0 and the whole levelised
    cost is carried as an annualised capacity cost.

    NB the USD->EUR factor: the LCOE arrives in USD, but `capital_cost` is read
    by the solver in the model's currency (EUR of 2020). Dropping it makes
    geothermal ~14% too expensive against every other technology."""
    return float(lcoe_usd_per_mwh) * USD_TO_EUR * 8760.0 * float(capacity_factor)


def connection_capital_cost(distance_km):
    """Annualised grid-connection cost (EUR/MW/yr) for a line of `distance_km`."""
    if not USE_CONNECTION_COST or not np.isfinite(distance_km):
        return 0.0
    return (LINE_USD_PER_MW_KM * USD_TO_EUR * float(distance_km)
            * annuity(CONN_WACC, LINE_LIFETIME))


# ── 3. Read JICA per-site data ───────────────────────────────────────────────
def find_xlsx(path):
    cands = [path,
             os.path.join("pypsa-earth", path),
             os.path.join(os.path.dirname(__file__), path),
             os.path.join(os.path.dirname(__file__), "pypsa-earth", path)]
    for c in cands:
        if os.path.isfile(c):
            return c
    raise FileNotFoundError(f"{path} not found (looked in {cands})")


def pick_col(df, keywords, required=True):
    """Return the first column whose name contains ALL keywords (case-insens.)."""
    for col in df.columns:
        low = str(col).lower()
        if all(k.lower() in low for k in keywords):
            return col
    if required:
        raise KeyError(f"no column matching {keywords} in {list(df.columns)}")
    return None


def read_sites(xlsx=GEO_XLSX, sheet=GEO_SHEET, lcoe_source="zuffi", blend=None):
    """Return DataFrame [Name, lon, lat, lcoe_usd_mwh, cap_mw, distance_km].
    Capacity = JICA installed (Table 5.3), falling back to JICA mode.
    LCOE = Zuffi FLASH (default) or JICA's own LCOE ($/MWh, already levelised),
    selected via lcoe_source ("zuffi" | "jica") -- see COL_LCOE_BY_SOURCE (§7).
    If `blend` is a float in [0,1] it OVERRIDES lcoe_source and interpolates
    per site: lcoe = zuffi + blend*(jica - zuffi), using JICA_LCOE_PROXY for the
    two sites with no JICA figure (documented substitution -- see that constant).
    Rows missing name / capacity / LCOE / coordinates are dropped with a note."""
    path = find_xlsx(xlsx)
    xls = pd.ExcelFile(path)
    if sheet in xls.sheet_names:
        use_sheet = sheet
    else:                                    # tab renamed (e.g. by Excel) -> find it
        cand = [s for s in xls.sheet_names if "jica" in s.lower() or "site" in s.lower()]
        use_sheet = cand[0] if cand else xls.sheet_names[0]
        print(f"   sheet '{sheet}' not found; using '{use_sheet}' "
              f"(available: {xls.sheet_names})")
    df = pd.read_excel(xls, sheet_name=use_sheet)

    lcoe_source = lcoe_source.lower()
    if lcoe_source not in COL_LCOE_BY_SOURCE:
        raise ValueError(f"lcoe_source must be one of {list(COL_LCOE_BY_SOURCE)}, got {lcoe_source!r}")

    c_name = pick_col(df, COL_NAME)
    names_raw = df[pick_col(df, COL_NAME)].astype(str).str.strip()

    if blend is None:
        c_lcoe = pick_col(df, COL_LCOE_BY_SOURCE[lcoe_source])
        print(f"   LCOE source: {lcoe_source} (column: {c_lcoe!r})")
        lcoe_values = pd.to_numeric(df[c_lcoe], errors="coerce")
    else:
        blend = float(blend)
        if not 0.0 <= blend <= 1.0:
            raise ValueError(f"--lcoe-blend must be in [0,1], got {blend}")
        c_z = pick_col(df, COL_LCOE_BY_SOURCE["zuffi"])
        c_j = pick_col(df, COL_LCOE_BY_SOURCE["jica"])
        z = pd.to_numeric(df[c_z], errors="coerce")
        j = pd.to_numeric(df[c_j], errors="coerce")
        # fill the two missing JICA values with their documented proxies
        applied = []
        for i, nm in names_raw.items():
            key = nm.lower()
            for pk, (src, val) in JICA_LCOE_PROXY.items():
                if pk in key and not np.isfinite(j.get(i, np.nan)):
                    j.at[i] = val
                    applied.append(f"{nm}<-{src}({val})")
        lcoe_values = z + blend * (j - z)
        print(f"   LCOE source: BLEND alpha={blend:g} "
              f"(0=Zuffi {c_z!r}, 1=JICA {c_j!r})")
        if applied:
            print(f"   JICA proxy substitutions applied: {', '.join(applied)}")
    # a single synthetic column keeps the rest of the function unchanged
    c_lcoe = "_lcoe_selected"
    df[c_lcoe] = lcoe_values
    c_lat  = pick_col(df, COL_LAT, required=False)
    c_lon  = pick_col(df, COL_LON, required=False)
    try:
        c_cap = pick_col(df, COL_CAP)
    except KeyError:
        c_cap = None
    c_cap_fb = pick_col(df, COL_CAP_FB, required=False)
    c_dist   = pick_col(df, COL_DIST, required=False)

    cap = pd.to_numeric(df[c_cap], errors="coerce") if c_cap else pd.Series(np.nan, index=df.index)
    if c_cap_fb is not None:                       # fill blanks with the mode capacity
        cap = cap.fillna(pd.to_numeric(df[c_cap_fb], errors="coerce"))

    names = df[c_name].astype(str).str.strip()

    # coordinates: from the sheet if it has Lat/Lon, else from the side-car CSV (join on name)
    if c_lat is not None and c_lon is not None:
        lat = pd.to_numeric(df[c_lat], errors="coerce").values
        lon = pd.to_numeric(df[c_lon], errors="coerce").values
    else:
        coords = pd.read_csv(find_xlsx(COORDS_CSV))
        cmap = {str(k).strip().casefold(): (float(la), float(lo))
                for k, la, lo in zip(coords[COORDS_NAME], coords[COORDS_LAT], coords[COORDS_LON])}
        lat = names.str.casefold().map(lambda x: cmap.get(x, (np.nan, np.nan))[0]).values
        lon = names.str.casefold().map(lambda x: cmap.get(x, (np.nan, np.nan))[1]).values
        nomatch = sorted(set(names[~names.str.casefold().isin(cmap)]))
        if nomatch:
            print(f"   no coords in {COORDS_CSV} for: {nomatch} -> those rows skipped")

    out = pd.DataFrame({
        "Name": names.values,
        "lat":  lat,
        "lon":  lon,
        "lcoe_usd_mwh": pd.to_numeric(df[c_lcoe], errors="coerce").values,
        "cap_mw": cap.values,
        "distance_km": (pd.to_numeric(df[c_dist], errors="coerce").fillna(0.0).values
                        if c_dist is not None else 0.0),
    })

    before = len(out)
    ok = out.dropna(subset=["lat", "lon", "lcoe_usd_mwh", "cap_mw"]).copy()
    ok = ok[(ok["cap_mw"] > 0) & (ok["lcoe_usd_mwh"] > 0)].reset_index(drop=True)
    dropped = out[~out["Name"].isin(ok["Name"])]
    if len(dropped):
        print(f"   dropped {before - len(ok)} row(s) missing cap/LCOE/coords: "
              f"{list(dropped['Name'])}")
    print(f"   JICA sites usable: {len(ok)} | total p_nom_max {ok['cap_mw'].sum():.0f} MWe "
          f"| FLASH LCOE {ok['lcoe_usd_mwh'].min():.1f}-{ok['lcoe_usd_mwh'].max():.1f} $/MWh")
    return ok


# ── 4. Nearest electrical bus ────────────────────────────────────────────────
def ac_buses(n):
    b = n.buses
    if "carrier" in b.columns and (b.carrier == "AC").any():
        b = b[b.carrier == "AC"]
    return b


def nearest_bus(buses, lon, lat):
    d = (buses.x - lon) ** 2 + (buses.y - lat) ** 2   # planar nn is fine within a country
    return d.idxmin()


# ── 5. Inject ────────────────────────────────────────────────────────────────
def inject(n, sites, extendable=True, frozen_today_mw=FROZEN_TODAY_MW):
    if GEO_CARRIER not in n.carriers.index:
        n.add("Carrier", GEO_CARRIER, co2_emissions=0.0)
    else:
        n.carriers.loc[GEO_CARRIER, "co2_emissions"] = 0.0

    buses = ac_buses(n)
    assigned = {}
    for _, s in sites.iterrows():
        bus = nearest_bus(buses, s["lon"], s["lat"])
        name = f"geothermal {s['Name']}"
        if name in n.generators.index:
            n.remove("Generator", name)
        # geothermal levelised cost (Zuffi FLASH LCOE) + optional grid-connection cost
        cap_cost = (lcoe_to_capital_cost(s["lcoe_usd_mwh"], GEO_CAPACITY_FACTOR)
                    + connection_capital_cost(s.get("distance_km", 0.0)))
        n.add("Generator", name,
              bus=bus, carrier=GEO_CARRIER,
              p_nom_extendable=bool(extendable),
              p_nom_max=float(s["cap_mw"]),
              p_max_pu=GEO_CAPACITY_FACTOR,
              capital_cost=cap_cost,
              marginal_cost=0.0,
              efficiency=1.0)
        assigned[s["Name"]] = bus

    if not extendable:
        # "frozen" reference: only today's plants exist, no expansion.
        # The curated fleet (data/custom_powerplants.csv) already contains the
        # real Aluto-Langano (7.3 MW), so if fleet geothermal is present we zero
        # ALL injected sites — otherwise (old powerplantmatching fleets that
        # missed Aluto) keep the cheapest site as a FROZEN_TODAY_MW proxy.
        injected = {f"geothermal {nm}" for nm in assigned}
        fleet_geo_mw = n.generators.loc[
            (n.generators.carrier == GEO_CARRIER)
            & (~n.generators.index.isin(injected)), "p_nom"].sum()
        proxy_needed = fleet_geo_mw < 1.0
        cheapest = sites.sort_values("lcoe_usd_mwh").iloc[0]["Name"]
        for nm in list(assigned):
            g = f"geothermal {nm}"
            if proxy_needed and nm == cheapest:
                n.generators.loc[g, ["p_nom", "p_nom_max"]] = frozen_today_mw, frozen_today_mw
            else:
                n.generators.loc[g, ["p_nom", "p_nom_max"]] = 0.0, 0.0
        print(f"   frozen mode: fleet geothermal {fleet_geo_mw:.1f} MW "
              + ("(no proxy added)" if not proxy_needed
                 else f"absent -> {frozen_today_mw} MW proxy at cheapest site"))

    n_b = sites.groupby([nearest_bus(buses, r.lon, r.lat) for r in sites.itertuples()]).size()
    lo, hi = sites["lcoe_usd_mwh"].min(), sites["lcoe_usd_mwh"].max()
    print(f"   currency: LCOE {lo:.1f}-{hi:.1f} $/MWh x {USD_TO_EUR} "
          f"-> {lo * USD_TO_EUR:.1f}-{hi * USD_TO_EUR:.1f} EUR/MWh "
          f"(model currency; see CURRENCY note)")
    print(f"   added {len(sites)} geothermal generators across {n_b.shape[0]} bus(es): "
          f"{dict(n_b)}")
    print(f"   total p_nom_max = {sites['cap_mw'].sum():.0f} MWe, "
          f"extendable={extendable}" + ("" if extendable else f" (frozen {frozen_today_mw} MW)"))
    return n


def main():
    # minimal parser: two positionals (in, out), flag --frozen,
    # options --year[=]YYYY, --lcoe[=]{zuffi,jica}, --lcoe-blend[=]ALPHA
    argv = sys.argv[1:]
    frozen = "--frozen" in argv
    year, lcoe_source, blend, pos, i = None, "zuffi", None, [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--frozen":
            i += 1; continue
        if a.startswith("--year"):
            year = int(a.split("=", 1)[1]) if "=" in a else int(argv[i + 1])
            i += 1 if "=" in a else 2
            continue
        # NB: check --lcoe-blend BEFORE --lcoe, otherwise the prefix match eats it
        if a.startswith("--lcoe-blend"):
            blend = float(a.split("=", 1)[1]) if "=" in a else float(argv[i + 1])
            i += 1 if "=" in a else 2
            continue
        if a.startswith("--lcoe"):
            lcoe_source = a.split("=", 1)[1] if "=" in a else argv[i + 1]
            i += 1 if "=" in a else 2
            continue
        if a.startswith("--"):
            i += 1; continue                       # ignore unknown flags
        pos.append(a); i += 1
    if len(pos) < 2:
        print(__doc__)
        sys.exit(1)
    in_path, out_path = pos[0], pos[1]

    print(f"Loading {in_path} ...")
    n = pypsa.Network(in_path)
    sites = read_sites(lcoe_source=lcoe_source, blend=blend)
    if year is not None:
        scale = YEAR_SCALE.get(year)
        if scale is None:
            raise SystemExit(f"--year {year} not in {sorted(YEAR_SCALE)}")
        sites = sites.copy()
        sites["cap_mw"] = sites["cap_mw"] * scale
        print(f"   year-phased ceiling (§3a): {year} -> ×{scale} "
              f"-> total {sites['cap_mw'].sum():.0f} MWe")
    inject(n, sites, extendable=not frozen)

    n.export_to_netcdf(out_path)
    print(f"\nSaved -> {out_path}")
    print("Solve it:  python -c \"import pypsa; n=pypsa.Network('" + out_path
          + "'); n.optimize(solver_name='gurobi'); n.export_to_netcdf('solved.nc')\"")


if __name__ == "__main__":
    main()
