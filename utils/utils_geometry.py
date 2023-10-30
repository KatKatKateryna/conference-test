import geopandas as gpd
import numpy as np
from geovoronoi import voronoi_regions_from_coords
from shapely.geometry import Polygon
from shapely.ops import triangulate


def fix_orientation(polyBorder, reversed_vert_indices, positive=True, coef=1):
    sum_orientation = 0
    for k, ptt in enumerate(polyBorder):  # pointTupleList:
        index = k + 1
        if k == len(polyBorder) - 1:
            index = 0
        pt = polyBorder[k * coef]
        pt2 = polyBorder[index * coef]

        sum_orientation += (pt2[0] - pt[0]) * (pt2[1] + pt[1])

    clockwise_orientation = True
    if sum_orientation < 0:
        reversed_vert_indices.reverse()
        clockwise_orientation = False
    return reversed_vert_indices, clockwise_orientation


def create_side_face(coords, i, next_coord_index, height) -> list[float]:
    """Constructing a vertical Mesh face assuming counter-clockwise orientation of the base polygon."""
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
    return side_vertices


def to_triangles(coords: list[dict], coords_inner: list[dict], attempt=0):
    # https://gis.stackexchange.com/questions/316697/delaunay-triangulation-algorithm-in-shapely-producing-erratic-result
    try:
        # round vertices precision
        digits = 3 - attempt

        vert = []
        vert_rounded = []
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

        poly_shapes, pts = voronoi_regions_from_coords(
            poly_points, polygon.buffer(0.000001)
        )
        gdf_poly_voronoi = (
            gpd.GeoDataFrame({"geometry": poly_shapes}).explode().reset_index()
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
        print(e)
        attempt += 1
        if attempt <= 3:
            return to_triangles(coords, coords_inner, attempt)
        else:
            return None, None
