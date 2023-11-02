import math
import os
import shutil
import tempfile
from datetime import datetime
from statistics import mean

import png
import requests

from utils.utils_other import getDegreesBboxFromLocationAndRadius

margin_coeff = 100

assets_folder_path = os.path.dirname(os.path.abspath(__file__)).replace(
    "utils", "assets"
)
path_copyright = os.path.join(assets_folder_path, "copyright.PNG")
path_numbers = os.path.join(assets_folder_path, "numbers.PNG")


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


def writePng(color_rows: list[list[float]], path: str, x_px, y_px):
    """Writes PNG file from rows with color tuples."""
    if not path.endswith(".png"):
        return

    p = color_rows
    f = open(path, "wb")
    w = png.Writer(int(len(color_rows[0]) / 3), len(color_rows), greyscale=False)
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
) -> list[list[float]]:
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
                    headers = {"User-Agent": f"Speckle-Automate; Image: {png_name}"}
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

            reader = png.Reader(filename=file_path)
            try:
                file_data = all_files_data[all_tile_names.index(file_name)]
            except ValueError:
                file_data = reader.read_flat()
                all_tile_names.append(file_name)
                all_files_data.append(file_data)
            w, h, pixels, metadata = file_data  # w = h = 256pixels each side
            # print(len(pixels))
            # get pixel color
            average_color_tuple = get_image_pixel_color(
                w,
                h,
                pixels,
                metadata,
                remainder_x_degrees,
                remainder_y_degrees,
                average_px_offset=1,
                contrast_factor=2,
            )
            color_rows[len(range_lat) - i - 1].extend(average_color_tuple)

    color_rows = add_copyright_text(color_rows, width=x_px)

    pixels_per_meter = x_px / 2 / radius
    scale_meters = math.floor(radius / 200) * 100
    if scale_meters == 0:
        scale_meters = math.floor(radius / 20) * 10
        if scale_meters == 0:
            scale_meters = 1
    color_rows = add_scale_bar(color_rows, pixels_per_meter, scale_meters, x_px)
    color_rows = add_scale_text(color_rows, scale_meters, width=x_px)

    return color_rows


def get_image_pixel_color(
    sizeX,
    sizeY,
    pixels,
    metadata,
    x_ratio,
    y_ratio,
    average_px_offset=1,
    contrast_factor=2,
) -> tuple:
    """From PNG file reader data, get pixel color at x,y (normalized) position."""
    try:
        palette = metadata["palette"]
    except KeyError as ke:
        palette = None
    # get average of surrounding pixels (in case it falls on the text/symbol)
    local_colors_list = []
    for offset_step_x in range((-1) * average_px_offset, average_px_offset + 1):
        coeff_x = offset_step_x  # + offset
        for offset_step_y in range((-1) * average_px_offset, average_px_offset + 1):
            coeff_y = offset_step_y  # + offset

            pixel_x_index = math.floor(x_ratio * sizeX)
            if 0 <= pixel_x_index + coeff_x < sizeX:
                pixel_x_index += coeff_x

            pixel_y_index = math.floor(y_ratio * sizeY)
            if 0 <= pixel_y_index + coeff_y < sizeY:
                pixel_y_index += coeff_y

            pixel_index = pixel_y_index * sizeX + pixel_x_index
            if palette is not None:
                color_tuple = palette[pixels[pixel_index]]
            elif metadata["alpha"] is True:
                color_tuple = (
                    pixels[pixel_index * 4],
                    pixels[pixel_index * 4 + 1],
                    pixels[pixel_index * 4 + 2],
                )
            else:
                color_tuple = (
                    pixels[pixel_index * 3],
                    pixels[pixel_index * 3 + 1],
                    pixels[pixel_index * 3 + 2],
                )
            local_colors_list.append(color_tuple)

    average_color_tuple = (
        int(mean([c[0] for c in local_colors_list])),
        int(mean([c[1] for c in local_colors_list])),
        int(mean([c[2] for c in local_colors_list])),
    )
    # increase contrast
    contrast_factor = 2
    average_color_tuple = (
        int(average_color_tuple[0] / contrast_factor) * contrast_factor,
        int(average_color_tuple[1] / contrast_factor) * contrast_factor,
        int(average_color_tuple[2] / contrast_factor) * contrast_factor,
    )
    return average_color_tuple


