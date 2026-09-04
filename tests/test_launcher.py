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
