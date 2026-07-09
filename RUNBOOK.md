# PyPSA-Earth EARS Geothermal — How the model works (step by step)

This runbook explains, in order, **what happens to get from raw data to results**
— so you can follow and understand the process, not just run commands. It is the
practical companion to `MODELING_PLAN.md` (the research design) and
`inject_geothermal.py` (the geothermal step).

> **Where to run:** everything lives in `pypsa-earth/`. Run commands from there,
> inside the `pypsa-earth` conda environment (it provides PyPSA, atlite,
> snakemake, and the Gurobi solver). The CDS API key (`~/.cdsapirc`) is used to
> fetch weather data.

---

## The big picture

The model turns **geography + weather + demand + a power-plant fleet** into a
**network**, then finds the **least-cost way to run (and expand) that network**
to meet demand every hour. We then add geothermal and re-solve to measure its
value.

```
 OSM grid  ┐
 ERA5 weather ┤
 demand (GEGIS) ┼──► build a clustered power-system network ──► OPTIMISE ──► results
 costs        ┤        (buses, lines, generators, storage)     (least cost)    (dispatch,
 fleet (EEP)  ┘                                                                  capacity, cost)
                                            │
                                            └──► inject geothermal ──► re-optimise ──► geothermal's value
```

One command runs the whole build-and-solve chain:

```bash
conda run -n pypsa-earth --no-capture-output snakemake -j1 solve_all_networks
```

The sections below explain each stage that command performs.

---

## Step 1 — Configure the study (`config.yaml`)

This file defines *what* is modeled. The settings that matter:

| Setting | Meaning |
|---|---|
| `countries: ["ET"]` | which country (Ethiopia here) |
| `scenario.clusters: [6]` | how many nodes the grid is aggregated to (detail vs speed) |
| `scenario.opts: [Co2L-4H]` | a CO₂ limit (`Co2L`) and 4-hourly time resolution |
| `snapshots: {start, end}` | the time window simulated (a representative week, or a full year) |
| `electricity.custom_powerplants: replace` | use our curated real fleet instead of the auto database |
| `electricity.renewable_carriers / extendable_carriers` | which technologies exist and which the model may *build* |
| `solving.solver: gurobi` | the optimiser |

---

## Step 2 — Gather the input data

Snakemake first assembles every dataset the network needs:

- **Power grid (OpenStreetMap):** downloads and cleans the country's transmission
  lines and substations → the physical skeleton of the network.
- **Weather (ERA5 cutout):** builds a gridded weather dataset for the country and
  time window (via the CDS key) — wind speeds, solar irradiance, and **runoff**
  (which drives hydro inflow).
- **Demand (GEGIS):** hourly electricity demand for the country, for a chosen
  projection year, derived from population, GDP and temperature.
- **Costs (technology-data):** capital/operating costs and efficiencies for every
  technology (solar, wind, gas, storage, …).
- **Power-plant fleet:** the existing plants. We supply the real Ethiopian fleet
  in `data/custom_powerplants.csv` (GERD, the hydro cascade, diesel units, Aluto
  geothermal, wind, solar) so the baseline matches reality.
- **Land/resource layers:** land cover, protected areas, bathymetry, river basins
  — used to decide where renewables can physically go.

---

## Step 3 — Build the network

The grid is assembled from those inputs through a chain of steps. Conceptually:

1. **Shapes** — draw the country and sub-region boundaries.
2. **Base network** — turn the OSM substations into **buses** and the lines into
   **transmission links**, with their voltages and capacities.
3. **Bus regions** — divide the country into one catchment area per bus, so demand
   and renewable resource can be assigned to the nearest bus.
4. **Renewable profiles** — for each bus, compute the **hourly availability** of
   solar and wind (capacity factor 0–1) from the weather cutout and the land
   available, and the **hydro inflow** time series from runoff.
5. **Demand profiles** — distribute the national hourly demand onto the buses
   (by population/GDP).
6. **Add electricity** — assemble everything into one network: attach the fleet
   (each plant becomes a generator; reservoir hydro becomes a **storage unit**
   with an inflow series), the demand, the costs, and the technology carriers.
7. **Simplify & cluster** — merge the detailed grid down to the chosen number of
   nodes (e.g. 6) so the optimisation is tractable, preserving the main flows.
