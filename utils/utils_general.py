from utils.utils_pyproj import createCRS, reprojectToCrs


def getDegreesBboxFromLocationAndRadius(
    lat: float, lon: float, radius: float
) -> list[tuple]:
    """Get min & max values of lat/lon given location and radius."""
    projectedCrs = createCRS(lat, lon)
    lonPlus1, latPlus1 = reprojectToCrs(1, 1, projectedCrs, "EPSG:4326")
    scaleXdegrees = lonPlus1 - lon  # degrees in 1m of longitude
    scaleYdegrees = latPlus1 - lat  # degrees in 1m of latitude

    min_lat_lon = (lat - scaleYdegrees * radius, lon - scaleXdegrees * radius)
    max_lat_lon = (lat + scaleYdegrees * radius, lon + scaleXdegrees * radius)

    return min_lat_lon, max_lat_lon
