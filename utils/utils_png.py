import json
import math
import os
import shutil
import tempfile
from datetime import datetime
from statistics import mean

import png
import requests

from utils.utils_general import getDegreesBboxFromLocationAndRadius


def createImageFromBbox(
    lat: float, lon: float, radius: float, png_name: str = "map_256x256"
) -> str:
    """Get OSM tile image around location and save to PNG file, returns file path."""
    temp_folder = "automate_tiles" + str(datetime.now().timestamp())[:4]
    temp_folder_path = os.path.join(os.path.abspath(tempfile.gettempdir()), temp_folder)
    folderExist = os.path.exists(temp_folder_path)
    if not folderExist:
        os.makedirs(temp_folder_path)

    min_lon_lat, max_lon_lat = getDegreesBboxFromLocationAndRadius(lat, lon, radius)
    color_rows = get_colors_of_points_from_tiles(
        min_lon_lat, max_lon_lat, temp_folder_path, png_name, 256, 256
    )

    file_name = os.path.join(temp_folder_path, png_name)
    writePng(color_rows, file_name)
    return file_name


def writePng(color_tuples: list[list[tuple]], path: str):
    """Writes PNG file from rows with color tuples."""
    if not path.endswith(".png"):
        return
    color_list = []
    for row in color_tuples:
        colors_row = []
        for item in row:
            colors_row.extend([item[0], item[1]])
        color_list.append(tuple(colors_row))
    p = color_list
    f = open(path, "wb")
    width_px = 256
    height_px = 256
    w = png.Writer(width_px, height_px, greyscale=False)
    w.write(f, p)
    f.close()


def get_colors_of_points_from_tiles(
    min_lon_lat: tuple,
    max_lon_lat: tuple,
    temp_folder_path: str,
    png_name: str,
    x_px: int = 256,
    y_px: int = 256,
) -> list[int]:
    """Retrieves colors from OSM tiles from bbox and writes to PNG file 256x256 px."""
    # set the map zoom level and get coefficients for retrieving tile indices
    zoom = 18
    lat_extent_degrees = 85.0511
    degrees_in_tile_x = 360 / math.pow(2, zoom)
    degrees_in_tile_y = 2 * lat_extent_degrees / math.pow(2, zoom)

    # initialize rows of colors
    range_lon = [
        min_lon_lat[0] + step / ((max_lon_lat[0] - min_lon_lat[0]) / x_px)
        for step in range(x_px)
    ]
    range_lat = [
        min_lon_lat[0] + step / ((max_lon_lat[1] - min_lon_lat[1]) / y_px)
        for step in range(y_px)
    ]
    color_rows: list[list[tuple]] = [list(range(x_px)) for _ in range(y_px)]

    for i, lat in enumerate(range_lat):
        for k, lon in enumerate(range_lon):
            # get tiles indices
            x = int((lon + 180) / degrees_in_tile_x)
            y_remapped_value = lat_extent_degrees - lat / 180 * lat_extent_degrees
            y = int(y_remapped_value / degrees_in_tile_y)

            # download a tile if doesn't exist yet
            file_name = f"{zoom}_{x}_{y}"
            file_path = os.path.join(temp_folder_path, f"{file_name}.png")
            fileExists = os.path.isfile(file_path)
            if not fileExists:
                url = f"https://tile.openstreetmap.org/{zoom}/{int(x)}/{int(y)}.png"  #'https://tile.openstreetmap.org/3/4/2.png'
                headers = {"User-Agent": "Some app in testing process"}
                r = requests.get(url, headers=headers, stream=True)
                if r.status_code == 200:
                    with open(file_path, "wb") as f:
                        r.raw.decode_content = True
                        shutil.copyfileobj(r.raw, f)

            # find pixel index in the image
            remainder_x_degrees = (lon + 180) % degrees_in_tile_x
            remainder_y_degrees = y_remapped_value % degrees_in_tile_y

            # get pixel color
            reader = png.Reader(filename=file_path)
            w, h, pixels, metadata = reader.read_flat()  # w = h = 256pixels each side
            palette = metadata["palette"]

            # get average of surrounding pixels (in case it falls on the text/symbol)
            local_colors_list = []
            offset = 3
            for offset_step_x in range((-1) * offset, offset + 1):
                coeff_x = offset_step_x + offset
                for offset_step_y in range((-1) * offset, offset + 1):
                    coeff_y = offset_step_y + offset

                    pixel_x_index = int(remainder_x_degrees / degrees_in_tile_x * w)
                    if 0 <= pixel_x_index + coeff_x < w:
                        pixel_x_index += coeff_x

                    pixel_y_index = int(remainder_y_degrees / degrees_in_tile_y * w)
                    if 0 <= pixel_y_index + coeff_y < w:
                        pixel_y_index += coeff_y

                    pixel_index = pixel_y_index * w + pixel_x_index
                    color_tuple = palette[pixels[pixel_index]]
                    local_colors_list.append(color_tuple)

            average_color_tuple = (
                int(mean([c[0] for c in local_colors_list])),
                int(mean([c[1] for c in local_colors_list])),
                int(mean([c[2] for c in local_colors_list])),
            )
            # increase contrast
            factor = 5
            average_color_tuple = (
                int(average_color_tuple[0] / factor / 2.5) * factor,
                int(average_color_tuple[1] / factor / 2.5) * factor,
                int(average_color_tuple[2] / factor / 2.5) * factor,
            )
            color = (
                # (255 << 24)
                +(average_color_tuple[0] << 16)
                + (average_color_tuple[1] << 8)
                + average_color_tuple[2]
            )
            color_rows[i][k] = color

    # shutil.rmtree(temp_folder_path)
    return color_rows
