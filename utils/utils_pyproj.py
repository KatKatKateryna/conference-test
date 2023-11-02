from pyproj import CRS, Transformer


def create_crs(lat: float, lon: float):
    newCrsString = (
        "+proj=tmerc +ellps=WGS84 +datum=WGS84 +units=m +no_defs +lon_0="
        + str(lon)
        + " lat_0="
        + str(lat)
        + " +x_0=0 +y_0=0 +k_0=1"
    )
    crs2 = CRS.from_string(newCrsString)
    return crs2


def reproject_to_crs(lat: float, lon: float, crs_from, crs_to, direction="FORWARD"):
    transformer = Transformer.from_crs(crs_from, crs_to, always_xy=True)
    pt = transformer.transform(lon, lat, direction=direction)

    return pt[0], pt[1]


def getBbox(lat, lon, r):
    projected_crs = create_crs(lat, lon)
    lon_plus_1, lat_plus_1 = reproject_to_crs(1, 1, projected_crs, "EPSG:4326")
    scaleX = lon_plus_1 - lon
    scaleY = lat_plus_1 - lat

    bbox = (lat - r * scaleY, lon - r * scaleX, lat + r * scaleY, lon + r * scaleX)
    return bbox
