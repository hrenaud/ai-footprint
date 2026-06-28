from agent_carbon.report.cli import render_report


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


def test_group_by_model_lists_each_model():
    out = render_report(ROWS, group_by="model")
    # noms raccourcis (préfixe claude- retiré) pour tenir en largeur
    assert "opus-4-8" in out
    assert "sonnet-4-6" in out


def test_model_names_shortened_in_table():
    out = render_report(ROWS, group_by="model")
    table = out.split("Impact total")[0]
    assert "claude-" not in table


def test_negligible_row_collapses_to_approx_zero():
    rows = [
        {"model": "claude-opus-4-8", "project": "p",
         "gwp_min": 8.0, "gwp_max": 13.0, "energy_min": 19.0, "energy_max": 33.0,
         "adpe_min": 4e-5, "adpe_max": 4.1e-5, "pe_min": 192.0, "pe_max": 335.0,
         "wcf_min": 61.0, "wcf_max": 135.0},
        {"model": "claude-opus-4-6", "project": "p",  # négligeable ~1e-10
         "gwp_min": 2.8e-5, "gwp_max": 5e-5, "energy_min": 6e-5, "energy_max": 1e-4,
         "adpe_min": 1.5e-10, "adpe_max": 1.6e-10, "pe_min": 6e-4, "pe_max": 1e-3,
         "wcf_min": 2e-4, "wcf_max": 5e-4},
    ]
    out = render_report(rows, group_by="model")
    assert "≈0" in out


def test_total_row_sums_ranges():
    out = render_report(ROWS, group_by="total")
    # somme GWP : min 1.5, max 3.0 → reste en kgCO2eq (≥ 1)
    assert "1.5" in out and "3" in out


def test_group_by_project_aggregates():
    out = render_report(ROWS, group_by="project")
    assert "projA" in out
    # un seul groupe projet
    assert out.count("projA") == 1


def test_rows_sorted_descending_by_gwp():
    out = render_report(ROWS, group_by="model")
    # opus (gwp 1–2, mid 1.5) doit précéder sonnet (0.5–1, mid 0.75)
    assert out.index("opus-4-8") < out.index("sonnet-4-6")


def test_bar_and_percent_rendered():
    out = render_report(ROWS, group_by="model")
    assert "█" in out and "%" in out


def test_long_tail_collapsed_into_autres():
    rows = [
        {"model": f"claude-m{i:02d}", "project": f"p{i:02d}",
         "gwp_min": 0.1 * (i + 1), "gwp_max": 0.2 * (i + 1),
         "energy_min": 0.1, "energy_max": 0.2, "adpe_min": 1e-6, "adpe_max": 2e-6,
         "pe_min": 0.1, "pe_max": 0.2, "wcf_min": 0.1, "wcf_max": 0.2}
        for i in range(12)
    ]
    out = render_report(rows, group_by="project")
    assert "autres" in out


def test_icon_summary_section_present():
    out = render_report(ROWS, group_by="model")
    for icon in ("⚡", "🌍", "💧", "⛏", "🔥"):
        assert icon in out
    assert "Impact total" in out
    # GWP total agrégé = 1.5 (reste en kgCO2eq)
    assert "1.5" in out


def test_tiny_values_are_scaled_to_readable_units():
    # ADPe ~ 4e-05 kgSbeq doit s'afficher en mg (≈ 40), pas en notation 4e-05.
    rows = [{"model": "m", "project": "p",
             "energy_min": 19.0, "energy_max": 33.0,
             "gwp_min": 8.0, "gwp_max": 13.0,
             "adpe_min": 4.0e-5, "adpe_max": 4.16e-5,
             "pe_min": 192.0, "pe_max": 335.0,
             "wcf_min": 61.0, "wcf_max": 135.0}]
    out = render_report(rows, group_by="total")
    assert "mgSbeq" in out          # unité mise à l'échelle
    assert "4e-05" not in out       # plus de notation scientifique illisible
    assert "40" in out and "41.6" in out
