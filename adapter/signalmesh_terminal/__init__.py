"""SignalMesh cTrader-style desktop terminal — READ-ONLY adapter.

This package reads what SignalMesh already computed and reshapes it for the
terminal UI. It computes no signal, no level, no bias and no verdict. It
never writes to SignalMesh: the only HTTP verb it knows is GET.
"""
__version__ = "0.1.0"
