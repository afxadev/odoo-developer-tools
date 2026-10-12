try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("odoo-developer-tools")
except Exception:
    __version__ = "0.0.0"