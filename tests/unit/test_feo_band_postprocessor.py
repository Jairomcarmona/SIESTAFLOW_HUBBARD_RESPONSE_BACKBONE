import numpy as np

from FEO_SCF_DIAGNOSTIC_EXPORT_20261001.analyze_feo_seekpath_bands import classify_spectrum


def test_classifies_insulating_spectrum_and_extracts_edges():
    # Shape is (k-point, spin, band); every sampled band stays on one side of EF.
    energies = np.array([[[-2.0, 1.0, 2.0]], [[-1.0, 1.5, 3.0]]])

    result = classify_spectrum(energies)

    assert result["classification"] == "INSULATOR"
    assert result["crossing_bands"] == []
    assert result["vbm_rel_ev"] == -1.0
    assert result["cbm_rel_ev"] == 1.0
    assert result["indirect_gap_ev"] == 2.0


def test_classifies_a_lower_index_fermi_crossing_as_metal():
    # Band 1 crosses EF even though a fixed high occupied-band index is absent.
    energies = np.array([[[-0.2, 0.6]], [[0.2, 0.8]]])

    result = classify_spectrum(energies)

    assert result["classification"] == "METAL"
    assert result["crossing_bands"] == [1]
    assert result["vbm_rel_ev"] is None
    assert result["indirect_gap_ev"] is None


def test_rejects_false_gap_from_fixed_band_count_when_lower_band_crosses():
    # The old 22/23 rule sees a positive 0.5 eV separation, while band 1 and
    # bands 2-22 cross EF. This spectrum must be classified as metallic first.
    first_k = np.array([-2.0] + [-1.0] * 21 + [2.0, 3.0])
    second_k = np.array([0.2] + [0.5] * 21 + [1.0, 2.0])
    energies = np.stack([first_k, second_k])[:, None, :]
    old_fixed_count_gap = second_k[22] - second_k[21]
    assert old_fixed_count_gap > 0

    result = classify_spectrum(energies)

    assert result["classification"] == "METAL"
    assert 1 in result["crossing_bands"]
    assert result["indirect_gap_ev"] is None
