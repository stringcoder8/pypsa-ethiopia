"""
Plot a PyPSA-Earth-style country power-system map (like the Zenodo 193-country
image repo): clustered buses as pie charts of installed capacity by technology,
transmission lines sized by capacity, on a country basemap.

Works with the installed PyPSA (0.30.x) API. Usage:
    python plot_country_map.py <solved_network.nc> <out.png> ["Title"]
"""
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import cartopy.crs as ccrs
import pypsa

# fallback colours for carriers that have no colour set in the network
FALLBACK = {
    "hydro": "#298c81", "ror": "#3dbfb0", "PHS": "#51dbcc",
    "onwind": "#235ebc", "offwind-ac": "#6895dd", "offwind-dc": "#74c6f2",
    "solar": "#f9d002", "geothermal": "#ba91b1", "OCGT": "#d35050",
    "CCGT": "#b20101", "coal": "#545454", "lignite": "#826837",
    "oil": "#262626", "nuclear": "#ff8c00", "biomass": "#0c6013",
    "battery": "#ace37f", "H2": "#ea048a", "load shedding": "#dd2e23",
}


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    netfile, out = sys.argv[1], sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else ""

    n = pypsa.Network(netfile)

    # installed capacity per (bus, carrier): generators + storage units
    parts = [n.generators.groupby(["bus", "carrier"]).p_nom_opt.sum()]
    if len(n.storage_units):
        parts.append(n.storage_units.groupby(["bus", "carrier"]).p_nom_opt.sum())
    cap = pd.concat(parts)
    cap = cap[cap > 1.0]                                   # drop sub-MW
    carr = cap.index.get_level_values("carrier")
    cap = cap[~carr.str.contains("load shedding", case=False)]   # not a real plant

    carriers = list(cap.index.get_level_values("carrier").unique())
    cmap = {}
    for c in carriers:
        col = n.carriers.color.get(c, "") if c in n.carriers.index else ""
        cmap[c] = col if isinstance(col, str) and col.startswith("#") else FALLBACK.get(c, "#999999")

    # scale pies so the biggest bus is ~1 unit (PlateCarree degrees); lines ~max 3
    bus_scale = 0.6 / cap.groupby(level=0).sum().max()
    lw = (n.lines.s_nom_opt.where(n.lines.s_nom_opt > 0, n.lines.s_nom)
          if len(n.lines) else pd.Series(dtype=float))
    line_w = (lw / lw.max() * 3.0) if (len(lw) and lw.max() > 0) else 0.6

    import cartopy.feature as cfeature
    acb = n.buses[n.buses.carrier == "AC"]
    fig, ax = plt.subplots(figsize=(7.5, 8.5), subplot_kw={"projection": ccrs.PlateCarree()})
    ax.add_feature(cfeature.LAND, facecolor="#f4f1ea", zorder=0)
    ax.add_feature(cfeature.OCEAN, facecolor="#dbeaf2", zorder=0)
    ax.add_feature(cfeature.BORDERS, linewidth=0.4, edgecolor="#888", zorder=1)
    ax.coastlines(linewidth=0.4)
    ax.set_extent([acb.x.min() - 1.5, acb.x.max() + 1.5,
                   acb.y.min() - 1.5, acb.y.max() + 1.5], crs=ccrs.PlateCarree())
    n.plot(
        ax=ax, geomap=True, color_geomap=False,
        bus_sizes=cap * bus_scale, bus_colors=cmap,
        line_widths=line_w, line_colors="#555", link_widths=0.0,
    )
    handles = [mpatches.Patch(color=cmap[c], label=c)
               for c in sorted(carriers, key=lambda c: -cap.xs(c, level=1).sum())]
    ax.legend(handles=handles, loc="upper left", fontsize=8, frameon=True,
              title="Installed capacity (MW)")
    ax.set_title(title or netfile, fontsize=13)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    print(f"saved {out}  ({len(carriers)} carriers, {len(n.buses[n.buses.carrier=='AC'])} AC buses, "
          f"total {cap.sum():.0f} MW)")


if __name__ == "__main__":
    main()
