from copy import copy

from utils.utils_pyproj import create_crs, reproject_to_crs

RESULT_BRANCH = "automate_local"
COLOR_ROAD = (255 << 24) + (30 << 16) + (30 << 8) + 30  # argb
COLOR_BLD = (255 << 24) + (230 << 16) + (230 << 8) + 230  # argb
COLOR_VISIBILITY = (255 << 24) + (255 << 16) + (10 << 8) + 10  # argb


def get_degrees_bbox_from_lat_lon_rad(
    lat: float, lon: float, radius: float
) -> list[tuple]:
    """Get min & max values of lat/lon given location and radius."""
    projected_crs = create_crs(lat, lon)
    lon_plus_1, lat_plus_1 = reproject_to_crs(1, 1, projected_crs, "EPSG:4326")
    scale_x_degrees = lon_plus_1 - lon  # degrees in 1m of longitude
    scale_y_degrees = lat_plus_1 - lat  # degrees in 1m of latitude

    min_lat_lon = (lat - scale_y_degrees * radius, lon - scale_x_degrees * radius)
    max_lat_lon = (lat + scale_y_degrees * radius, lon + scale_x_degrees * radius)

    return min_lat_lon, max_lat_lon


def clean_string(text: str) -> str:
    """Clean string from non-numeric symbols."""
    symbols = r"/[^\d.-]/g, ''"
    text_part = text
    for s in symbols:
        text_part = text_part.split(s)[0]

    new_text = ""
    for t in text_part:
        if t in "0123456789.":
            new_text += t

    return new_text


def fill_list(vals: list, lsts: list) -> list[list]:
    """Split values into separate lists by the repeated value."""
    if len(vals) > 1:
        lsts.append([])
    else:
        return lsts

    for i, v in enumerate(vals):
        if v not in lsts[len(lsts) - 1]:
            lsts[len(lsts) - 1].append(v)
        else:
            if len(lsts[len(lsts) - 1]) <= 1:
                lsts.pop(len(lsts) - 1)
            vals = copy(vals[i - 1 :])
            lsts = fill_list(vals, lsts)
    return lsts
