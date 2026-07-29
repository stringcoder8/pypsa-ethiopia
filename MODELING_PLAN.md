# Modeling Plan — Geothermal in the EARS power systems (PyPSA-Earth)

Reference document for the thesis modeling: the research question, the framing,
the methodological commitments, the validation protocol, and the (pruned)
scenario design. Companion to `RUNBOOK.md` (how to run) and
`inject_geothermal.py` (geothermal injection).

> **Revision note (2026-06-28).** Restructured for a runnable, defensible
> experimental design. Key changes: the 96-cell scenario grid is replaced by a
> prioritized factorial (§6); full-year simulation is promoted
> from a to-do to a **locked methodological commitment** (§3e); an explicit
> **validation protocol** (§5) and **sensitivity design** (§7) are added; and the
> headline "value of geothermal" is now a **precisely defined delta** (§8). The
> previous version is kept at `_backups/MODELING_PLAN_backup_20260628.md`.

> **Revision note (2026-07-01).** Geothermal site/capacity basis switched to the
> **JICA Master Plan** and the **capacity scenario axis dropped** to cut runs.
> (1) Sites and per-site capacities now come from the JICA (2015) Master Plan
> (`_thesis_inputs/JICA_Geothermal_Sites_Ethiopia.xlsx`), not the EARS grid-feed-in filter.
> (2) Each site has a **single `p_nom_max` = JICA capacity** — no more low/planned/
> high levels; the only geothermal axis is **on vs off** (§3a, §6).
> (3) **FLASH technology for all sites** for simplicity (§3f).
> (4) Cost = **Zuffi FLASH LCOE**; JICA LCOE kept as an optional sensitivity.
> The ArcGIS/EARS clustering list still underpins the separate wind/PV+storage +
> distance analysis; only the PyPSA geothermal injection moves to JICA.
> Previous version: `_backups/MODELING_PLAN_backup_20260628.md`; old injector:
> `_backups/inject_geothermal_backup_20260701.py`.

> **Revision note (2026-07-02).** Two dimension reductions.
> (1) Drought collapsed to a **single −50% inflow factor** (was −30/−45/−60),
> cited to Tegenu et al. 2022 (*Applied Sciences* 12:1954, "Drought Scenario" =
> 50% hydro cut) and the 2022–23 event; hydro axis is now **normal vs −50%** (§3c).
> (2) Demand = **two scenarios run**: **GEGIS** (low, PyPSA-native, empirically
> accurate) and **Gebremeskel HEG** (high, rigorous bottom-up ≈ govt master plan),
> at 2030/2040/2050; Exp 4 runs them at **2050**. An optional third scenario would
> be an *upper* case **above HEG** (e.g. Boke HERA ~769 TWh 2050), not a middle —
> TBD. (Corrects an earlier draft that mislabeled LEAP-BAU as ~66 TWh — the real
> LEAP electricity is ~585–835 TWh by 2060.) Scenario matrix now **~11 runs**.