def add_scale_bar(
    color_rows, pixels_per_meter, scale_meters, size
) -> list[list[float]]:
    """Add a scale bar."""
    line_width = int(size / margin_coeff / 5)
    line_width = max(2, line_width)

    scale_start = int(size / margin_coeff)
    scale_end = int(size / margin_coeff + scale_meters * pixels_per_meter)

    tick_height = 2 * size / margin_coeff
    tick_height = max(tick_height, 4)
    rows = len(color_rows)

    for i, _ in enumerate(range(rows)):
        # stop at the necessary row for ticks
        count = 0
        if (
            i >= (rows - min(2, size / margin_coeff) - line_width - tick_height)
            and i < rows - min(2, size / margin_coeff) - line_width
            and count <= line_width
        ):
            count += 1
            for k, _ in enumerate(range(3 * size)):
                # only color pixel within the scale range
                if k in list(
                    range(int(3 * scale_start), int(3 * scale_start + line_width))
                ) or k in list(
                    range(int(3 * (scale_end - line_width)), int(3 * scale_end))
                ):
                    color_rows[i][k] = 0

        # stop at the necessary row for the strip
        count = 0
        if (
            i >= rows - min(2, size / margin_coeff) - line_width
            and i < rows - min(2, size / margin_coeff)
            and count <= line_width
        ):
            count += 1
            for k, _ in enumerate(range(3 * size)):
                # only color pixel within the scale range
                if k >= 3 * scale_start and k < 3 * scale_end:
                    color_rows[i][k] = 0

    return color_rows


def add_scale_text(
    color_rows: list[float], scale: int, width: float
) -> list[list[float]]:
    """Add text (e.g. '100 m') to the scale bar."""
    fileExists = os.path.isfile(path_numbers)
    if not fileExists:
        raise Exception("Number file not found")

    reader = png.Reader(filename=path_numbers)
    file_data = reader.read_flat()
    w, h, pixels, metadata = file_data  # w = h = 256pixels each side

    text = str(int(scale)) + "m"
    size = 25

    new_size = int(3 * width / margin_coeff)
    new_size = min(new_size, 25)
    new_size = max(new_size, 12)
    size_coeff = new_size / size

    new_h = int(h * size_coeff)
    new_w = int(w * size_coeff)
    rows = len(color_rows)
    start_row = width  # int(rows - 2 * rows / margin_coeff - new_h)
    start_ind = int(3 * 2 * width / margin_coeff)

    for r in range(new_h):
        x_remainder = 0  # start a count
        char_index = 0
        for c in range(new_w):
            # at each X, check which number to add
            if round(x_remainder, 2) == round(size * size_coeff, 2):
                x_remainder = 0  # restart for each char
                char_index += 1

            if char_index >= len(text):
                continue

            # find the data from that number
            for char in "0123456789m":
                if char == text[char_index]:
                    try:
                        index = int(char)
                    except:
                        index = 10
            x_ratio = (index * size * size_coeff + x_remainder) / new_w
            # get pixel color
            color_tuple = get_image_pixel_color(
                w,
                h,
                pixels,
                metadata,
                x_ratio,
                r / new_h,
                average_px_offset=0,
                contrast_factor=1,
            )
            x_remainder += 1 * size_coeff
            row_index = start_row + r
            column_index = start_ind + int(
                3 * (size * char_index * size_coeff + x_remainder)
            )
            # only overwrite nearly black pixels
            if all([255 - color_tuple[k] > 50 for k in range(3)]):
                color_rows[row_index][column_index] = max(color_tuple)
                color_rows[row_index][column_index + 1] = max(color_tuple)
                color_rows[row_index][column_index + 2] = max(color_tuple)
        # color_rows.append(new_color_row)

    return color_rows


def add_copyright_text(color_rows: list[float], width: float) -> list[list[float]]:
    """Add copyright notice."""
    fileExists = os.path.isfile(path_copyright)
    if not fileExists:
        raise Exception("Copyright file not found")

    reader = png.Reader(filename=path_copyright)
    file_data = reader.read_flat()
    w, h, pixels, metadata = file_data  # w = h = 256pixels each side

    size = 25

    new_size = int(4 * width / margin_coeff)
    new_size = min(new_size, 30)
    new_size = max(new_size, 15)
    size_coeff = new_size / size

    new_h = int(h * size_coeff)
    start_ind = int(width - width / margin_coeff - w * size_coeff)

    for r in range(new_h):
        new_row = []
        for c in range(width):
            if c >= start_ind and c < start_ind + w * size_coeff:
                # get pixel color
                color_tuple = get_image_pixel_color(
                    w,
                    h,
                    pixels,
                    metadata,
                    (c - start_ind) / size_coeff / w,
                    r / new_h,
                    average_px_offset=0,
                    contrast_factor=1,
                )
                new_row.extend(color_tuple)
            else:
                new_row.extend([255, 255, 255])

        color_rows.append(new_row)

    return color_rows
