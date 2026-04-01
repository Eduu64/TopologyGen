import sys, os, math, argparse, yaml, textwrap, re
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import FancyBboxPatch, Wedge, FancyArrowPatch
from matplotlib.lines import Line2D
import numpy as np
import networkx as nx

# ══════════════════════════════════════════════
#  THEMES
# ══════════════════════════════════════════════
THEMES = {
    "dark": {
        "bg":          "#0A0E1A",
        "grid":        "#1C2333",
        "node_fill":   "#1A2744",
        "node_stroke": "#3B82F6",
        "node_text":   "#F1F5F9",
        "node_ip":     "#38BDF8",
        "edge_single": "#3B82F6",
        "edge_multi":  "#F59E0B",
        "edge_label":  "#94A3B8",
        "title":       "#F8FAFC",
        "subtitle":    "#64748B",
        "legend_bg":   "#111827",
        "legend_edge": "#1E293B",
        "badge_text":  "#38BDF8",
        # per-type accent strokes
        "stroke_switch":   "#3B82F6",
        "stroke_router":   "#10B981",
        "stroke_firewall": "#EF4444",
        "stroke_server":   "#A78BFA",
        "stroke_ap":       "#F59E0B",
    },
    "light": {
        "bg":          "#F8FAFC",
        "grid":        "#E2E8F0",
        "node_fill":   "#EFF6FF",
        "node_stroke": "#2563EB",
        "node_text":   "#0F172A",
        "node_ip":     "#0369A1",
        "edge_single": "#3B82F6",
        "edge_multi":  "#D97706",
        "edge_label":  "#475569",
        "title":       "#0F172A",
        "subtitle":    "#64748B",
        "legend_bg":   "#FFFFFF",
        "legend_edge": "#CBD5E1",
        "badge_text":  "#1D4ED8",
        "stroke_switch":   "#2563EB",
        "stroke_router":   "#059669",
        "stroke_firewall": "#DC2626",
        "stroke_server":   "#7C3AED",
        "stroke_ap":       "#D97706",
    },
}

# ══════════════════════════════════════════════
#  DEVICE TYPE DETECTION  (by name keywords)
# ══════════════════════════════════════════════
# Order matters: first match wins
TYPE_RULES = [
    ("firewall", re.compile(r"(?i)(fw|firewall|asa|ftd|palo|fortigate|checkpoint|ngfw)")),
    ("router",   re.compile(r"(?i)(rtr|router|gw|gateway|pe|ce|asbr|abr|edge)")),
    ("ap",       re.compile(r"(?i)(ap|wap|wifi|wireless|capwap|lwap)")),
    ("server",   re.compile(r"(?i)(srv|server|host|pc|vm|linux|win|esxi|hyper)")),
    ("switch",   re.compile(r"(?i)(sw|switch|swi|bridge|l2|l3|core|access|dist|agg)")),
]

def detect_type(name: str) -> str:
    for dtype, pattern in TYPE_RULES:
        if pattern.search(name):
            return dtype
    return "switch"   # safe default

# ══════════════════════════════════════════════
#  INTERFACE ABBREVIATION
# ══════════════════════════════════════════════
def abbrev_iface(name: str) -> str:
    abbrevs = [
        (r"(?i)^HundredGig(?:abit)?(?:Ethernet)?", "H"),
        (r"(?i)^TwentyFiveGig(?:abit)?(?:E)?",     "TF"),
        (r"(?i)^TenGig(?:abit)?(?:Ethernet)?",     "Te"),
        (r"(?i)^GigabitEthernet",                  "G"),
        (r"(?i)^FastEthernet",                     "F"),
        (r"(?i)^Ethernet",                         "E"),
        (r"(?i)^Serial",                           "S"),
        (r"(?i)^Loopback",                         "Lo"),
        (r"(?i)^Management",                       "Mg"),
        (r"(?i)^Port-channel",                     "Po"),
        (r"(?i)^Vlan",                             "Vl"),
        (r"(?i)^Tunnel",                           "Tu"),
    ]
    for pattern, short in abbrevs:
        result = re.sub(pattern, short, name)
        if result != name:
            return result
    return name

