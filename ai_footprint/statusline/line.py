import re


def _short_name(model: str) -> str:
    """Raccourcit un nom de modèle Anthropic pour la statusline
    (ex. « claude-sonnet-4-6 » → « sonnet-4 », « claude-sonnet-5 » → « sonnet-5 »)."""
    name = model.removeprefix("claude-")
    match = re.match(r"([a-z]+-\d+)", name)
    return match.group(1) if match else name


# Paliers d'unités (du plus grand au plus petit) pour chaque indicateur, afin
# d'éviter les « 0.000… » : on descend d'un palier tant que la plus grande
# valeur (min ou max) reste sous le seuil du palier courant.
_ENERGY_LADDER = (("kWh", 1.0), ("Wh", 1e-3), ("mWh", 1e-6))
_GWP_LADDER = (("kgCO2eq", 1.0), ("gCO2eq", 1e-3), ("mgCO2eq", 1e-6))
_WATER_LADDER = (("L", 1.0), ("cL", 1e-2), ("mL", 1e-3))


def _scale(min_v: float, max_v: float, ladder: tuple) -> tuple[float, float, str]:
    ref = max(abs(min_v), abs(max_v))
    for unit, factor in ladder:
        if ref >= factor:
            return min_v / factor, max_v / factor, unit
    unit, factor = ladder[-1]
    return min_v / factor, max_v / factor, unit


def render_statusline(rows: list[dict]) -> str:
    if not rows:
        # Ligne à 0 plutôt que vide : une statusline vide n'est pas
        # (ré)affichée par Claude Code.
        return f"🌍 0 {_GWP_LADDER[0][0]} · 💧 0 {_WATER_LADDER[0][0]} · ⚡ 0 {_ENERGY_LADDER[0][0]}"
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
    g_min, g_max, g_unit = _scale(g_min, g_max, _GWP_LADDER)
    w_min, w_max, w_unit = _scale(w_min, w_max, _WATER_LADDER)
    e_min, e_max, e_unit = _scale(e_min, e_max, _ENERGY_LADDER)
    return (
        f"{prefix}🌍 {g_min:.3g}–{g_max:.3g} {g_unit} · "
        f"💧 {w_min:.3g}–{w_max:.3g} {w_unit} · "
        f"⚡ {e_min:.3g}–{e_max:.3g} {e_unit}{note}"
    )
