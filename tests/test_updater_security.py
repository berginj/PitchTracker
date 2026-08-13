"""Security defaults for application updates."""

import inspect

from updater import download_update


def test_download_update_requires_checksum_by_default():
    parameter = inspect.signature(download_update).parameters["require_checksum"]

    assert parameter.default is True
