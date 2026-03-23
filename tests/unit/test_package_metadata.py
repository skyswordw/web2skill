def test_package_version_is_exposed() -> None:
    from web2skill import __version__

    assert __version__ == "0.1.0"
