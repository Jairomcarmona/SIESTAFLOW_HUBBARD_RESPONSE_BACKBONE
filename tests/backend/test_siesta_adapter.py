import pytest
import numpy as np

from siestaflow_hubbard.siesta_backend.adapter import SiestaLRAdapter
from siestaflow_hubbard.domain.exceptions import ChecksumFailure, SemanticValidationFailure, SiestaParserError


MOCK_VALID_OUTPUT = """
InitMesh: Mesh cutoff (required, used) =   400.000   401.186 Ry
hubbard_term: recalculating local occupations    1
 hubbard_term: projector occupations
 hubbard_term: atom, species:            1           1
   1   1     0.87010     0.31587
   1   2     0.00003     0.00020
   1   3     0.00012    -0.00024
   1   4    -0.15640     0.11818
   1   5    -0.00003     0.00052
   2   1     0.00003     0.00020
   2   2     0.76889     0.35331
   2   3    -0.00457    -0.03454
   2   4     0.00022     0.00039
   2   5    -0.18052     0.12726
   3   1     0.00012    -0.00024
   3   2    -0.00457    -0.03454
   3   3     0.98573     0.25363
   3   4     0.00017    -0.00036
   3   5    -0.00116     0.04344
   4   1    -0.15640     0.11818
   4   2     0.00022     0.00039
   4   3     0.00017    -0.00036
   4   4     0.79221     0.36451
   4   5     0.00011     0.00044
   5   1    -0.00003     0.00052
   5   2    -0.18052     0.12726
   5   3    -0.00116     0.04344
   5   4     0.00011     0.00044
   5   5     0.84289     0.32107
hubbard_term: Total projector shell
Occupations:     4.259807    1.608383    5.868190
"""

MOCK_CHECKSUM_FAIL_UP = """
 hubbard_term: projector occupations
 hubbard_term: atom, species:            1           1
   1   1     0.87010     0.31587
   1   2     0.00003     0.00020
   1   3     0.00012    -0.00024
   1   4    -0.15640     0.11818
   1   5    -0.00003     0.00052
   2   1     0.00003     0.00020
   2   2     0.76889     0.35331
   2   3    -0.00457    -0.03454
   2   4     0.00022     0.00039
   2   5    -0.18052     0.12726
   3   1     0.00012    -0.00024
   3   2    -0.00457    -0.03454
   3   3     0.98573     0.25363
   3   4     0.00017    -0.00036
   3   5    -0.00116     0.04344
   4   1    -0.15640     0.11818
   4   2     0.00022     0.00039
   4   3     0.00017    -0.00036
   4   4     0.79221     0.36451
   4   5     0.00011     0.00044
   5   1    -0.00003     0.00052
   5   2    -0.18052     0.12726
   5   3    -0.00116     0.04344
   5   4     0.00011     0.00044
   5   5     0.84289     0.32107
hubbard_term: Total projector shell
Occupations:     3.000000    1.608383    4.608383
"""

MOCK_CHECKSUM_FAIL_DOWN = """
 hubbard_term: projector occupations
 hubbard_term: atom, species:            1           1
   1   1     0.87010     0.31587
   1   2     0.00003     0.00020
   1   3     0.00012    -0.00024
   1   4    -0.15640     0.11818
   1   5    -0.00003     0.00052
   2   1     0.00003     0.00020
   2   2     0.76889     0.35331
   2   3    -0.00457    -0.03454
   2   4     0.00022     0.00039
   2   5    -0.18052     0.12726
   3   1     0.00012    -0.00024
   3   2    -0.00457    -0.03454
   3   3     0.98573     0.25363
   3   4     0.00017    -0.00036
   3   5    -0.00116     0.04344
   4   1    -0.15640     0.11818
   4   2     0.00022     0.00039
   4   3     0.00017    -0.00036
   4   4     0.79221     0.36451
   4   5     0.00011     0.00044
   5   1    -0.00003     0.00052
   5   2    -0.18052     0.12726
   5   3    -0.00116     0.04344
   5   4     0.00011     0.00044
   5   5     0.84289     0.32107
hubbard_term: Total projector shell
Occupations:     4.259807    2.000000    6.259807
"""

MOCK_CHECKSUM_FAIL_TOTAL = """
 hubbard_term: projector occupations
 hubbard_term: atom, species:            1           1
   1   1     0.87010     0.31587
   1   2     0.00003     0.00020
   1   3     0.00012    -0.00024
   1   4    -0.15640     0.11818
   1   5    -0.00003     0.00052
   2   1     0.00003     0.00020
   2   2     0.76889     0.35331
   2   3    -0.00457    -0.03454
   2   4     0.00022     0.00039
   2   5    -0.18052     0.12726
   3   1     0.00012    -0.00024
   3   2    -0.00457    -0.03454
   3   3     0.98573     0.25363
   3   4     0.00017    -0.00036
   3   5    -0.00116     0.04344
   4   1    -0.15640     0.11818
   4   2     0.00022     0.00039
   4   3     0.00017    -0.00036
   4   4     0.79221     0.36451
   4   5     0.00011     0.00044
   5   1    -0.00003     0.00052
   5   2    -0.18052     0.12726
   5   3    -0.00116     0.04344
   5   4     0.00011     0.00044
   5   5     0.84289     0.32107
hubbard_term: Total projector shell
Occupations:     4.259807    1.608383    7.000000
"""


def test_siesta_lr_adapter_valid_mock_parsing():
    adapter = SiestaLRAdapter()
    results = adapter.parse_converged_hubbard_occupations(MOCK_VALID_OUTPUT)

    assert 1 in results
    atom_data = results[1]

    matrix_up = atom_data["matrix_up"]
    matrix_down = atom_data["matrix_down"]

    assert matrix_up.shape == (5, 5)
    assert matrix_down.shape == (5, 5)

    computed_up = float(np.trace(matrix_up))
    computed_down = float(np.trace(matrix_down))

    assert abs(computed_up - atom_data["trace_up"]) < 1e-4
    assert abs(computed_down - atom_data["trace_down"]) < 1e-4
    assert abs(computed_up - 4.259807) < 1e-4
    assert abs(computed_down - 1.608383) < 1e-4
    assert abs((computed_up + computed_down) - 5.868190) < 1e-4


def test_siesta_lr_adapter_checksum_failure_spin_up():
    adapter = SiestaLRAdapter()
    with pytest.raises(ChecksumFailure, match="Spin-UP trace mismatch"):
        adapter.parse_converged_hubbard_occupations(MOCK_CHECKSUM_FAIL_UP)


def test_siesta_lr_adapter_checksum_failure_spin_down():
    adapter = SiestaLRAdapter()
    with pytest.raises(ChecksumFailure, match="Spin-DOWN trace mismatch"):
        adapter.parse_converged_hubbard_occupations(MOCK_CHECKSUM_FAIL_DOWN)


def test_siesta_lr_adapter_checksum_failure_total():
    adapter = SiestaLRAdapter()
    with pytest.raises(ChecksumFailure, match="Total trace mismatch"):
        adapter.parse_converged_hubbard_occupations(MOCK_CHECKSUM_FAIL_TOTAL)


def test_siesta_lr_adapter_extract_occupations():
    adapter = SiestaLRAdapter()
    records = adapter.extract_occupations(
        out_filename=MOCK_VALID_OUTPUT,
        response_mode="SCREENED",
        alpha=0.05,
        target_atom_idx=1,
    )

    assert len(records) == 1
    rec = records[0]
    assert rec.response_mode == "SCREENED"
    assert rec.alpha_ev == 0.05
    assert abs(rec.occupation - 5.868190) < 1e-4
