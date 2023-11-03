import json
import math
from copy import copy

import geopandas as gpd
import numpy as np
from geovoronoi import voronoi_regions_from_coords
from shapely import (
    LineString,
    Polygon,
    buffer,
    to_geojson,
)
from shapely.ops import triangulate
from specklepy.objects import Base
from specklepy.objects.geometry import Mesh, Point, Polyline

from utils.utils_other import (
    COLOR_BLD,
    COLOR_ROAD,
    fill_list,
)


def fix_orientation(
    point_tuple_list: list,
    vert_indices: list,
    make_counter_clockwise: bool = True,
    coef: int = 1,
) -> tuple[list, bool]:
    """Check the polygon face orientation and reverse if needed."""
    sum_orientation = 0
    for k, _ in enumerate(point_tuple_list):  # pointTupleList:
        index = k + 1
        if k == len(point_tuple_list) - 1:
            index = 0
        pt = point_tuple_list[k * coef]
        pt2 = point_tuple_list[index * coef]

        sum_orientation += (pt2[0] - pt[0]) * (pt2[1] + pt[1])

    if sum_orientation > 0:
        original_clockwise_orientation = True  # facing down originally
    else:
        original_clockwise_orientation = False  # facing up originally
        # if needs to be facing down, reverse the vertex order
        if make_counter_clockwise:
            vert_indices.reverse()

    return vert_indices, original_clockwise_orientation


def create_side_face(
    coords, i, next_coord_index, height, clockwise_orientation
) -> list[float]:
    """Constructing a vertical Mesh face assuming counter-clockwise orientation of the base polygon."""
    if clockwise_orientation is False:
        side_vertices = [
            coords[i]["x"],
            coords[i]["y"],
            0,
            next_coord_index["x"],
            next_coord_index["y"],
            0,
            next_coord_index["x"],
            next_coord_index["y"],
            height,
            coords[i]["x"],
            coords[i]["y"],
            height,
        ]
    else:  # if clockwise orientation
        side_vertices = [
            coords[i]["x"],
            coords[i]["y"],
            0,
            coords[i]["x"],
            coords[i]["y"],
            height,
            next_coord_index["x"],
            next_coord_index["y"],
            height,
            next_coord_index["x"],
            next_coord_index["y"],
            0,
        ]

    return side_vertices


def to_triangles(
    coords: list[dict], coords_inner: list[dict], attempt: int = 0
) -> tuple[dict, int]:
    """Generate triangular faces from the Polygon with voids."""
    # https://gis.stackexchange.com/questions/316697/delaunay-triangulation-algorithm-in-shapely-producing-erratic-result
    try:
        # round vertices precision
        digits = 3 - attempt

        vert = []
        vert_rounded = []
        # round boundary precision:
        for i, v in enumerate(coords):
            if i == len(coords) - 1:
                vert.append((v["x"], v["y"]))
                break  # don't test last point
            rounded = [round(v["x"], digits), round(v["y"], digits)]
            if v not in vert and rounded not in vert_rounded:
                vert.append((v["x"], v["y"]))
                vert_rounded.append(rounded)
        # round courtyards precision:
        holes = []
        holes_rounded = []
        for k, h in enumerate(coords_inner):
            hole = []
            for i, v in enumerate(h):
                if i == len(h) - 1:
                    hole.append((v["x"], v["y"]))
                    break  # don't test last point

                # test if any previour vertext with similar rounded value
                # has been added before, then ignore
                rounded = [round(v["x"], digits), round(v["y"], digits)]
                if v not in holes and rounded not in holes_rounded:
                    hole.append((v["x"], v["y"]))
                    holes_rounded.append(rounded)
            holes.append(hole)

        # check if sufficient holes vertices were added
        if len(holes) == 1 and len(holes[0]) == 0:
            polygon = Polygon([(v[0], v[1]) for v in vert])
        else:
            polygon = Polygon([(v[0], v[1]) for v in vert], holes)

        exterior_linearring = polygon.exterior
        poly_points = np.array(exterior_linearring.coords).tolist()

        try:
            polygon.interiors[0]
        except:
            poly_points = poly_points
        else:
            for i, interior_linearring in enumerate(polygon.interiors):
                a = interior_linearring.coords
                poly_points += np.array(a).tolist()

        poly_points = np.array(
            [item for sublist in poly_points for item in sublist]
        ).reshape(-1, 2)

        poly_shapes, _ = voronoi_regions_from_coords(
            poly_points, polygon.buffer(0.000001)
        )
        gdf_poly_voronoi = (
            gpd.GeoDataFrame({"geometry": poly_shapes})
            .explode(index_parts=True)
            .reset_index()
        )

        tri_geom = []
        for geom in gdf_poly_voronoi.geometry:
            inside_triangles = [
                tri for tri in triangulate(geom) if tri.centroid.within(polygon)
            ]
            tri_geom += inside_triangles

        vertices = []
        triangles = []
        for tri in tri_geom:
            xx, yy = tri.exterior.coords.xy
            v_list = zip(xx.tolist(), yy.tolist())

            tr_indices = []
            count = 0
            for vt in v_list:
                v = list(vt)
                if count == 3:
                    continue
                if v not in vertices:
                    vertices.append(v)
                    tr_indices.append(len(vertices) - 1)
                else:
                    tr_indices.append(vertices.index(v))
                count += 1
            triangles.append(tr_indices)

        shape = {"vertices": vertices, "triangles": triangles}
        return shape, attempt
    except Exception as e:
        print(f"Meshing iteration {attempt} failed: {e}")
        attempt += 1
        if attempt <= 3:
            return to_triangles(coords, coords_inner, attempt)
        else:
            return None, None


