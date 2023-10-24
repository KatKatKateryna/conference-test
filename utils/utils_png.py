import json
import math
import os
import shutil
import tempfile
from datetime import datetime
from statistics import mean

import png
import requests

from utils.utils_other import getDegreesBboxFromLocationAndRadius


def createImageFromBbox(lat: float, lon: float, radius: float) -> str:
    """Get OSM tile image around location and save to PNG file, returns file path."""
    temp_folder = "automate_tiles_" + str(datetime.now().timestamp())[:6]
    temp_folder_path = os.path.join(os.path.abspath(tempfile.gettempdir()), temp_folder)
    folderExist = os.path.exists(temp_folder_path)
    if not folderExist:
        os.makedirs(temp_folder_path)

    min_lat_lon, max_lat_lon = getDegreesBboxFromLocationAndRadius(lat, lon, radius)

    x_px = min(2048, int(5 * radius))
    y_px = min(2048, int(5 * radius))
    png_name = f"map_{int(lat*1000000)}_{int(lon*1000000)}_{radius}.png"
    color_rows = get_colors_of_points_from_tiles(
        min_lat_lon, max_lat_lon, temp_folder_path, png_name, x_px, y_px
    )

    file_name = os.path.join(temp_folder_path, png_name)
    writePng(color_rows, file_name, x_px, y_px)
    return file_name


def writePng(color_tuples: list[list[tuple]], path: str, x_px, y_px):
    """Writes PNG file from rows with color tuples."""
    if not path.endswith(".png"):
        return
    color_list = []
    for row in color_tuples:
        colors_row = []
        for item in row:
            colors_row.extend([item[0], item[1], item[2]])
        color_list.append(tuple(colors_row))
    p = color_list
    f = open(path, "wb")
    w = png.Writer(x_px, y_px, greyscale=False)
    w.write(f, p)
    f.close()


def get_colors_of_points_from_tiles(
    min_lat_lon: tuple,
    max_lat_lon: tuple,
    temp_folder_path: str,
    png_name: str,
    x_px: int = 256,
    y_px: int = 256,
) -> list[int]:
    """Retrieves colors from OSM tiles from bbox and writes to PNG file 256x256 px."""
    # set the map zoom level and get coefficients for retrieving tile indices
    zoom = 18
    lon_extent_degrees = 180
    lat_extent_degrees = 85.0511

    # initialize rows of colors
    range_lon = [
        min_lat_lon[1] + (max_lat_lon[1] - min_lat_lon[1]) * step / x_px
        for step in range(x_px)
    ]
    range_lat = [
        min_lat_lon[0] + (max_lat_lon[0] - min_lat_lon[0]) * step / y_px
        for step in range(y_px)
    ]
    color_rows: list[list[tuple]] = [list(range(x_px)) for _ in range(y_px)]

    # degrees_in_tile_x = 2 * lon_extent_degrees / math.pow(2, zoom)
    # degrees_in_tile_y = 1 * lat_extent_degrees / math.pow(2, zoom)  # if zoom==5: 2.65

    all_tile_names = []
    all_files_data = []
    for i, lat in enumerate(range_lat):
        for k, lon in enumerate(range_lon):
            # get tiles indices
            # x = math.floor((lon + lon_extent_degrees) / degrees_in_tile_x)
            # y_remapped_value = lat_extent_degrees - lat / 90 * lat_extent_degrees
            # y = math.floor(y_remapped_value / degrees_in_tile_y)
            n = math.pow(2, zoom)
            x = n * ((lon + 180) / 360)
            y_r = math.radians(lat)
            y = n * (1 - (math.log(math.tan(y_r) + 1 / math.cos(y_r)) / math.pi)) / 2

            # download a tile if doesn't exist yet
            file_name = f"{zoom}_{int(x)}_{int(y)}"
            # print(file_name)
            if file_name not in all_tile_names:
                file_path = os.path.join(temp_folder_path, f"{file_name}.png")
                fileExists = os.path.isfile(file_path)
                if not fileExists:
                    url = f"https://tile.openstreetmap.org/{zoom}/{int(x)}/{int(y)}.png"  #'https://tile.openstreetmap.org/3/4/2.png'
                    headers = {"User-Agent": f"App: {png_name}"}
                    r = requests.get(url, headers=headers, stream=True)
                    if r.status_code == 200:
                        with open(file_path, "wb") as f:
                            r.raw.decode_content = True
                            shutil.copyfileobj(r.raw, f)
                    else:
                        raise Exception(
                            f"Request not successful: Response code {r.status_code}"
                        )
            # find pixel index in the image
            remainder_x_degrees = x % 1  # (lon + 180) % degrees_in_tile_x
            remainder_y_degrees = y % 1  # y_remapped_value % degrees_in_tile_y

            # get pixel color
            reader = png.Reader(filename=file_path)
            try:
                file_data = all_files_data[all_tile_names.index(file_name)]
            except ValueError:
                file_data = reader.read_flat()
                all_tile_names.append(file_name)
                all_files_data.append(file_data)

            w, h, pixels, metadata = file_data  # w = h = 256pixels each side
            palette = metadata["palette"]

            # get average of surrounding pixels (in case it falls on the text/symbol)
            local_colors_list = []
            offset = 1
            for offset_step_x in range((-1) * offset, offset + 1):
                coeff_x = offset_step_x  # + offset
                for offset_step_y in range((-1) * offset, offset + 1):
                    coeff_y = offset_step_y  # + offset

                    pixel_x_index = int(remainder_x_degrees * w)
                    # pixel_x_index = int(remainder_x_degrees / degrees_in_tile_x * w)
                    if 0 <= pixel_x_index + coeff_x < w:
                        pixel_x_index += coeff_x

                    pixel_y_index = int(remainder_y_degrees * w)
                    # pixel_y_index = int(remainder_y_degrees / degrees_in_tile_y * w)
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
            factor = 2
            average_color_tuple = (
                int(average_color_tuple[0] / factor) * factor,
                int(average_color_tuple[1] / factor) * factor,
                int(average_color_tuple[2] / factor) * factor,
            )
            # color = (
            #    (255 << 24)
            #    +(average_color_tuple[0] << 16)
            #    + (average_color_tuple[1] << 8)
            #    + average_color_tuple[2]
            # )
            color_rows[range_lat - i - 1][k] = average_color_tuple

    # shutil.rmtree(temp_folder_path)
    return color_rows


path = createImageFromBbox(51.50067837147388, -0.1267429761070425, 300)
print(path)