# ══════════════════════════════════════════════
#  YAML PARSER
# ══════════════════════════════════════════════
def parse_testbed(path: str):
    with open(path) as f:
        data = yaml.safe_load(f)

    tb = data.get("testbed", data)
    devices_raw = data.get("devices", {})
    topology_raw = data.get("topology", {})

    devices = {}
    for name, info in devices_raw.items():
        ip = None
        for c in info.get("connections", {}).values():
            if isinstance(c, dict) and "ip" in c:
                ip = c["ip"]
                break
        devices[name] = {
            "alias": info.get("alias", name),
            "ip":    ip,
            "type":  detect_type(name),
        }

    link_map = {}
    for dev_name, dev_topo in topology_raw.items():
        for iface_name, iface_info in dev_topo.get("interfaces", {}).items():
            link = iface_info.get("link", "")
            if not link:
                continue
            if link not in link_map:
                link_map[link] = {"endpoints": [], "ifaces": []}
            link_map[link]["endpoints"].append(dev_name)
            link_map[link]["ifaces"].append(iface_name)

    edges = []
    for link_name, info in link_map.items():
        eps, ifs = info["endpoints"], info["ifaces"]
        if len(eps) >= 2:
            edges.append((eps[0], eps[1], ifs[0], ifs[1], link_name))

    return devices, edges, tb.get("name", "Network Topology")

# ══════════════════════════════════════════════
#  BEZIER CURVE
# ══════════════════════════════════════════════
def bezier_curve(x1, y1, x2, y2, bend: float, n=120):
    mx, my = (x1+x2)/2, (y1+y2)/2
    dx, dy = x2-x1, y2-y1
    length = math.sqrt(dx*dx + dy*dy) or 1.0
    cx = mx - bend * dy / length
    cy = my + bend * dx / length
    t = np.linspace(0, 1, n)
    bx = (1-t)**2 * x1 + 2*(1-t)*t * cx + t**2 * x2
    by = (1-t)**2 * y1 + 2*(1-t)*t * cy + t**2 * y2
    return bx, by

# ══════════════════════════════════════════════
#  ICONS  
# ══════════════════════════════════════════════

def _icon_switch(ax, x, y, r, stroke, zorder=7):
    """Rack bar with port dots."""
    iw, ih = r*0.78, r*0.32
    ix, iy = x - iw/2, y - ih/2 + r*0.08
    ax.add_patch(FancyBboxPatch(
        (ix, iy), iw, ih, boxstyle="round,pad=0.012",
        linewidth=1.4, edgecolor=stroke,
        facecolor=stroke + "28", zorder=zorder))
    for i in range(6):
        px = ix + iw * (i + 0.8) / 6.5
        ax.add_patch(plt.Circle(
            (px, iy + ih*0.5), ih*0.13,
            color=stroke, alpha=0.9, zorder=zorder+1))


def _icon_router(ax, x, y, r, stroke, zorder=7):
    # Inner ring
    ax.add_patch(plt.Circle((x, y), r*0.42, fill=False,
                             edgecolor=stroke, linewidth=1.4, zorder=zorder))
    # Four arrows N S E W
    arr_len = r * 0.30
    arr_kw = dict(color=stroke, linewidth=1.3, zorder=zorder+1)
    for angle in [90, 270, 0, 180]:
        rad = math.radians(angle)
        x0 = x + math.cos(rad) * r * 0.44
        y0 = y + math.sin(rad) * r * 0.44
        x1 = x + math.cos(rad) * (r * 0.44 + arr_len)
        y1 = y + math.sin(rad) * (r * 0.44 + arr_len)
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=stroke,
                                   lw=1.2, mutation_scale=6),
                    zorder=zorder+1)


def _icon_firewall(ax, x, y, r, stroke, zorder=7):
    # Shield: pentagon-ish with a pointed bottom
    pts = np.array([
        [-0.38,  0.42],
        [ 0.38,  0.42],
        [ 0.38, -0.05],
        [ 0.00, -0.46],
        [-0.38, -0.05],
    ]) * r
    xs = pts[:,0] + x
    ys = pts[:,1] + y
    ax.fill(xs, ys, color=stroke+"22", zorder=zorder)
    ax.plot(np.append(xs, xs[0]), np.append(ys, ys[0]),
            color=stroke, linewidth=1.5, zorder=zorder+1)
    # Horizontal lines inside shield (grille)
    for dy_off in [0.12, -0.05, -0.22]:
        ly = y + dy_off * r
        lx0 = x - r * 0.22
        lx1 = x + r * 0.22
        ax.plot([lx0, lx1], [ly, ly],
                color=stroke, linewidth=0.9, alpha=0.7, zorder=zorder+1)


