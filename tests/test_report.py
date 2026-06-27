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
    assert "claude-opus-4-8" in out
    assert "claude-sonnet-4-6" in out


def test_total_row_sums_ranges():
    out = render_report(ROWS, group_by="total")
    # somme GWP : min 1.5, max 3.0
    assert "1.5" in out and "3" in out


def test_group_by_project_aggregates():
    out = render_report(ROWS, group_by="project")
    assert "projA" in out
    # un seul groupe projet
    assert out.count("projA") == 1
