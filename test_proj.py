import sys
import os
sys.path.insert(0, 'src')
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder
builder = FdfBuilder()
s = builder.construct_dftu_proj_block([{"species": "Mn", "n": 3, "l": 2}], 0.05)
print(repr(s))