def _icon_server(ax, x, y, r, stroke, zorder=7):
    """Stack of 3 rack units."""
    sw, sh = r * 0.70, r * 0.20
    gaps = [-0.24, 0.0, 0.24]
    for dy_off in gaps:
        sx = x - sw/2
        sy = y + dy_off * r - sh/2
        ax.add_patch(FancyBboxPatch(
            (sx, sy), sw, sh, boxstyle="round,pad=0.008",
            linewidth=1.1, edgecolor=stroke,
            facecolor=stroke+"22", zorder=zorder))
        # LED dot on right side
        ax.add_patch(plt.Circle(
            (sx + sw - sh*0.35, sy + sh*0.5), sh*0.18,
            color=stroke, alpha=0.85, zorder=zorder+1))


def _icon_ap(ax, x, y, r, stroke, zorder=7):
    # Base
    bw, bh = r*0.44, r*0.18
    ax.add_patch(FancyBboxPatch(
        (x - bw/2, y - r*0.30), bw, bh,
        boxstyle="round,pad=0.008",
        linewidth=1.2, edgecolor=stroke,
        facecolor=stroke+"28", zorder=zorder))
    # Antenna stub
    ax.plot([x, x], [y - r*0.12, y + r*0.02],
            color=stroke, linewidth=1.2, zorder=zorder)
    # 3 concentric arcs radiating upward
    for i, arc_r in enumerate([0.18, 0.30, 0.42]):
        theta1, theta2 = 30, 150
        arc = matplotlib.patches.Arc(
            (x, y + r*0.02), arc_r*r*2, arc_r*r*2,
            angle=0, theta1=theta1, theta2=theta2,
            color=stroke, linewidth=1.1 - i*0.15,
            alpha=0.9 - i*0.15, zorder=zorder+1)
        ax.add_patch(arc)

import matplotlib.patches as mpatches

ICON_DRAW = {
    "switch":   _icon_switch,
    "router":   _icon_router,
    "firewall": _icon_firewall,
    "server":   _icon_server,
    "ap":       _icon_ap,
}

TYPE_LABEL = {
    "switch":   "Switch",
    "router":   "Router",
    "firewall": "Firewall",
    "server":   "Server / Host",
    "ap":       "Access Point",
}

# ══════════════════════════════════════════════
#  DRAW NODE
# ══════════════════════════════════════════════
def draw_node(ax, x, y, name, dev_type, T, r=0.30):
    stroke = T[f"stroke_{dev_type}"]
    fill   = T["node_fill"]

    # Body circle
    ax.add_patch(plt.Circle((x, y), r, color=fill, zorder=5))
    ax.add_patch(plt.Circle((x, y), r, fill=False,
                             edgecolor=stroke, linewidth=2.0, zorder=6))

    # Type-specific icon
    ICON_DRAW[dev_type](ax, x, y, r, stroke, zorder=7)

    # Name label below icon
    ax.text(x, y - r*0.58, name,
            ha="center", va="top", fontsize=7.0, fontweight="bold",
            color=T["node_text"], fontfamily="monospace", zorder=9,
            path_effects=[pe.withStroke(linewidth=2.5, foreground=fill)])


# ══════════════════════════════════════════════
#  IP LABELS — radially outward
# ══════════════════════════════════════════════
def draw_ip_labels(ax, pos, devices, T, r=0.30, center=(0.0, 0.0)):
    cx, cy = center
    ip_offset = r * 1.75

    for name, (nx_, ny_) in pos.items():
        ip = devices.get(name, {}).get("ip")
        if not ip:
            continue
        dx, dy = nx_ - cx, ny_ - cy
        dist = math.sqrt(dx*dx + dy*dy) or 1.0
        ux, uy = dx/dist, dy/dist
        lx = nx_ + ux * ip_offset
        ly = ny_ + uy * ip_offset
        ax.text(lx, ly, ip,
                ha="center", va="center", fontsize=6.0,
                color=T["node_ip"], fontfamily="monospace", zorder=10,
                path_effects=[pe.withStroke(linewidth=2.2, foreground=T["bg"])])

