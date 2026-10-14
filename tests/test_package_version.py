"""Keep installed package and imported source release identifiers aligned."""
from importlib.metadata import version as distribution_version

import vera_habitat


def test_package_version_matches_imported_module():
    assert distribution_version("vera-habitat") == vera_habitat.__version__
