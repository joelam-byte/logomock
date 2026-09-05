import importlib.util
from pathlib import Path


def load_runtime_tool():
    path = Path(__file__).parents[1] / 'tools' / 'prepare_tk_runtime.py'
    spec = importlib.util.spec_from_file_location('prepare_tk_runtime', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_finds_tcl_and_tk_pair_in_python_style_layout(tmp_path):
    layout = tmp_path / 'python' / 'tcl'
    (layout / 'tcl8.6').mkdir(parents=True)
    (layout / 'tk8.6').mkdir()

    tool = load_runtime_tool()

    assert tool.find_runtime([layout.parent]) == layout
