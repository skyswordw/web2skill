def test_package_version_is_exposed() -> None:
    from importlib.metadata import version

    from web2skill import __version__

    assert __version__ == version("web2skill")
