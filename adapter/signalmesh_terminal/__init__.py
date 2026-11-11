"""SignalMesh cTrader-style desktop terminal — READ-ONLY adapter.

This package reads what SignalMesh already computed and reshapes it for the
terminal UI. It computes no signal, no level, no bias and no verdict. It
never writes to SignalMesh: the only HTTP verb it knows is GET.
"""
from .build import version as _version

__version__ = _version()      # the VERSION file; never typed here