8. **Add storage options** — make battery / hydrogen storage available as build
   options.
9. **Prepare** — apply the CO₂ limit and line-expansion rules; the result is a
   **solve-ready network**.

The two networks worth knowing:
- `networks/elec_s_6_ec_lcopt_Co2L-4H.nc` — the **prepared (pre-solve)** network.
- `results/networks/elec_s_6_ec_lcopt_Co2L-4H.nc` — the **solved** network.

---

## Step 4 — Solve (the optimisation)

The solver (Gurobi) finds the **least-cost** way to meet demand. It decides:
- **how much new capacity to build** of each *extendable* technology, and
- **how every plant dispatches in each time step**,

minimising **total system cost** =
`annualised capital cost × capacity built` + `marginal (fuel/O&M) cost × energy dispatched`,

subject to physical constraints:
- demand is met at **every bus and every time step** (or paid for as unserved
  energy / load-shedding at a high penalty),
- each plant's output ≤ its availability (`capacity × hourly availability`),
- **hydro reservoirs** obey a storage balance — they can only release the water
  (inflow) they receive over the period,
- transmission line limits,
- the **CO₂ cap** (when active).

**Representative-period weighting.** A one-week window is solved at 4-hourly steps,
and each step carries a **weight** so the week represents a full year. Therefore
**energy = dispatch × snapshot weight** — always multiply time series by
`n.snapshot_weightings.objective` to get annual GWh.

The solved network stores the built capacity (`p_nom_opt`) and the hourly dispatch
of every generator, storage unit and line.

---

## Step 5 — Read & validate the baseline

```bash
python analyse_results.py results\networks\elec_s_6_ec_lcopt_Co2L-4H.nc
```

Check it reproduces reality: for Ethiopia, **hydro should dominate (~84–90%)**.
Hydro is a *storage unit*, so include `storage_units_t.p`, and weight energy by
the snapshot weights. This confirms the model is a faithful starting point before
we add geothermal.

**If a check fails:** fix the underlying input (fleet in `custom_powerplants.csv`,
hydro inflow normalization, or the GEGIS demand-year setting) — never tune a
scenario knob (VOLL, CO₂ handling, load-shedding cost) just to make the baseline
numbers pass. See `MODELING_PLAN.md` §5. Do not proceed to Step 6 or any scenario
run until every check below passes.

### Validation log (fill in once Tier-0 passes)

Record the **realized** baseline numbers next to the exact code/config version
that produced them (`git rev-parse --short HEAD` in `pypsa-earth/`, plus the
config file name/snapshot range) — this is the audit trail if a number is
questioned later, since the config has already changed several times (CO₂
mechanism, geothermal capacity basis, hydro normalization — see
`MODELING_PLAN.md` revision notes).

| Date | Run hash (git) | Config / snapshots | Demand (TWh/yr) | Hydro share (%) | Diesel share (%) | Unserved (%) | Pass? | Notes |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

Targets (§5): demand ~16.5 TWh ±5% · hydro ~84% ±5pp · diesel <1% · unserved <0.5%.

---

## Step 6 — Inject geothermal (the thesis contribution)

`inject_geothermal.py` adds geothermal to the prepared network as a set of
**named, capped, build-or-not generators**:

1. Read each **JICA Master Plan prospect** — site name, coordinates, **JICA
   installed capacity** (Table 5.3) and **Zuffi FLASH LCOE** — from
   `_thesis_inputs/JICA_Geothermal_Sites_Ethiopia.xlsx` (21 sites, ≈ 4.1 GWe
   total, year-phased ceiling per `MODELING_PLAN.md` §3a).
2. Attach each site to its **nearest electrical bus**, capped at the site's
   JICA capacity, available as baseload (capacity factor ~0.9).
3. Set its cost: the geothermal **LCOE** is carried as an annualised capacity cost
   (`capital_cost = LCOE × 8760 × CF`). A grid-connection cost adder exists but is
   off by default (`USE_CONNECTION_COST`; ~1–2% of capex).
4. `--frozen` builds the reference network instead: today's ~7 MW (Aluto) only,
   no expansion.

