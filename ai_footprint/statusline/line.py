import re


def _short_name(model: str) -> str:
    """Raccourcit un nom de modèle Anthropic pour la statusline
    (ex. « claude-sonnet-4-6 » → « sonnet-4 », « claude-sonnet-5 » → « sonnet-5 »)."""
    name = model.removeprefix("claude-")
    match = re.match(r"([a-z]+-\d+)", name)
    return match.group(1) if match else name


def render_statusline(rows: list[dict]) -> str:
    if not rows:
        return ""
    e_min = sum(r["energy_min"] for r in rows)
    e_max = sum(r["energy_max"] for r in rows)
    g_min = sum(r["gwp_min"] for r in rows)
    g_max = sum(r["gwp_max"] for r in rows)
    w_min = sum(r["wcf_min"] for r in rows)
    w_max = sum(r["wcf_max"] for r in rows)
    # Un modèle trop récent pour le registre EcoLogits (ex. claude-sonnet-5)
    # utilise un stand-in extrapolé d'une version sœur — signalé par « ≈ » +
    # un rappel court (modèle inconnu → params de la version de repli).
    note = ""
    for r in rows:
        warnings = r.get("warnings") or ""
        marker = "params-extrapolated-anthropic:"
        idx = warnings.find(marker)
        if idx != -1:
            sibling = warnings[idx + len(marker):].split('"')[0]
            model = r.get("model", "")
            note = f" ({_short_name(model)} inconnu, params {_short_name(sibling)})"
            break
    prefix = "≈ " if note else ""
    return (
        f"{prefix}🌍 {g_min:.3g}–{g_max:.3g} kgCO2eq · "
        f"💧 {w_min:.3g}–{w_max:.3g} L · "
        f"⚡ {e_min:.3g}–{e_max:.3g} kWh{note}"
    )
