from agent_carbon.report.cli import render_intensity, render_report


ROWS = [
    {"model": "claude-opus-4-8", "project": "projA",
     "gwp_min": 1.0, "gwp_max": 2.0, "energy_min": 0.1, "energy_max": 0.2,
     "adpe_min": 1e-9, "adpe_max": 2e-9, "pe_min": 0.3, "pe_max": 0.6,
     "wcf_min": 0.01, "wcf_max": 0.02},
    {"model": "claude-sonnet-4-6", "project": "projA",
     "gwp_min": 0.5, "gwp_max": 1.0, "energy_min": 0.05, "energy_max": 0.1,
     "adpe_min": 1e-9, "adpe_max": 1e-9, "pe_min": 0.1, "pe_max": 0.2,
     "wcf_min": 0.005, "wcf_max": 0.01},
]


def test_report_shows_central_and_range_in_one_section():
    out = render_report(ROWS)
    # GWP total 1.5–3.0 → valeur centrale ~2.25 ET la plage 1.5–3 dans la même section
    assert "~2.25" in out
    assert "1.5–3" in out


def test_report_lists_five_criteria_with_icons():
    out = render_report(ROWS)
    for icon in ("⚡", "🌍", "💧", "⛏", "🔥"):
        assert icon in out
    assert "Impact total" in out


def test_tiny_values_scaled_to_readable_units():
    rows = [{"model": "m", "project": "p",
             "energy_min": 19.0, "energy_max": 33.0,
             "gwp_min": 8.0, "gwp_max": 13.0,
             "adpe_min": 4.0e-5, "adpe_max": 4.16e-5,
             "pe_min": 192.0, "pe_max": 335.0,
             "wcf_min": 61.0, "wcf_max": 135.0}]
    out = render_report(rows)
    # la plage ADPe doit être en mg, pas en 4e-05
    assert "mgSbeq" in out
    assert "4e-05" not in out
    assert "40" in out and "41.6" in out


def test_render_intensity_shows_tokens_bar_and_emissions():
    rows = [
        {"model": "claude-opus-4-8", "hours": 1.0, "tokens": 566000,
         "energy": 5.0, "gwp": 1.07, "adpe": 5e-6, "pe": 50.0, "wcf": 9.0},
        {"model": "claude-haiku-4-5", "hours": 1.0, "tokens": 276000,
         "energy": 1.0, "gwp": 0.014, "adpe": 1e-6, "pe": 10.0, "wcf": 2.0},
    ]
    out = render_intensity(rows)
    assert "tok/h" in out
    assert "█" in out                       # barre de visualisation des tokens
    for icon in ("🌍", "⚡", "💧", "⛏", "🔥"):
        assert icon in out
    # trié par tok/h décroissant : opus (566k) avant haiku (276k)
    assert out.index("opus-4-8") < out.index("haiku-4-5")


def test_render_intensity_empty():
    assert render_intensity([]) == ""