> **Revision note (2026-07-02b).** Consolidated to a **single framing** and a clean
> factorial. The A/B/C build framings are dropped: framing B (frozen fleet) was
> unrealistic and its clean-attribution role is now served by the geothermal
> **available-vs-excluded** pair under one realistic **open-competition framing
> with a CO₂ cap declining to net-zero by 2050** (Ethiopia's CRGE pledge) and a
> **load-shedding backstop** (§3d). The diesel/emissions counterfactual becomes a
> **qualitative, cited** argument (2015 & 2022–23 events; Tegenu et al. 2022) — not
> modelled, since nothing emits under the cap. Scenario design is now a factorial
> over **year (2030/40/50) × hydro (normal/−50%) × demand (GEGIS/HEG) × geothermal
> (available/excluded)** (§6). **VOLL corrected** to an Ethiopia-sourced central
> **1.0 €/kWh** (~$1,000/MWh), replacing the European 100 €/kWh default; sensitivity
> conditional (§7). Diesel-cost sensitivity dropped (no fossil under the cap).

> **Revision note (2026-07-09).** Supervisor confirmed **the main factorial
> (§6, the 18 clean-by-construction runs) is sufficient scope** — the
> validation protocol (§5), the uncapped emissions experiment, the
> hydro-extendable sensitivity, and the conditional VOLL/geothermal-cost
> sensitivities are **demoted out of the active analysis plan** (not required
> deliverables for now; kept below, marked, in case they're reinstated later).
> `config.ET.yaml` updated to match: `Co2L` dropped from `scenario.opts`
> (kept `4H`), `OCGT` removed from `extendable_carriers` — the
> clean-by-construction framing is now actually implemented in the config,
> not just described in this plan. See revised §9 for the current sequencing.

> **Revision note (2026-07-08b).** Scope narrowed to **Ethiopia only, for now**.
> Tanzania and Kenya are paused (not dropped) — no further modeling work on
> either until Ethiopia's factorial is complete. This removes the
> "cross-country spine" framing (§1): the CO₂-cap discussion that motivated
> Tanzania's fossil-displacement framing is no longer a near-term concern.
> Tanzania's existing 1-week A/B result (§9) stands as a paused checkpoint, not
> a live deliverable. Revisit multi-country scope only after the Ethiopia
> validation + main factorial + mandatory add-ons (§6, §9) are done.

> **Revision note (2026-07-08).** Critical re-assessment against thesis goals;
> five changes. **(1) CO₂-cap mechanism replaced** (§3d): traced PyPSA-Earth's
> actual `add_co2limit` code — it is a single **static** global constraint per
> solve (no native multi-year trajectory), and with `automatic_emission: true`
> the cap defaults to Ethiopia's real ~1990 EDGAR baseline, which is already
> ~0.05–0.1 Mt for the power sector — so a "decline from today to net-zero" cap
> is vacuous at *every* horizon year, not just 2050, and cannot deliver the
> 2030/2040 emissions delta promised in the previous revision. Fixed by
> **dropping the CO₂-constraint mechanism entirely**: the main factorial goes
> clean **by construction** (OCGT excluded from `extendable_carriers`, existing
> ~99 MW diesel frozen), and the diesel/CO₂ story is answered by a **separate,
> mandatory, uncapped** counterfactual experiment (§3d, §6, §8). **(2) Geothermal
> capacity is now year-phased**, not a flat 4.1 GWe from 2030 (§3a): 2030 uses a
> realistic pipeline ceiling (~370 MW, EEP's own 2030 geothermal target), ramping
> to the full JICA resource by 2050. **(3) Hydro-extendable vs. geothermal is
> promoted from optional to a mandatory sensitivity** (§7): if geothermal is
> still built when hydro can also expand (under the same drought), that beats
> the incumbent on its own terms. **(4) LCOE sequencing clarified** (§7): Zuffi
> FLASH LCOE runs first (central case); the JICA LCOE re-run is triggered
> specifically if geothermal saturates its cap in (nearly) every cell, as a
> bias check, not run unconditionally. **(5) The GEGIS/HEG-corner interaction is
> now stated as an expected design feature, not left as a possible confound**
> (§6). Regional (KE/UG/DJ) modeling remains explicitly out of scope for now.

## 1. Research question & framing

**Central question (Ethiopia, the anchor country):**
> How much does geothermal improve the **security and industrial-readiness** of
> Ethiopia's hydro-dependent power system — under drought, seasonal hydro
> variability, and rising (industrial) demand — and what does it cost Ethiopia
> to lag behind its own geothermal ambition?

**Framing — security & diversification, NOT decarbonization.** Ethiopia's grid is
~90% hydro and already clean, so the argument is *not* CO₂ reduction. It is
**drought resilience + firm power for industrialization + reducing reliance on
rainfall**, motivated by the real 2018 and 2022–23 crises (load-shedding,
expensive diesel ~$0.25/kWh, suspended exports, curtailed industry). Geothermal
= weather-independent baseload hedge.

**Scope (as of 2026-07-08b).** **Ethiopia only, for now.** The original
five-country EARS scope (KE, ET, TZ, UG, DJ) with Tanzania as fossil-grid
counterpoint is **paused, not dropped** — all modeling effort goes to
Ethiopia's factorial (§6) until it's complete. **Individual per-country
models** (not a combined/interconnected grid) remains the method if/when
Tanzania resumes. The EEP 2030 generation plan is **discussion-layer only** —
not modeled.

**Ethiopia's role:** geothermal = drought-resilience / firm-capacity hedge
(hydro-clean system). The former "cross-country spine" (Tanzania as
gas-heavy/CO₂-cut counterpoint) is deferred along with Tanzania itself — see
revision note above.

---

## 2. The model

- **PyPSA-Earth**, per country, 6 clusters (development) → raise only if the
  geothermal *location*/transmission story proves material (§9).
- **Fleet:** curated real fleet in `data/custom_powerplants.csv` (from official
  EEP list): GERD 5,150 MW, the hydro cascade, ~99 MW diesel, Aluto-Langano
  7.3 MW geothermal, operational + under-construction, biomass excluded.
- **Geothermal is endogenous** — added by `inject_geothermal.py` from the **JICA
  site inventory** (`_thesis_inputs/JICA_Geothermal_Sites_Ethiopia.xlsx`, sheet "JICA Sites"):
  one extendable generator per JICA prospect, attached to the nearest AC bus,
  **FLASH** technology (§3f), `p_nom_max` = the site's **JICA installed capacity**
  (Table 5.3, mode fallback), cost = **Zuffi FLASH LCOE**→`capital_cost =
  LCOE×8760×CF`. Grid-connection cost is off by default (no distance column;
  ~1–2% of capex — toggle `USE_CONNECTION_COST`). Only Aluto (7.3 MW) sits in the
  fixed fleet; all new geothermal is a model build decision.

---

## 3. Key methodological decisions

### 3a. Geothermal capacity = year-phased JICA ceiling (no low/mid/high axis)

**How capacity is used in the model.** Each geothermal site is an *extendable*
generator with `p_nom_max` = its **JICA installed capacity** (Master Plan
Table 5.3, most-probable Monte-Carlo value; mode used where 5.3 is blank). The
optimiser **decides how much to actually build (0 → cap)** based on cost.
Geothermal is cheap, firm, zero-fuel power, so in a stressed system (drought /
high demand) it builds **toward the cap** — the cap therefore **bounds
geothermal's maximum contribution**. The result we read out is *how much it
builds* and *what it displaces* (unserved energy, diesel, CO₂, cost).

**The full JICA resource is not available from year one.** Summed across the
21 JICA sites with complete data, the modeled geothermal ceiling is
**≈ 4.1 GWe** — essentially the full national Monte-Carlo mode (~4.2 GW). Letting
the model build toward all of it as early as 2030 is not credible: Ethiopia took
25 years to commission 7 MW, and the country's own plan targets only
**~370 MW of geothermal by 2030** (EEP generation plan). So the ceiling is now
**year-phased**, scaled uniformly across all sites by year:

| Year | Aggregate ceiling | Scale of JICA cap | Basis |
|---|---|---|---|
| **2030** | ~370–410 MW | ×0.09 | EEP's own 2030 geothermal target (pipeline-realistic: Aluto-II, Tulu Moye, Corbetti, Tendaho phase 1) |
| **2040** | ~2.0 GWe | ×0.5 | interpolated mid-buildout |
| **2050** | ≈ 4.1 GWe (full) | ×1.0 | full JICA developable resource unlocked |

Mechanism: each site's `p_nom_max` is the JICA value × the year's scale factor
(implementation detail for `inject_geothermal.py`: a `--year` flag). A
named-subset alternative (pick specific pipeline sites for 2030 rather than a
uniform scale) is possible later if site-level realism is wanted for the write-up,
but the uniform scale is simpler and defensible as a first pass.

The **only geothermal axis is therefore on vs off, now per year**:

| State | `p_nom_max` | Meaning |
|---|---|---|
| **off** (`--frozen`) | Aluto only at ~**7 MW**, rest 0 | today's lagging system (reference) |
| **on** | each site at its **year-phased JICA capacity** | resource available to build, at that year's realistic ceiling |

This still powers the **"lagging 7 MW today vs the JICA resource"** narrative,
now without the "4.1 GW overnight" credibility problem.

> Provenance: capacities from JICA/GSE (2015) Master Plan, Table 5.3; the full
> per-site table (JICA mode/P80/P20, developer & planned figures, Zuffi FLASH/ORC
> LCOEs, coordinates) lives in `_thesis_inputs/JICA_Geothermal_Sites_Ethiopia.xlsx`. Three
> EARS-only sites (Aleta Wendo, Borawli, Tedecha) are not JICA prospects and are
> dropped from the PyPSA set.

### 3b. Demand = two scenarios (GEGIS low, Gebremeskel HEG high) at 2030/2040/2050

Ethiopian electricity-demand projections span ~8–20× by 2050, so demand is a
**scenario axis, not a point forecast**. For now **two scenarios are run**; a
third (middle) may be added depending on the outcome. Base year 2023 = **~12 TWh**
(EEP 2024, actual consumption).

| Scenario | 2030 | 2040 | 2050 | Basis |
|---|---|---|---|---|
| **Low = GEGIS** (SSP2-2.6, PyPSA-Earth native) | 16 | 23 | 34 | empirically grounded |
| **High = Gebremeskel HEG** (2021, LEAP) | 112 | 201 | 289 | rigorous bottom-up ≈ govt master plan |
| *(optional) Very-high = Boke HERA* (2022) | *128* | *~314* | *769* | *extreme-industrialisation upper bound* |

**Why these two.** GEGIS is the low case because it is **PyPSA-native and the only
forecast whose base year and ~4%/yr growth track the real grid** (actual demand
grew ~5%/yr over 2018–23). Gebremeskel's HEG is the high case because it has the
**most rigorous, Ethiopia-specific bottom-up end-use methodology** (LEAP:
households × appliances × electrification rate, 17 industrial parks, transport
EVs) and its trajectory **matches the government's own master-plan ambition**
(~147 TWh generation by 2037, 22 GW peak, ~12–13%/yr). So the bracket spans an
*empirically accurate floor* and a *methodologically rigorous, policy-ambition
ceiling*. The high case is explicitly flagged as ambition — Ethiopia has
historically under-delivered (5.2 GW actual in 2023 vs ~20 GW planned by 2025).

> Optional third scenario (TBD): if a third is added it would be an **upper** case
> *above* HEG — not a middle — e.g. **Boke-2022 HERA** (~769 TWh 2050) or LEAP-2025
> HUG (~836 TWh 2060), to stress-test extreme industrialisation where geothermal's
> firm-capacity value is largest. Decision deferred.

Implementation: PyPSA-Earth's load is GEGIS-based, so **Low** uses
`load_options.prediction_year` directly. **High = a uniform ×8.4 rescale** of the
GEGIS profile to the HEG annual total (`apply_heg_demand.py`), preserving both the
temporal shape and the spatial distribution across buses.

> **Revised 2026-07-29 — this replaces an earlier "flat industrial increment"
> design.** The previous version kept GEGIS as a residential/commercial base and
> added `(HEG − GEGIS)` as a constant round-the-clock block, on the reasoning that
> HEG growth is industrial and industry runs ~24/7. That was withdrawn for two
> reasons:
>
> 1. **It swamped the profile.** The increment is ~87% of the HEG total (2050:
>    34 TWh GEGIS + 255 TWh increment), so the flat block did not modify the shape —
>    it *became* the shape. Resulting national load factor 0.98, diurnal swing 1.03.
>    No real grid is that flat; even Iceland (~80% aluminium smelters) is ~0.94.
> 2. **It pre-loaded the conclusion.** Flat demand is precisely the shape firm
>    baseload serves best, and simultaneously the worst case for solar. The earlier
>    claim that a flat block was *conservative* (and that a peakier profile would
>    *understate* geothermal's value) was backwards: flat demand is the most
>    favourable possible demand shape for geothermal.
>
> A uniform rescale makes no claim about the composition of demand growth, which is
> the more neutral assumption to defend in an examination.

**Known limitations of the demand representation (state these in the write-up):**

1. The rescale inherits the GEGIS *shape*, which is materially flatter than
   Ethiopia's observed load curve. Measured against EEP's national hourly demand
   curve:

   | | GEGIS (raw hourly) | Observed (EEP) |
   |---|---|---|
   | Peak hour | 17:00 | **19:00** |
   | Trough hour | 00:00 | 03:00 |
   | Diurnal swing | 1.31 | **2.63** |
   | Night floor (% of peak) | 77% | **38%** |
   | Weekday/weekend ratio | 0.98 | should be >1 |
   | Annual load factor | 0.83 | **~0.67** |

   GEGIS is a GDP/population/temperature regression, not observed load. It carries
   roughly twice the overnight demand that actually exists and has no evening peak.
   These two errors bias in *opposite* directions (a high night floor favours firm
   baseload; a missing evening peak understates the value of firm/storage), so the
   net effect is not determinable by inspection and is **not** resolved here.
2. Rescaling assumes demand composition is invariant while the system grows ~8×.
   Real industrialisation would raise the load factor somewhat, so the true 2050
   shape likely lies between this profile and a flatter one.

> A potential upper third demand case would rescale further (Boke HERA ≈ **22×**
> GEGIS-equivalent at 2050).

### 3c. Drought = a single calibrated ×factor (−50%), not a real-year cutout

A real drought-year cutout fights the hydro normalization (`irena 2023` rescales
runoff and washes the drought back out) and breaks demand–weather-year
consistency. So perturb hydro on the prepared network: scale reservoir
`storage_units_t.inflow` (and run-of-river `p_max_pu`) by a **single factor
representing a severe, documented drought: −50% inflow.** This matches the one
published Ethiopia hydropower-drought model (Tegenu et al. 2022, *Applied
Sciences* 12(4):1954 — "Drought Scenario" = 50% hydro reduction) and the real
2022–23 event (~−45–50%). Using one severity instead of a −30/−45/−60 sweep cuts
the run count. Because the −50% magnitude is already well-established (Tegenu et
al. 2022; the 2022–23 event), it is taken as given — **no separate drought-year-
cutout validation run**.

> Note on magnitude: this −50% is a *drought-event deficit*, not the long-term
> climate-change mean (Blue Nile median ~−10% by 2070–99; Omo-Gibe −7 to −20%).
> Droughts are episodic deficits much larger than the mean shift, and reviews
> agree they are becoming more frequent/intense — so −50% is a defensible severe
> event, not an implausible extreme.

### 3d. Framing = clean-by-construction, with a separate uncapped emissions test

A **single, consistent framing** is used (replacing the earlier A/B/C structure),
now with the CO₂-cap mechanism fixed after tracing PyPSA-Earth's actual code:

> **Why the CO₂-cap mechanism was dropped.** PyPSA-Earth's `Co2L` wildcard adds
> **one static global constraint per solve** (`prepare_network.py::add_co2limit`) —
> there is no native multi-year declining trajectory; each horizon-year would need
> its own manually-set cap. Worse, with `automatic_emission: true` the cap defaults
> to Ethiopia's real historical (EDGAR, default year 1990) emissions — and
> Ethiopia's power-sector emissions are already tiny (~0.05–0.1 Mt/yr, ~99 MW
> diesel). A cap "declining from today to zero by 2050" is therefore **already
> ≈ 0 at every horizon year**, not just 2050 — it cannot produce the 2030/2040
> emissions delta the previous revision promised, and it makes "geothermal wins"
> partly a restatement of the constraint rather than an economic result. (Also
> note: the config's current `co2limit`/`co2base` = 1.487×10⁹ t are stale,
> non-Ethiopia values and are currently **inert** anyway, since
> `automatic_emission: true` overrides them.)

- **All technologies compete** — existing fleet retained, and solar, wind, storage
  **and** geothermal all extendable (least-cost capacity expansion).
- **Clean by construction, not by CO₂ constraint** — for the **main factorial**,
  **OCGT is removed from `extendable_carriers`**; only the existing ~99 MW diesel
  fleet exists, frozen, and no new fossil can be built. This gives the same
  "system must stay clean" framing as the old net-zero cap, without touching
  PyPSA's CO₂-constraint machinery at all — simpler and easier to defend.
- **Load-shedding backstop** at every bus (PyPSA-Earth's `load_shedding` generator,
  already in the model), priced at **VOLL** (§7), so the model may leave demand
  unserved rather than build clean firm capacity at unlimited cost — this makes
  **unserved energy** a real, reported metric.

**Value of geothermal = with vs without.** Each cell is run twice — **geothermal
available** (year-phased JICA caps, §3a) vs **geothermal excluded** (frozen at
today's ~7 MW). The available run shows *how much* geothermal the optimiser
picks; the excluded run shows *how much worse off* the clean system is without it
(more VRE+storage overbuild, or more shedding). The difference is geothermal's
value.

> **Why one clean-by-construction framing, not the old A/B/C.** Framing B (frozen
> fleet) was dropped — a frozen fleet is not a realistic future; its only merit was
> clean attribution, which the available/excluded pair now provides under a
> realistic open-competition setup. Old framing A survives only as the validation
> baseline (§5).

**The diesel / emissions counterfactual — a separate, mandatory, uncapped experiment.**
Because the main factorial excludes fossil by construction, it cannot produce an
emissions delta on its own. So the emissions story gets its **own small set of
runs**: OCGT restored to `extendable_carriers`, **no `Co2L` constraint at all**
(dropped from `opts` for these runs), at the **dry + geo-available/excluded**
cells. This directly quantifies **how much diesel/OCGT gets built and burned, and
the resulting CO₂**, when geothermal is and isn't there to cover the hydro gap —
a clean, mechanism-honest version of the "missed opportunity" from the previous
revision, not tied to an arbitrary yearly cap value. It is also literally what
happened in **2015** and **2022–23** (Tegenu et al. 2022 modelled the same
"drought → HFO backup → CO₂ rise" mechanism), so the modelled result and the
cited historical event reinforce each other. The model now answers two distinct
questions: *(1) can a clean system stay reliable under drought and rising demand,
and how much does geothermal help?* (main factorial) and *(2) if fossil is
allowed, how much less of it gets burned when geothermal is available?*
(emissions experiment).

### 3e. Simulation period = FULL YEAR (locked commitment)

The dry *season* is the mechanism, so a representative week cannot carry the
argument. **All reported results use a full-year (8760 h, 2013 ERA5 cutout) build**;
the 1-week representative period is retired to a development/debugging tool only.
This is a hard requirement, not a stretch goal — every number that enters the
thesis comes from a full-year run.

### 3f. Technology = FLASH for all sites (simplification)

Every geothermal generator is modeled as **single-flash** with a baseload
capacity factor (`p_max_pu = 0.90`) and the site's **Zuffi FLASH LCOE**. JICA's
200 °C rule would strictly put the two class-D sites (**Gedemsa, Kone**,
130–170 °C) on **binary/ORC**, but for simplicity we standardise on flash across
the board. This slightly over-credits those two small (37 + 14 MW), low-priority
sites; the injector can switch a site to the Zuffi `ORC_LCOE` if a binary variant
is wanted later. Cost source stays **Zuffi FLASH LCOE**, with **JICA LCOE** kept
as an optional cost sensitivity (the two differ ~2–4×; see §7).

---

## 4. Arguments for geothermal & how each is modeled

| Argument | Mechanism | Model lever | Metric |
|---|---|---|---|
| Drought resilience | hydro collapses → shedding | inflow ×factor (−50%) | unserved energy, system cost |
| Seasonal firmness | dry season (Oct–May) hydro dips | full-year run | dry-season shedding w/o geo |
| Demand growth / industrialization | demand outpaces slow new hydro | demand GEGIS vs HEG, 2030/40/50 | required firm capacity; gap geo fills |
| Emissions under stress | dry year → fossil backup | **modelled**: separate uncapped experiment, OCGT extendable, no `Co2L` (§3d, §6); cited corroboration (2015, 2022–23; Tegenu 2022) | ΔCO₂, Δdiesel (mandatory model output) |
| Hydro is not a free substitute | new dams are slow/contested (GERD ~13 yr; Koysha delayed since the 1990s) and share the same rainfall risk | hydro-extendable sensitivity, same −50% drought (§7) | geothermal still built? (robustness) |
| Diversification / risk | hydro spatially correlated (one rainfall regime) | −50% + full-year | variance of unserved ↓ (discussion) |
| (Export revenue, inertia, water use) | — | — | discussion-layer |

---

## 5. Validation protocol — **demoted 2026-07-09, not currently required**

> Kept for reference. Supervisor confirmed the main factorial alone is
> sufficient scope, so this protocol is not an active deliverable. If
> reinstated, the gate below still applies as written.

Validation protocol (must pass before any scenario run)

The baseline must reproduce the real Ethiopian system before its deltas are
trusted. **Baseline = full-year, today's fleet, normal hydro, expansion disabled
(or geothermal excluded at 7 MW).** Pass criteria:

| Check | Target | Tolerance | Source |
|---|---|---|---|
| Annual demand | ~16.5 TWh/yr | ±5% | EEP / IEA |
| Hydro generation share | ~84% | within **±5 pp** | EEP historical; cf. Boke et al. ~71% in 2030 (BAU) |
| Geothermal | ~7 MW (Aluto), generating | qualitative | EEP fleet |
| Diesel/oil generation | ≈ 0 in a normal year | < 1% of generation | EEP |
| Unserved energy | ≈ 0 in normal baseline | < 0.5% of demand | model sanity |

If hydro share or demand falls outside tolerance, fix inputs (fleet, inflow
normalization, demand profile) **before** running scenarios — do not interpret
deltas off an unvalidated base. Record the realized baseline numbers in
`RUNBOOK.md` next to the run hash.

---

## 6. Scenario design — clean-by-construction factorial

One framing (§3d): open competition, fossil frozen at ~99 MW (no CO₂ constraint
needed), load-shedding backstop. Inside it, a **factorial over four axes**:

- **Year:** 2030 · 2040 · 2050 (also sets the geothermal ceiling, §3a, and the
  technology-cost year)
- **Hydro:** normal · dry (−50%)
- **Demand:** GEGIS (low) · Gebremeskel HEG (high) — year-matched values (§3b)
- **Geothermal:** available (year-phased JICA caps) · excluded (frozen ~7 MW) —
  the with/without value pair

**Expected interaction between the drought and industrialization axes (state this
up front, not as a post-hoc surprise).** These two axes are expected to peak in
different corners, because they stress different things:
- **Drought resilience value peaks at GEGIS (low) demand** — today's hydro-heavy
  system, where a −50% cut removes a large *share* of a small supply, is the
  cleanest read of "geothermal as a rainfall hedge."
- **Geothermal build volume / industrialization value peaks at HEG (high) demand**
  — by 2050 at HEG (~289 TWh), existing hydro (~38 TWh once GERD+Koysha are
  counted, see the normalization fix) is only ~13% of supply, so the system is
  already a near-greenfield build-out and a further −50% hydro cut is a much
  smaller relative perturbation. Geothermal's role here is driven by the sheer
  size of the firm-capacity gap, not by drought.

So: **don't expect the biggest ΔUnserved-from-drought and the biggest
geothermal-GW-built to land in the same cell** — they answer two different halves
of the thesis question (resilience vs. industrial readiness) by design.

**Per horizon year — a 2×2×2 block:**

| hydro \ demand | GEGIS (low) | HEG (high) |
|---|---|---|
| **normal** | geo avail / excl | geo avail / excl |
| **dry −50%** | geo avail / excl | geo avail / excl |

= 8 runs/year × 3 years = **24 runs** (full factorial).

**Pruning option (recommended):** run all **12 geo-available** cells (the
progression + drought + demand stress, and *how much* geothermal builds), and add
the **geo-excluded twin only for the dry cells** — where geothermal's resilience
value peaks — → **18 runs**. Add the normal-year excluded twins only if the
calm-year value proves interesting.

**What each axis delivers:**
- **Year** → the *progression*: how much geothermal is realistically available
  (§3a phasing) and how demand rises, as the horizon extends.
- **Hydro (normal/−50%)** → *drought resilience*: the firm-capacity need under a
  severe dry year.
- **Demand (GEGIS/HEG)** → *industrialisation*: how far the firm-capacity gap
  widens as demand outpaces slow new hydro.
- **Geothermal available/excluded** → the *value* (Δcost / Δunserved / what's built
  instead), measured in each cell.

> **Demoted 2026-07-09 (supervisor: main factorial is sufficient scope).** The
> validation run, the emissions experiment, the hydro-extendable sensitivity,
> and the conditional sensitivities below are no longer part of the active
> plan. Kept as written in case they're reinstated later.

~~**Plus validation:** 1 baseline run (§5). (No drought-year-cutout run — the −50%
factor is taken as established from Tegenu et al. 2022 and the 2022–23 event, §3c.)~~

~~**Plus the mandatory emissions experiment (§3d, §4):** OCGT extendable, no `Co2L`
constraint, at the **dry** cells × geo-available/excluded, run at **GEGIS demand**
(the cleanest read on the resilience question — see the corner-interaction note
above) → **+2–4 runs**, giving the real Δdiesel/ΔCO₂ number.~~

~~**Plus the mandatory hydro-extendable sensitivity (§7):** the **2050 cells —
normal & dry hydro × GEGIS & HEG demand (4 runs)** — re-run with hydro also
extendable, subject to the same −50% drought in the dry cells → **+4 runs**.~~

~~Plus the **conditional** VOLL / geothermal-cost sensitivities (§7) — only run if
load-shedding actually appears, or if geothermal saturates its cap almost
everywhere (bias check, §7).~~

**Active scope (2026-07-09): the 18-run main factorial only** (12 geo-available
cells + 6 geo-excluded dry-cell twins, §6 above). Every run maps to a specific
claim; an optional even-higher demand scenario (above HEG, §3b) can be added later.

---

## 7. Sensitivity analysis — **demoted 2026-07-09, not currently required**

> Kept for reference. Supervisor confirmed the main factorial (§6) alone is
> sufficient scope; this section (hydro-extendable, VOLL, geothermal-cost
> sensitivities) is not an active deliverable. Note the **VOLL central value
> (1.0 €/kWh) still applies to all main runs** (§3d) — only the low/high
> sensitivity sweep here is demoted, not the central assumption itself.

Two conditional parameters, plus one now-**mandatory** structural sensitivity.
The conditional ones are **one-at-a-time on a single anchor cell** — **2050 ·
dry · HEG demand · geo-excluded**, where load-shedding is most likely — **not**
crossed with the whole factorial.

**Hydro-extendable (mandatory, not conditional).** The main factorial keeps hydro
non-extendable — realistic, since new dams in Ethiopia are slow and politically
constrained (GERD ~13 years; Koysha delayed since the 1990s), not a pure
cost-optimisation decision an LP would make on its own. But a reviewer will ask
"why not let the model just build more hydro instead of geothermal?" So re-run
**the 2050 cells — normal & dry hydro × GEGIS & HEG demand (4 runs)** — with hydro
also extendable (`StorageUnit: [hydro]` added to `extendable_carriers`), subject
to the **same −50% drought factor** in the dry cells (new dams sit in the same
rainfall regime, so they don't get a free pass from the stress test). Running both
hydro states × both demands isolates *when* hydro can substitute (normal / low
demand) from *when it can't* (dry / high demand).

> Note (hydro mechanics): PyPSA `p_nom`-extendable hydro only adds **turbines** to
> reservoirs with **fixed inflow** — it creates no new drought-season water. So in
> the **dry** cells the expected result is that extra hydro barely helps and
> geothermal is still chosen; the substitution, if any, shows up in the **normal**
> cells. That expected null in the dry cells is itself the rebuttal to "you just
> disallowed the cheaper option."

If geothermal is still built even when hydro can compete, that is a *stronger*
result than excluding hydro by assumption — it shows geothermal wins because it is
rainfall-independent, not because the alternative was disallowed. **+4 runs.**

**VOLL (value of lost load)** sets the load-shedding price (§3d). A central value
of **1.0 €/kWh (~$1,000/MWh)** — a blended Ethiopia national value — is used in
**all** main runs (config `load_shedding: 1.0`). The PyPSA-Earth default of
**100 €/kWh** (European, Schröder & Kuckshinrichs 2015) is ~200–600× above every
Ethiopia estimate and is deliberately replaced. The sensitivity is run **only if
meaningful shedding appears** in the main runs:

| VOLL | €/kWh | $/MWh | Basis |
|---|---|---|---|
| Low | 0.25 | ~250 | Ethiopia firm WTP / diesel-backup floor (revealed) |
| **Central** | **1.0** | **~1,000** | blended national economic VOLL |
| High | 5.0 | ~5,000 | industrial/manufacturing outage cost (SSA firm range) |

Sources: Ethiopia household/firm WTP ~$0.17–0.25/kWh; African backup ~$0.47/kWh;
SSA firm outage $2–32/kWh (Energy for Growth Hub; Ethiopian stated-preference
studies). **The strong result to look for:** geothermal is valuable *even at the
low VOLL* → conclusion robust. → **+2 runs (conditional).**

**Geothermal cost — sequenced, not run unconditionally.** Zuffi FLASH LCOE
(~$22–29/MWh) is the central case and runs first across the whole factorial.
**Trigger for the JICA-LCOE re-run (~$60/MWh, primary national source):** if
geothermal saturates its cap in (nearly) every cell at the Zuffi price, that is a
sign the result may just be "cheapest resource always wins" rather than a
genuine resilience finding — in that case, re-run the anchor cell(s) at the
JICA LCOE to check geothermal is still chosen at the higher, more conservative
national cost estimate. If Zuffi-based results already show geothermal losing
out in some cells (i.e. the model is discriminating, not just maxing out the
cheapest option), the JICA re-run is optional evidence, not a required fix.
→ **+1–2 runs, conditional on the bias check.**

> Diesel-cost sensitivity **dropped** — no fossil is built under the net-zero cap,
> so it no longer affects any result.

---

## 8. Outcome metrics — the "value of geothermal" is a defined delta

For any cell *S*, geothermal's value is the **difference between geothermal
excluded and available**, everything else fixed:

```
Value(geo | S) = X(S, geo = excluded, 7 MW)  −  X(S, geo = available, JICA)
```

reported for each X:

- **ΔTotal system cost** (€/yr) — the net economic value of geothermal
- **ΔUnserved energy** (GWh) — blackouts avoided, via the load-shedding backstop (§3d)
- ~~**ΔCO₂ and Δdiesel** (t, GWh) — from the separate uncapped emissions
  experiment~~ — **not currently produced**: the emissions experiment that would
  generate this metric is demoted (§6, 2026-07-09). The main (clean-by-construction)
  factorial excludes fossil build entirely by design, so this row is out of scope
  for now; the diesel/CO₂ argument stays a **cited, qualitative** point (2015,
  2022–23 events; Tegenu et al. 2022) rather than a modelled delta.
- **What's built instead** (solar / wind / storage MW) — the honest counterfactual
- **Geothermal built** (MW, generation share, full-load hours) + reliability
  (% demand served)

Every cell reports the absolute metrics *and* the paired delta, plus what the
optimiser built instead of geothermal when it didn't pick it.

---

## 9. Status & sequencing

> **Scope confirmed 2026-07-09 (supervisor meeting): main factorial is
> sufficient.** Sequencing below reflects the active plan only; validation,
> emissions experiment, hydro-extendable sensitivity, and conditional
> sensitivities are demoted (see §5, §6, §7) and moved to "Deferred" below.

- ✅ ET baseline on real fleet (hydro ~84%); first drought matrix (**1-week,
  now superseded**): −50% hydro → 6.2 TWh unserved; geothermal (214 MWe) cuts it
  ~27% and eliminates diesel. ✅ Tanzania A/B (fossil-displacement, paused).
- **Next (in order) — active scope:**
  1. **Full-year network build** (8760 h, 2013 cutout). `config.ET.yaml` already
     set: `load_shedding: 1.0`, `OCGT` removed from `extendable_carriers`,
     `Co2L` dropped from `opts` (clean-by-construction, §3d). Wire in the
     year-phased geothermal caps (§3a). A quick sanity check against §5's
     targets before trusting results is still worth doing informally, even
     though the formal validation protocol is demoted.
  2. **Main factorial** (§6): the 12 geo-available cells (year × hydro × demand)
     for the progression + how much geothermal builds.
  3. **Geo-excluded twins** for the dry cells → the geothermal-value deltas (§8),
     completing the 18-run main factorial.
  4. Raise clusters (10–20) **only if** the geothermal *location*/transmission
     story proves material.

**Deferred (not in current scope, kept for reference):**
- Formal validation protocol as a separate deliverable (§5).
- Uncapped emissions experiment → Δdiesel/ΔCO₂ delta (§3d, §6, §8).
- Hydro-extendable sensitivity (§7).
- Conditional VOLL / geothermal-cost sensitivities (§7).

---

## 10. Caveats to state in the write-up

- Geothermal capacity is a **year-phased single JICA value per site** (Master Plan
  Table 5.3): ~370–410 MW at 2030 (EEP pipeline realism) ramping to the full
  ≈ 4.1 GWe developable resource by 2050 (national mode ~4.2 GW; P20 ~11 GW) —
  not a scenario range; the geothermal axis is available vs excluded at each
  year. Resource uncertainty is acknowledged via JICA's own P80/P20 band (in
  `_thesis_inputs/JICA_Geothermal_Sites_Ethiopia.xlsx`).
- **FLASH assumed for all sites** — slightly over-credits the two class-D binary
  sites (Gedemsa, Kone); noted in §3f.
- **Clean-by-construction framing, not a CO₂ constraint** — the main factorial
  excludes new fossil build entirely (§3d) rather than relying on PyPSA-Earth's
  static, EDGAR-baseline CO₂ cap, which is vacuous for Ethiopia's near-zero
  power-sector baseline at every horizon year. The diesel/emissions
  counterfactual is a **separate, mandatory, uncapped experiment** (§3d, §6, §8),
  corroborated by cited historical events (2015, 2022–23; Tegenu et al. 2022).
- **Zuffi FLASH LCOE is the central, optimistic cost case (~$22–29/MWh)** —
  Ethiopia's own PPAs and JICA's cost estimate run higher (~$60/MWh). Results are
  checked against this: if geothermal saturates its cap almost everywhere at the
  Zuffi price, a JICA-LCOE re-run is triggered as a bias check (§7).
- **Hydro is not LP-extendable in the main factorial** (new dams are slow/contested,
  not a pure cost decision — GERD ~13 yr, Koysha delayed since the 1990s; and PyPSA
  `p_nom` expansion only adds turbines to fixed inflow, no new drought energy). A
  **mandatory sensitivity** re-runs the 2050 cells (normal/dry × both demands) with
  hydro extendable, to test whether geothermal still wins when hydro can compete
  on its own terms (§7).
- GEGIS (low) is the empirically accurate demand path; HEG (high) is the
  methodologically rigorous government-ambition ceiling. The high case is modeled as
  a **uniform rescale of the GEGIS profile** to the HEG annual total, preserving
  shape — this makes no claim about the composition of demand growth (§3b). The
  GEGIS shape itself is flatter than Ethiopia's observed load curve; that is a
  documented limitation, not a modelling choice (§3b).
- **Drought resilience value and geothermal build volume are expected to peak in
  different corners** (GEGIS/low-demand vs HEG/high-demand respectively) — stated
  as a design expectation, not an anomaly, in §6.
- **VOLL** drives the unserved-energy results → central 1.0 €/kWh (Ethiopia-sourced),
  with a conditional low/high sensitivity (§7); conclusions stated as robust only
  where they survive the range — ideally down to the low VOLL.
- The −50% drought ×factor is calibrated from the literature (Tegenu et al. 2022;
  the 2022–23 event) and taken as established — no separate drought-year-cutout run.
- Per-country, non-interconnected models → regional trade and KE/UG/DJ are
  discussion-layer only; not modeled quantitatively in this thesis.
- **Tanzania is paused (2026-07-08b), not dropped** — current focus is
  Ethiopia only. Tanzania's existing 1-week A/B result is a checkpoint, not a
  thesis-reportable number (superseded by the full-year commitment, §3e, like
  the Ethiopia 1-week runs).
