from pathlib import Path

import launcher


def test_initial_launch_creates_browsable_projects_folder(tmp_path):
    folder=tmp_path/'new workstation'
    launcher.prepare_runtime(folder)
    assert (folder/'projects').is_dir()
    original=folder/'projects'/'existing.txt'
    original.write_text('keep')
    launcher.prepare_runtime(folder)
    assert original.read_text()=='keep'


def test_data_folder_explicit_choice_wins_over_environment(tmp_path,monkeypatch):
    monkeypatch.setenv('LOGOMOCK_DATA_DIR',str(tmp_path/'environment'))
    assert launcher.data_folder(tmp_path/'explicit')==(tmp_path/'explicit').resolve()


def test_frozen_launch_uses_the_collected_tcl_runtime_next_to_executable(tmp_path, monkeypatch):
    executable = tmp_path / 'LogoMock.exe'
    executable.touch()
    runtime = tmp_path / '_internal'
    (runtime / '_tcl_data').mkdir(parents=True)
    (runtime / '_tk_data').mkdir()
    (runtime / '_tcl_data' / 'init.tcl').touch()
    (runtime / '_tk_data' / 'tk.tcl').touch()
    monkeypatch.setattr(launcher.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(launcher.sys, 'executable', str(executable))
    monkeypatch.delenv('TCL_LIBRARY', raising=False)
    monkeypatch.delenv('TK_LIBRARY', raising=False)

    launcher.prepare_runtime(tmp_path / 'workstation')

    assert Path(launcher.os.environ['TCL_LIBRARY']) == runtime / '_tcl_data'
    assert Path(launcher.os.environ['TK_LIBRARY']) == runtime / '_tk_data'
