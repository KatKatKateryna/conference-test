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
        min_lat_lon, max_lat_lon, radius, temp_folder_path, png_name, x_px, y_px
    )

    file_name = os.path.join(temp_folder_path, png_name)
    writePng(color_rows, file_name, x_px, y_px)
    return file_name


def writePng(color_rows: list[list], path: str, x_px, y_px):
    """Writes PNG file from rows with color tuples."""
    if not path.endswith(".png"):
        return

    p = color_rows
    f = open(path, "wb")
    w = png.Writer(x_px, y_px, greyscale=False)
    w.write(f, p)
    f.close()


def get_colors_of_points_from_tiles(
    min_lat_lon: tuple,
    max_lat_lon: tuple,
    radius: float,
    temp_folder_path: str,
    png_name: str,
    x_px: int = 256,
    y_px: int = 256,
) -> list[int]:
    """Retrieves colors from OSM tiles from bbox and writes to PNG file 256x256 px."""
    # set the map zoom level
    zoom = 18
    zoom_max_range = 0.014
    diff_lat = max_lat_lon[0] - min_lat_lon[0]  # 0.008988129231113362 # for 500m r
    diff_lon = max_lat_lon[1] - min_lat_lon[1]  # 0.014401018774201635 # for 500m r

    if diff_lat > zoom_max_range or diff_lon > zoom_max_range:
        zoom_step = 1
        if diff_lat / zoom_max_range >= 2 or diff_lon / zoom_max_range >= 2:
            zoom_step = 2
        zoom -= zoom_step

    # initialize rows of colors
    range_lon = [
        min_lat_lon[1] + (max_lat_lon[1] - min_lat_lon[1]) * step / x_px
        for step in range(x_px)
    ]
    range_lat = [
        min_lat_lon[0] + (max_lat_lon[0] - min_lat_lon[0]) * step / y_px
        for step in range(y_px)
    ]
    color_rows: list[list] = [[] for _ in range(y_px)]

    all_tile_names = []
    all_files_data = []
    for i, lat in enumerate(range_lat):
        for k, lon in enumerate(range_lon):
            # get tiles indices
            n = math.pow(2, zoom)
            x = n * ((lon + 180) / 360)
            y_r = math.radians(lat)
            y = n * (1 - (math.log(math.tan(y_r) + 1 / math.cos(y_r)) / math.pi)) / 2

            # check if the previous iterations saved this tile
            file_name = f"{zoom}_{int(x)}_{int(y)}"
            if file_name not in all_tile_names:
                # if not, check whether the file with this name exists
                file_path = os.path.join(temp_folder_path, f"{file_name}.png")
                fileExists = os.path.isfile(file_path)
                # download a tile if doesn't exist yet
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

            color_rows[len(range_lat) - i - 1].extend(average_color_tuple)

    color_rows = add_scale_bar(color_rows, radius, x_px)

    return color_rows


def add_scale_bar(color_rows, radius, size):
    """Add a scale bar."""
    margin_coeff = 100
    pixels_per_meter = size / 2 / radius

    scale_meters = math.floor(radius / 100) * 100
    if scale_meters == 0:
        scale_meters = math.floor(radius / 10) * 10
        if scale_meters == 0:
            scale_meters = 1
    print(radius)
    print(scale_meters)
    print(size)
    print(pixels_per_meter)
    print("___")

    scale_start = size - size / margin_coeff - (scale_meters * pixels_per_meter)
    scale_end = size - size / margin_coeff
    print(3 * scale_start)
    print(3 * scale_end)
    # print(len(color_rows[0]))
    for i, _ in enumerate(range(size)):
        # stop at the necessary row for ticks
        count = 0
        if i >= (size - size / margin_coeff) - 2 and count <= 2 and i < size - 2 - 2:
            count += 1
            for k, _ in enumerate(range(3 * size)):
                # only color pixel within the scale range
                if k in list(
                    range(int(3 * scale_start), int(3 * scale_start) + 6)
                ) or k in list(range(int(3 * scale_end - 6), int(3 * scale_end))):
                    color_rows[i][k] = 0

        # stop at the necessary row for the strip
        count = 0
        if i >= (size - size / margin_coeff) and count <= 2 and i < size - 2:
            count += 1
            for k, _ in enumerate(range(3 * size)):
                # only color pixel within the scale range
                if k >= 3 * scale_start and k < 3 * scale_end:
                    color_rows[i][k] = 0

    return color_rows


# path = createImageFromBbox(51.50067837147388, -0.1267429761070425, 300)
# print(path)