def rotate_pt(coord: dict, angle: float) -> dict:
    """Rotate a point around (0,0,1) axis."""
    x = coord["x"]
    y = coord["y"]
    x2 = x * math.cos(angle) + y * math.sin(angle)
    y2 = -x * math.sin(angle) + y * math.cos(angle)

    return {"x": x2, "y": y2}


def extrude_building(
    coords: list[dict], coords_inner: list[list[dict]], height: float
) -> Mesh:
    """Create a 3d Mesh from the lists of outer and inner coords and height."""
    vertices = []
    faces = []
    colors = []

    color = COLOR_BLD  # (255<<24) + (100<<16) + (100<<8) + 100 # argb

    if len(coords) < 3:
        return None
    # if the building has single outline
    if len(coords_inner) == 0:
        # bottom
        bottom_vert_indices = list(range(len(coords)))
        bottom_vertices = [[c["x"], c["y"]] for c in coords]
        bottom_vert_indices, clockwise_orientation = fix_orientation(
            bottom_vertices, bottom_vert_indices
        )
        for c in coords:
            vertices.extend([c["x"], c["y"], 0])
            colors.append(color)
        faces.extend([len(coords)] + bottom_vert_indices)

        # top
        top_vert_indices = list(range(len(coords), 2 * len(coords)))
        for c in coords:
            vertices.extend([c["x"], c["y"], height])
            colors.append(color)

        if clockwise_orientation is True:  # if facing down originally
            top_vert_indices.reverse()
        faces.extend([len(coords)] + top_vert_indices)

        # sides
        total_vertices = len(colors)
        for i, c in enumerate(coords):
            if i != len(coords) - 1:
                next_coord_index = coords[i + 1]
            else:
                next_coord_index = coords[0]  # 0

            side_vert_indices = list(range(total_vertices, total_vertices + 4))
            faces.extend([4] + side_vert_indices)
            side_vertices = create_side_face(
                coords, i, next_coord_index, height, clockwise_orientation
            )
            # if clockwise_orientation is True:  # if facing down originally
            #    side_vertices.reverse()

            vertices.extend(side_vertices)
            colors.extend([color, color, color, color])
            total_vertices += 4

    else:  # if outline contains holes and mesh needs to be constructed
        # bottom
        try:
            total_vertices = 0
            triangulated_geom, _ = to_triangles(coords, coords_inner)
        except Exception as e:  # default to only outer border mesh generation
            print(f"Mesh creation failed: {e}")
            return extrude_building(coords, [], height)

        if triangulated_geom is None:  # default to only outer border mesh generation
            return extrude_building(coords, [], height)

        pt_list = [[p[0], p[1], 0] for p in triangulated_geom["vertices"]]
        triangle_list = [trg for trg in triangulated_geom["triangles"]]

        for trg in triangle_list:
            a = trg[0]
            b = trg[1]
            c = trg[2]
            vertices.extend(pt_list[a] + pt_list[b] + pt_list[c])
            colors.extend([color, color, color])
            total_vertices += 3

            # all faces are counter-clockwise now (facing up)
            # therefore, add vertices in the reverse (clockwise) order (facing down)
            faces.extend(
                [3, total_vertices - 1, total_vertices - 2, total_vertices - 3]
            )

        # top
        pt_list = [[p[0], p[1], height] for p in triangulated_geom["vertices"]]

        for trg in triangle_list:
            a = trg[0]
            b = trg[1]
            c = trg[2]
            # all faces are counter-clockwise now (facing up)
            vertices.extend(pt_list[a] + pt_list[b] + pt_list[c])
            colors.extend([color, color, color])
            total_vertices += 3
            faces.extend(
                [3, total_vertices - 3, total_vertices - 2, total_vertices - 1]
            )

        # sides
        bottom_vert_indices = list(range(len(coords)))
        bottom_vertices = [[c["x"], c["y"]] for c in coords]
        bottom_vert_indices, clockwise_orientation = fix_orientation(
            bottom_vertices, bottom_vert_indices
        )
        for i, c in enumerate(coords):
            if i != len(coords) - 1:
                next_coord_index = coords[i + 1]
            else:
                next_coord_index = coords[0]  # 0

            side_vert_indices = list(range(total_vertices, total_vertices + 4))
            faces.extend([4] + side_vert_indices)
            side_vertices = create_side_face(
                coords, i, next_coord_index, height, clockwise_orientation
            )

            vertices.extend(side_vertices)
            colors.extend([color, color, color, color])
            total_vertices += 4

        # voids sides
        for _, local_coords_inner in enumerate(coords_inner):
            bottom_void_vert_indices = list(range(len(local_coords_inner)))
            bottom_void_vertices = [[c["x"], c["y"]] for c in local_coords_inner]
            bottom_void_vert_indices, clockwise_orientation_void = fix_orientation(
                bottom_void_vertices, bottom_void_vert_indices
            )

            for i, c in enumerate(local_coords_inner):
                if i != len(local_coords_inner) - 1:
                    next_coord_index = local_coords_inner[i + 1]
                else:
                    next_coord_index = local_coords_inner[0]  # 0

                side_vert_indices = list(range(total_vertices, total_vertices + 4))
                faces.extend([4] + side_vert_indices)
                side_vertices = create_side_face(
                    local_coords_inner,
                    i,
                    next_coord_index,
                    height,
                    clockwise_orientation_void,
                )
                vertices.extend(side_vertices)
                colors.extend([color, color, color, color])
                total_vertices += 4

    obj = Mesh.create(faces=faces, vertices=vertices, colors=colors)
    obj.units = "m"

    return obj