# ══════════════════════════════════════════════
#  MAIN DRAW
# ══════════════════════════════════════════════
def draw_topology(devices, edges, topo_name,
                  theme="dark", output_dir=".", base_name="topology"):

    T = THEMES[theme]
    NODE_R = 0.30

    MG = nx.MultiGraph()
    MG.add_nodes_from(devices.keys())
    for src, dst, si, di, lname in edges:
        MG.add_edge(src, dst, src_iface=si, dst_iface=di, link=lname)

    pair_counts = defaultdict(list)
    for src, dst, si, di, lname in edges:
        pair_counts[tuple(sorted([src, dst]))].append((src, dst, si, di, lname))

    pos = nx.circular_layout(nx.Graph(MG), scale=2.5)

    xs = [v[0] for v in pos.values()]
    ys = [v[1] for v in pos.values()]
    layout_cx = sum(xs) / len(xs)
    layout_cy = sum(ys) / len(ys)

    fig, ax = plt.subplots(figsize=(16, 11), facecolor=T["bg"])
    ax.set_facecolor(T["bg"])
    ax.set_aspect("equal")
    ax.axis("off")

    pad = 1.8
    ax.set_xlim(min(xs)-pad, max(xs)+pad)
    ax.set_ylim(min(ys)-pad*1.8, max(ys)+pad)

    # Grid
    for gx in np.arange(math.floor(min(xs)-pad), math.ceil(max(xs)+pad)+1):
        ax.axvline(gx, color=T["grid"], linewidth=0.35, alpha=0.45, zorder=0)
    for gy in np.arange(math.floor(min(ys)-pad*1.8), math.ceil(max(ys)+pad)+1):
        ax.axhline(gy, color=T["grid"], linewidth=0.35, alpha=0.45, zorder=0)

    # ── Edges ─────────────────────────────────
    for key, link_list in pair_counts.items():
        n = len(link_list)
        is_multi = n > 1
        color = T["edge_multi"] if is_multi else T["edge_single"]
        lw = 1.8 + (0.3 if is_multi else 0)

        if n == 1:   bends = [0.0]
        elif n == 2: bends = [-0.30, 0.30]
        elif n == 3: bends = [-0.40, 0.0, 0.40]
        else:
            half = (n-1)/2
            bends = [round((i-half)*0.32, 3) for i in range(n)]

        for idx, (src, dst, si, di, _) in enumerate(link_list):
            x1, y1 = pos[src]
            x2, y2 = pos[dst]
            bx, by = bezier_curve(x1, y1, x2, y2, bends[idx])

            ax.plot(bx, by, color=color, alpha=0.88, linewidth=lw,
                    solid_capstyle="round", zorder=2)

            si_short = abbrev_iface(si)
            di_short = abbrev_iface(di)
            for frac, label in [(0.20, si_short), (0.80, di_short)]:
                pt = int(frac * 119)
                ax.text(bx[pt], by[pt], label,
                        ha="center", va="center", fontsize=5.0,
                        color=T["edge_label"], fontfamily="monospace", zorder=3,
                        path_effects=[pe.withStroke(linewidth=1.8, foreground=T["bg"])])

    # ── Nodes ─────────────────────────────────
    for name, (x, y) in pos.items():
        dev = devices.get(name, {})
        draw_node(ax, x, y, name, dev.get("type", "switch"), T, NODE_R)

    # ── IP labels ─────────────────────────────
    draw_ip_labels(ax, pos, devices, T, r=NODE_R,
                   center=(layout_cx, layout_cy))

    # ── Title ─────────────────────────────────
    fig.text(0.5, 0.965, topo_name.upper().replace("_", " ").replace("-", " "),
             ha="center", va="top", fontsize=17, fontweight="bold",
             color=T["title"], fontfamily="monospace",
             path_effects=[pe.withStroke(linewidth=3, foreground=T["bg"])])

    # ── Stats footer ──────────────────────────
    multi_pairs = sum(1 for v in pair_counts.values() if len(v) > 1)
    fig.text(0.5, 0.025,
             f"Devices: {len(devices)}   Links: {len(edges)}   Multi-link pairs: {multi_pairs}",
             ha="center", va="bottom", fontsize=7.5,
             color=T["subtitle"], fontfamily="monospace")

    # ── Dynamic legend ────────────────────────
    present_types = sorted({d["type"] for d in devices.values()})
    legend_handles = []
    for dtype in present_types:
        stroke = T[f"stroke_{dtype}"]
        legend_handles.append(
            Line2D([0],[0], marker="o", color="none",
                   markerfacecolor=T["node_fill"],
                   markeredgecolor=stroke,
                   markersize=9, label=TYPE_LABEL[dtype])
        )
    legend_handles += [
        Line2D([0],[0], color=T["edge_single"], linewidth=2.0, label="Single link"),
        Line2D([0],[0], color=T["edge_multi"],  linewidth=2.0, label="Multi-link"),
    ]
    ax.legend(handles=legend_handles,
              loc="lower left", frameon=True, framealpha=0.92,
              facecolor=T["legend_bg"], edgecolor=T["legend_edge"],
              fontsize=7.5, labelcolor=T["edge_label"],
              handlelength=2.2, borderpad=0.8)

    plt.tight_layout(rect=[0, 0.03, 1, 0.94])

    # ── Save ──────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, f"{base_name}.png")
    svg_path = os.path.join(output_dir, f"{base_name}.svg")

    fig.savefig(png_path, dpi=300, bbox_inches="tight",
                facecolor=T["bg"], edgecolor="none")
    fig.savefig(svg_path, format="svg", bbox_inches="tight",
                facecolor=T["bg"], edgecolor="none")
    plt.close(fig)

    print(f"  [saved] {png_path}")
    print(f"  [saved] {svg_path}")
    return png_path, svg_path


