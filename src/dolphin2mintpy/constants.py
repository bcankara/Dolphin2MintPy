"""
Sentinel-1 IW-mode radar constants and default values.

These constants are used across the package for .rsc sidecar generation.
Values are derived from ESA Sentinel-1 technical documentation and are
consistent with ISCE2 and MintPy conventions.
"""

# Physical constants
SPEED_OF_LIGHT = 299_792_458.0  # m/s

# Sentinel-1 C-band SAR parameters
S1_CARRIER_FREQUENCY = 5.405e9  # Hz
S1_WAVELENGTH = SPEED_OF_LIGHT / S1_CARRIER_FREQUENCY  # ~0.05546576 m

# Sentinel-1 IW mode pixel dimensions (single-look)
S1_RANGE_PIXEL_SIZE = 2.329562    # m (slant range)
S1_AZIMUTH_PIXEL_SIZE = 13.932898  # m (along track)

# Default orbital parameters (Sentinel-1 nominal)
DEFAULT_EARTH_RADIUS = 6_371_000.0  # m (mean)
DEFAULT_SAT_HEIGHT = 693_000.0      # m (nominal altitude)

# Default processing parameters
DEFAULT_ALOOKS = 1
DEFAULT_RLOOKS = 1
DEFAULT_ANTENNA_SIDE = -1  # right-looking

# MintPy processor label used for GDAL-based reading path
MINTPY_PROCESSOR = "hyp3"

# RSC template for interferogram files
RSC_TEMPLATE = """\
WIDTH                 {width}
LENGTH                {length}
FILE_LENGTH           {length}
XMIN                  0
XMAX                  {xmax}
YMIN                  0
YMAX                  {ymax}
X_FIRST               {x_first}
Y_FIRST               {y_first}
X_STEP                {x_step}
Y_STEP                {y_step}
WAVELENGTH            {wavelength}
RANGE_PIXEL_SIZE      {range_pixel_size}
AZIMUTH_PIXEL_SIZE    {azimuth_pixel_size}
STARTING_RANGE        {starting_range}
PRF                   {prf}
EARTH_RADIUS          {earth_radius}
HEIGHT                {height}
PLATFORM              Sen
ORBIT_DIRECTION       {orbit_direction}
PROCESSOR             {processor}
INSAR_PROCESSOR       {processor}
ANTENNA_SIDE          {antenna_side}
ALOOKS                {alooks}
RLOOKS                {rlooks}
NUMBER_BANDS          {number_bands}
FILE_TYPE             {file_type}
DATA_TYPE             {data_type}
"""

# Additional lines appended for interferogram files (unw, cor, conncomp)
RSC_IFG_EXTRA = """\
DATE12                {date12}
P_BASELINE_TOP_HDR    {bperp}
P_BASELINE_BOTTOM_HDR {bperp}
"""

# Additional lines for geometry files
RSC_GEOM_EXTRA = """\
"""
