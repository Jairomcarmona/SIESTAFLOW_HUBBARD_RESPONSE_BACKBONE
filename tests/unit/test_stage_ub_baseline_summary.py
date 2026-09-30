from fractions import Fraction

from benchmarks.lr_u.forensic_audit.stage_ub_baseline_summary import interval_metrics


def test_interval_summary_uses_endpoint_span_and_reports_nominal_distances_separately():
    result = interval_metrics("6.857300307", "6.870129237", "6.861874364188249", "0.020")
    expected_half_width = Fraction("0.006414465")
    assert result["width"] == Fraction("0.012828930")
    assert result["half_width"] == expected_half_width
    assert result["precision_margin"] == Fraction("0.013585535")
    assert result["interval_center"] == Fraction("6.863714772")
    assert result["lower_distance_from_nominal"] != result["half_width"]
    assert result["upper_distance_from_nominal"] != result["half_width"]
