import pytest
from app.config import get_engine
from app.engine.base import EngineError
from app.engine.inkscape import InkscapeEngine


def test_failed_conversion_cannot_reuse_a_stale_png(tmp_path):
    engine=get_engine()
    if not engine.available():
        pytest.skip('Inkscape required for real conversion regression')
    source=tmp_path/'broken.svg'
    source.write_text('not an svg')
    output=tmp_path/'old.png'
    output.write_bytes(b'old-image')
    with pytest.raises(EngineError):
        engine.svg_to_png(source,output)
    assert output.read_bytes()==b'old-image'


def test_inkscape_page_conversion_tries_modern_then_legacy_flag(monkeypatch, tmp_path):
    engine = InkscapeEngine(exe=tmp_path / 'inkscape.exe')
    calls = []
    monkeypatch.setattr(engine, '_export', lambda src, dst, kind, extra=(): calls.append(tuple(extra)))

    engine.to_svg_page(tmp_path / 'source.pdf', tmp_path / 'page.svg', 2)

    assert calls[0] == ('--pages=2',)


def test_inkscape_page_conversion_falls_back_to_legacy_flag(monkeypatch, tmp_path):
    engine = InkscapeEngine(exe=tmp_path / 'inkscape.exe')
    calls = []

    def export(_src, _dst, _kind, extra=()):
        calls.append(tuple(extra))
        if len(calls) == 1:
            raise EngineError('CONVERT_FAILED', 'modern flag unsupported')

    monkeypatch.setattr(engine, '_export', export)

    engine.to_svg_page(tmp_path / 'source.pdf', tmp_path / 'page.svg', 2)

    assert calls == [('--pages=2',), ('--pdf-page=2',)]