Then re-solve. Because geothermal is cheap, firm power, the optimiser builds it up
to whatever cap is allowed — so the **geothermal contribution is read directly
from how much it builds and what it displaces** (diesel, unserved energy, or other
new build).

```bash
python inject_geothermal.py networks\elec_s_6_ec_lcopt_Co2L-4H.nc scenarios\ET_geo_on_unsolved.nc
python -c "import pypsa; n=pypsa.Network('scenarios/ET_geo_on_unsolved.nc'); n.optimize(solver_name='gurobi'); n.export_to_netcdf('scenarios/ET_geo_on.nc')"
```

---

## Step 7 — Build the scenarios

Scenarios are constructed by modifying the prepared network in Python before
solving (see `MODELING_PLAN.md` for the full matrix). The levers:

- **Drought** — scale reservoir inflow (and run-of-river availability) down by a
  calibrated factor (e.g. ×0.55 for a −45% year). Hydro produces less → the system
  must cover the gap.
- **Demand** — set `load_options.prediction_year` (2030 / 2040 / 2050) or apply a
  `scale` factor for a high-industrialisation future.
- **Geothermal capacity** — the cap is a scenario in itself: conservative (named
  grid-feed-in sites) → project-pipeline → technical potential.
- **Build framing** — choose what the optimiser may build:
  - *today's-system stress test*: freeze the existing fleet, allow only geothermal;
  - *open competition*: also allow new solar, wind and storage, so geothermal must
    win on merit.
- **Emissions experiment** — allow fossil (diesel/gas) to expand and drop the CO₂
  cap, then compare geo-off vs geo-on: in a dry year fossil fills the hydro gap
  (emissions rise) unless geothermal covers it (emissions stay low).

Each scenario is solved the same way as the baseline, and the same metrics are read
out.

---

## Step 8 — Analyse & visualise the results

For every solved scenario, read the **outcome metrics** (weighting time series by
the snapshot weights):

- **Unserved energy** (load-shedding GWh) — reliability / the crisis,
- **Diesel/oil generation and cost** — the expensive-backup burden,
- **CO₂ emissions** (from fossil dispatch × emission factors) — the emissions story,
- **Total system cost** (drought vs normal) — the $ value of the hedge,
- **Geothermal built** (MW, generation, share).

Maps and charts:

```bash
python plot_country_map.py results\networks\elec_s_6_ec_lcopt_Co2L-4H.nc plots\ET_capacity_map.png "Ethiopia — power system"
```

This produces the country map with per-node capacity pies by technology and
transmission lines — the same style as the published PyPSA-Earth country atlas.

---

## Concepts to keep in mind when reading results

- **Snapshot weighting** — energy is `dispatch × snapshot weight`, not the raw sum.
- **Hydro is a *storage unit*** (reservoir + inflow), not an ordinary generator —
  look in `storage_units`, not just `generators`.
- **Existing vs extendable** — fleet plants have fixed capacity; *extendable*
  technologies are the ones the optimiser may build. What you allow to be
  extendable defines the scenario.
- **Geothermal cost as capacity cost** — geothermal is ~all capital, so its LCOE
  is modeled as an annualised capacity cost with ~zero fuel cost; it runs whenever
  available.
- **Capacity is a scenario, not a fact** — the geothermal resource estimate is a
  conservative floor, so results are reported across a capacity range.

---

## Quick reference — full run

```bash
cd C:\Users\user\PycharmProjects\earthkit\pypsa-earth
conda activate pypsa-earth

# 1–4: build inputs, assemble & cluster the network, and solve the baseline
snakemake -j1 solve_all_networks

# 5: validate
python analyse_results.py results\networks\elec_s_6_ec_lcopt_Co2L-4H.nc

# 6: add geothermal and re-solve
python inject_geothermal.py networks\elec_s_6_ec_lcopt_Co2L-4H.nc scenarios\ET_geo_on_unsolved.nc
python -c "import pypsa; n=pypsa.Network('scenarios/ET_geo_on_unsolved.nc'); n.optimize(solver_name='gurobi'); n.export_to_netcdf('scenarios/ET_geo_on.nc')"

# 7–8: scenarios (drought / demand / framings) + analysis & maps
```

For another country, set `countries`, give the run a `run: name:` so results don't
overwrite, keep offshore wind only if the country is coastal, then repeat from
Step 1.
```
