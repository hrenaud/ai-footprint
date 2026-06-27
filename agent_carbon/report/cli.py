from agent_carbon.impact.engine import CRITERIA

_LABELS = {
    "energy": "Énergie(kWh)", "gwp": "GWP(kgCO2e)", "adpe": "ADPe(kgSb)",
    "pe": "PE(MJ)", "wcf": "Eau(L)",
}


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

    header = ["groupe"] + [_LABELS[c] for c in CRITERIA]
    lines = [" | ".join(header), "-" * (len(" | ".join(header)))]
    totals = {c: [0.0, 0.0] for c in CRITERIA}
    for name, vals in groups.items():
        cells = [name]
        for c in CRITERIA:
            cells.append(_fmt(vals[c][0], vals[c][1]))
            totals[c][0] += vals[c][0]
            totals[c][1] += vals[c][1]
        lines.append(" | ".join(cells))
    if group_by != "total":
        lines.append("-" * (len(" | ".join(header))))
        lines.append(" | ".join(["TOTAL"] + [_fmt(totals[c][0], totals[c][1]) for c in CRITERIA]))
    lines.append("")
    lines.append("Fourchettes min–max (incertitude irréductible : région datacenter inconnue). "
                 "Zone élec configurable (défaut USA). Impact basé sur les tokens de sortie.")
    return "\n".join(lines)