# ══════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Topology",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python topology_visualizer.py testbed.yaml
              python topology_visualizer.py testbed.yaml --theme light
              python topology_visualizer.py testbed.yaml --output-dir ./diagrams --name lab1

            Device type detection (by name keywords):
              switch   : sw, switch, l2, l3, core, access, dist, agg, bridge
              router   : rtr, router, gw, gateway, pe, ce, asbr, abr, edge
              firewall : fw, firewall, asa, ftd, palo, fortigate, ngfw
              server   : srv, server, host, pc, vm, linux, esxi
              ap       : ap, wap, wifi, wireless
        """)
    )
    parser.add_argument("yaml_file",    help="Path to the testbed YAML file")
    parser.add_argument("--theme",      default="dark", choices=["dark", "light"],
                        help="Color theme  (default: dark)")
    parser.add_argument("--output-dir", default=".", dest="output_dir",
                        help="Output directory  (default: current dir)")
    parser.add_argument("--name",       default="topology",
                        help="Base filename for outputs  (default: topology)")
    args = parser.parse_args()

    if not os.path.isfile(args.yaml_file):
        sys.exit(f"[error] File not found: {args.yaml_file}")

    print(f"[parse] {args.yaml_file}")
    devices, edges, topo_name = parse_testbed(args.yaml_file)

    pc = defaultdict(int)
    for s, d, *_ in edges:
        pc[tuple(sorted([s, d]))] += 1
    multi_pairs = sum(1 for v in pc.values() if v > 1)

    type_summary = defaultdict(int)
    for d in devices.values():
        type_summary[d["type"]] += 1

    print(f"  [info] devices      : {len(devices)}")
    for dtype, count in sorted(type_summary.items()):
        print(f"  [info]   {dtype:<10}: {count}")
    print(f"  [info] links        : {len(edges)}")
    print(f"  [info] multi-link   : {multi_pairs} pair(s)")
    print(f"[draw] theme={args.theme}  layout=circular")

    file_title = os.path.splitext(os.path.basename(args.yaml_file))[0]

    draw_topology(
        devices, edges, file_title,
        theme=args.theme,
        output_dir=args.output_dir,
        base_name=args.name,
    )
    print("[done]")


if __name__ == "__main__":
    main()