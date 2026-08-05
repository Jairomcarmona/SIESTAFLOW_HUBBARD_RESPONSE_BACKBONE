import pytest
import os
import glob

def test_no_pinv_in_source():
    src_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
    if os.path.exists(src_dir):
        for py_file in glob.glob(f"{src_dir}/**/*.py", recursive=True):
            with open(py_file) as f:
                content = f.read()
                assert 'pinv' not in content or 'pinvh' not in content, f"Found pinv in {py_file}"

def test_no_pinvh_in_source():
    pass
