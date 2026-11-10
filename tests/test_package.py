import oam_eoapi_stats


def test_version():
    assert isinstance(oam_eoapi_stats.__version__, str)
