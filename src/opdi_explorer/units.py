"""The pipeline's unit conversions, in one place that imports nothing.

Storage is SI because it mirrors OpenSky's own schema; everything OPDI shows a
person is in aviation units. Getting a factor wrong is the most likely source
of a silent bug -- a factor 3.28 too large simply draws a plausible-looking
wrong altitude -- so there is one copy, used by the Spark build and by the app,
which must not import Spark.
"""

#: Metres to feet.
M_TO_FT = 3.28084

#: Metres per second to feet per minute.
MS_TO_FT_MIN = 196.850394

#: Metres per second to knots.
MS_TO_KT = 1.94384