def road_buffer(poly: Polyline, value: float) -> Base:
    """Creage a Mesh from Polyline and buffer value."""
    if value is None:
        return
    line = LineString([(p.x, p.y) for p in poly.as_points()])
    area = to_geojson(buffer(line, value, cap_style="square"))  # POLYGON to geojson
    area = json.loads(area)
    vertices = []
    colors = []
    vetricesTuples = []

    color = COLOR_ROAD  # (255<<24) + (150<<16) + (150<<8) + 150 # argb

    for i, c in enumerate(area["coordinates"][0]):
        if i != len(area["coordinates"][0]) - 1:
            vertices.extend(c + [0])
            vetricesTuples.append(c)
            colors.append(color)

    face_list = list(range(len(vetricesTuples)))
    face_list, _ = fix_orientation(vetricesTuples, face_list)
    face_list.reverse()

    mesh = Mesh.create(
        vertices=vertices, colors=colors, faces=[len(vetricesTuples)] + face_list
    )
    mesh.units = "m"

    return Base(
        units="m",
        displayValue=[mesh],
        width=2 * value,
        source_data="© OpenStreetMap",
        source_url="https://www.openstreetmap.org/",
    )


def split_ways_by_intersection(ways: list[dict], tags: list[dict]) -> tuple[list[dict]]:
    """Separate ways and tags into different lists if they self-intersect."""
    splitWays = []
    splitTags = []

    for i, w in enumerate(ways):
        ids = w["nodes"]

        try:
            if tags[i]["area"] == "yes":
                splitWays.append(w)
                splitTags.append(tags[i])
                continue
        except:
            pass

        if len(list(set(ids))) < len(ids):  # if there are repetitions
            wList = fill_list(ids, [])
            for item in wList:
                x = copy(w)
                x["nodes"] = item
                splitWays.append(x)
                splitTags.append(tags[i])
        else:
            splitWays.append(w)
            splitTags.append(tags[i])

    return splitWays, splitTags


def join_roads(coords: list[dict], closed: bool, height: float) -> Polyline:
    """Create a Polyline from a list of coordinates."""
    points = []

    for c in coords:
        points.append(Point.from_list([c["x"], c["y"], 0]))

    poly = Polyline.from_points(points)
    poly.closed = closed
    poly.units = "m"

    return poly
