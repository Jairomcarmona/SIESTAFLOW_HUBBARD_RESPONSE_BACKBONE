import sys
import os
sys.path.insert(0, 'src')
from hubbardflow.siesta_backend.fdf_builder import FdfBuilder
builder = FdfBuilder()
s = builder.construct_dftu_proj_block(
    [{"species": "fixture", "n": 3, "l": 2, "rc": 3.0, "omega": 0.05}],
    0.05, target_species="fixture", execution_mode="DEVELOPMENT",
)
print(repr(s))
