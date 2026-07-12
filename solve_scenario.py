#!/usr/bin/env python
"""
Solve a (transformed) prepared network with the load-shedding backstop.

PyPSA-Earth adds load-shedding generators only inside its own solve_network
rule — a prepared network solved manually has NO backstop and goes infeasible
the moment demand cannot be met. Since factorial cells are produced by
transforming prepared networks (apply_heg_demand / apply_drought /
inject_geothermal) and solved outside snakemake, this helper replicates the
backstop, then optimises.

VOLL = 1.0 EUR/kWh (=1,000 EUR/MWh) — the Ethiopia-sourced central value
(MODELING_PLAN.md §7); same as config.yaml solving.options.load_shedding.

USAGE
    python solve_scenario.py cell_unsolved.nc cell_solved.nc [--voll 1.0]
"""
import argparse
import pypsa


def add_load_shedding(n, voll_eur_per_kwh=1.0):
    if "load" in n.carriers.index:
        print("   load-shedding carrier already present; skipping add")
        return n
    n.add("Carrier", "load")
    buses = n.buses.index[n.buses.carrier == "AC"]
    for bus in buses:
        n.add("Generator", f"{bus} load shedding",
              bus=bus, carrier="load",
              p_nom=1e6,                                # effectively unbounded backstop
              marginal_cost=voll_eur_per_kwh * 1e3)     # EUR/kWh -> EUR/MWh
    print(f"   load shedding added at {len(buses)} AC buses "
          f"(VOLL {voll_eur_per_kwh} EUR/kWh)")
    return n


def main():
    p = argparse.ArgumentParser()
    p.add_argument("in_path")
    p.add_argument("out_path")
    p.add_argument("--voll", type=float, default=1.0, help="EUR/kWh (default 1.0)")
    args = p.parse_args()

    print(f"Loading {args.in_path} ...")
    n = pypsa.Network(args.in_path)
    add_load_shedding(n, args.voll)
    status, cond = n.optimize(solver_name="gurobi")
    print(f"solve: {status} / {cond}")
    if status != "ok":
        raise SystemExit(f"solve failed: {status} / {cond}")
    n.export_to_netcdf(args.out_path)
    print(f"Saved -> {args.out_path}")


if __name__ == "__main__":
    main()
