from agent_carbon.impact.engine import CRITERIA

_LABELS = {
    "energy": "Énergie(kWh)", "gwp": "GWP(kgCO2e)", "adpe": "ADPe(kgSb)",
    "pe": "PE(MJ)", "wcf": "Eau(L)",
}

# Section agrégée : (icône, libellé, unité). Ordre lisible énergie/CO2/eau/métaux/PE.
_ICONS = {
    "energy": ("⚡", "Énergie", "kWh"),
    "gwp": ("🌍", "GWP", "kgCO2eq"),
    "wcf": ("💧", "Eau", "L"),
    "adpe": ("⛏", "ADPe", "kgSbeq"),
    "pe": ("🔥", "PE", "MJ"),
}
_SUMMARY_ORDER = ("energy", "gwp", "wcf", "adpe", "pe")


def _key(row: dict, group_by: str) -> str:
    if group_by == "total":
        return "TOTAL"
    return row.get(group_by, "?")


def _fmt(lo: float, hi: float) -> str:
    return f"{lo:.3g}–{hi:.3g}"


def render_report(rows: list[dict], group_by: str) -> str:
    groups: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        g = groups.setdefault(_key(row, group_by), {c: [0.0, 0.0] for c in CRITERIA})
        for c in CRITERIA:
            g[c][0] += row[f"{c}_min"]
            g[c][1] += row[f"{c}_max"]

    totals = {c: [0.0, 0.0] for c in CRITERIA}
    for vals in groups.values():
        for c in CRITERIA:
            totals[c][0] += vals[c][0]
            totals[c][1] += vals[c][1]

    # --- Section 1 : tableau aligné ---
    header = ["groupe"] + [_LABELS[c] for c in CRITERIA]
    table = [[name] + [_fmt(vals[c][0], vals[c][1]) for c in CRITERIA]
             for name, vals in groups.items()]
    if group_by != "total":
        table.append(["TOTAL"] + [_fmt(totals[c][0], totals[c][1]) for c in CRITERIA])

    widths = [max(len(r[i]) for r in [header, *table]) for i in range(len(header))]

    def _line(cells: list[str]) -> str:
        return " | ".join(cells[i].ljust(widths[i]) for i in range(len(cells))).rstrip()

    sep = "-" * len(" | ".join(" " * w for w in widths))
    lines = [_line(header), sep]
    lines += [_line(r) for r in table]

    # --- Section 2 : agrégat des impacts avec icônes ---
    lines.append("")
    lines.append("Impact total (tous modèles) :")
    label_w = max(len(name) for _, name, _ in _ICONS.values())
    for c in _SUMMARY_ORDER:
        icon, name, unit = _ICONS[c]
        lines.append(f"  {icon} {name.ljust(label_w)} : {_fmt(totals[c][0], totals[c][1])} {unit}")

    # --- Pied ---
    lines.append("")
    lines.append("Fourchettes min–max (incertitude irréductible : région datacenter inconnue). "
                 "Zone élec configurable (défaut USA). Impact basé sur les tokens de sortie.")
    return "\n".join(lines)
