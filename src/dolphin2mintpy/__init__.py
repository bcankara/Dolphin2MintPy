"""
dolphin2mintpy — Bridge between Dolphin InSAR processor and MintPy time-series analysis.

Dolphin produces GeoTIFF outputs with GDAL metadata, while MintPy expects ROI_PAC-style
.rsc sidecar files. This package bridges that gap by generating .rsc metadata files and
MintPy-compatible configuration templates.
"""

__version__ = "0.1.0"
__author__ = "Burak Can Kara"

from dolphin2mintpy.prepare import prepare_rsc, prepare_stack

__all__ = [
    "__version__",
    "prepare_rsc",
    "prepare_stack",
]
