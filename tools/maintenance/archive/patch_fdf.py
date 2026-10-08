import os

file_path = r"tests/backend/test_fdf_builder.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix SystemLabel
content = content.replace('"SystemLabel         MnO_BARE_p0p05"', '"SystemLabel MnO_BARE_p0p05"')
content = content.replace('"SystemLabel         MnO_SCR_m0p10"', '"SystemLabel MnO_SCR_m0p10"')

# Fix MaxSCFIterations
content = content.replace('"MaxSCFIterations    2"', '"MaxSCFIterations 2"')

# Fix MixingWeight
content = content.replace(r'DM\.MixingWeight', r'SCF\.Mixer\.Weight')
content = content.replace('"DM.MixingWeight     1.0"', '"SCF.Mixer.Weight 1.0"')

# Fix Alpha array match in screened mode
content = content.replace('"  0.0000  -0.1000"', '"  -0.1000  0.0000"')

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
