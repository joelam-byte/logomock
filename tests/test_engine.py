import pytest
from app.config import get_engine
from app.engine.base import EngineError


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
