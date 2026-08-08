with open("tests/backend/test_fdf_builder.py", "r") as f:
    c = f.read()
c = c.replace('proj_block = "%block DFTU.proj\\\\n  Mn   1\\\\n  3  2\\\\n  0.0500  0.0000\\\\n  3.0000  0.0500\\\\n%endblock DFTU.proj"',
    'proj_block = "%block DFTU.proj\\n  Mn   1\\n  3  2\\n  0.0500  0.0000\\n  3.0000  0.0500\\n%endblock DFTU.proj"')
with open("tests/backend/test_fdf_builder.py", "w") as f:
    f.write(c)
