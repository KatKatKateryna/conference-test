import json
import math
from copy import copy
from typing import List

import requests
from shapely import (
    BufferCapStyle,
    BufferJoinStyle,
    LineString,
    Point,
    Polygon,
    buffer,
    offset_curve,
    to_geojson,
)
from specklepy.objects import Base
from specklepy.objects.geometry import Line, Mesh, Point, Polyline

# from utils.utils_network import colorSegments
from utils.utils_other import COLOR_BLD, COLOR_ROAD, cleanString, fillList
from utils.utils_pyproj import createCRS, reprojectToCrs


def getBuildings(lat: float, lon: float, r: float):
    """Get a list of 3d meshes by location lat&lon (in degrees) and radius (in meters)."""
    # https://towardsdatascience.com/loading-data-from-openstreetmap-with-python-and-the-overpass-api-513882a27fd0

    projectedCrs = createCRS(lat, lon)
    lonPlus1, latPlus1 = reprojectToCrs(1, 1, projectedCrs, "EPSG:4326")
    scaleX = lonPlus1 - lon
    scaleY = latPlus1 - lat
    # r = RADIUS #meters

    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""[out:json];
    (node["building"]({lat-r*scaleY},{lon-r*scaleX},{lat+r*scaleY},{lon+r*scaleX});
    way["building"]({lat-r*scaleY},{lon-r*scaleX},{lat+r*scaleY},{lon+r*scaleX});
    relation["building"]({lat-r*scaleY},{lon-r*scaleX},{lat+r*scaleY},{lon+r*scaleX});
    );out body;>;out skel qt;"""

    response = requests.get(overpass_url, params={"data": overpass_query})
    data = response.json()
    features = data["elements"]

    ways = []
    tags = []

    rel_outer_ways = []
    rel_outer_ways_tags = []

    ways_part = []
    nodes = []

    for feature in features:
        # ways
        if feature["type"] == "way":
            try:
                feature["id"]
                feature["nodes"]

                try:
                    tags.append(
                        {
                            "building": feature["tags"]["building"],
                            "height": feature["tags"]["height"],
                        }
                    )
                except:
                    try:
                        tags.append(
                            {
                                "building": feature["tags"]["building"],
                                "levels": feature["tags"]["building:levels"],
                            }
                        )
                    except:
                        try:
                            tags.append(
                                {
                                    "building": feature["tags"]["building"],
                                    "layer": feature["tags"]["layer"],
                                }
                            )
                        except:
                            tags.append({"building": feature["tags"]["building"]})
                ways.append({"id": feature["id"], "nodes": feature["nodes"]})
            except:
                ways_part.append({"id": feature["id"], "nodes": feature["nodes"]})

        # relations
        elif feature["type"] == "relation":
            outer_ways = []
            try:
                outer_ways_tags = {
                    "building": feature["tags"]["building"],
                    "height": feature["tags"]["height"],
                }
            except:
                try:
                    outer_ways_tags = {
                        "building": feature["tags"]["building"],
                        "levels": feature["tags"]["building:levels"],
                    }
                except:
                    try:
                        outer_ways_tags = {
                            "building": feature["tags"]["building"],
                            "layer": feature["tags"]["layer"],
                        }
                    except:
                        outer_ways_tags = {"building": feature["tags"]["building"]}

            for n, x in enumerate(feature["members"]):
                # if several Outer ways, combine them
                if (
                    feature["members"][n]["type"] == "way"
                    and feature["members"][n]["role"] == "outer"
                ):
                    outer_ways.append({"ref": feature["members"][n]["ref"]})
            rel_outer_ways.append(outer_ways)
            rel_outer_ways_tags.append(outer_ways_tags)

        # get nodes (that don't have tags)
        elif feature["type"] == "node":
            try:
                feature["tags"]
            except:
                nodes.append(
                    {"id": feature["id"], "lat": feature["lat"], "lon": feature["lon"]}
                )

    # turn relations_OUTER into ways
    for n, x in enumerate(rel_outer_ways):
        # there will be a list of "ways" in each of rel_outer_ways
        full_node_list = []
        for m, y in enumerate(rel_outer_ways[n]):
            # find ways_parts with corresponding ID
            for k, z in enumerate(ways_part):
                if k == len(ways_part):
                    break
                if rel_outer_ways[n][m]["ref"] == ways_part[k]["id"]:
                    full_node_list += ways_part[k]["nodes"]
                    ways_part.pop(k)  # remove used ways_parts
                    k -= 1  # reset index
                    break
        ways.append({"nodes": full_node_list})
        try:
            tags.append(
                {
                    "building": rel_outer_ways_tags[n]["building"],
                    "height": rel_outer_ways_tags[n]["height"],
                }
            )
        except:
            try:
                tags.append(
                    {
                        "building": rel_outer_ways_tags[n]["building"],
                        "levels": rel_outer_ways_tags[n]["levels"],
                    }
                )
            except:
                try:
                    tags.append(
                        {
                            "building": rel_outer_ways_tags[n]["building"],
                            "layer": rel_outer_ways_tags[n]["layer"],
                        }
                    )
                except:
                    tags.append({"building": rel_outer_ways_tags[n]["building"]})

        buildingsCount = len(ways)
        # print(buildingsCount)

    # get coords of Ways
    objectGroup = []
    for i, x in enumerate(ways):  # go through each Way: 2384
        ids = ways[i]["nodes"]
        coords = []  # replace node IDs with actual coords for each Way
        height = 3
        tags[i]["building"]: height = 9
        try:
            height = (
                float(cleanString(tags[i]["levels"].split(",")[0].split(";")[0])) * 3
            )
        except:
            try:
                height = float(
                    cleanString(tags[i]["height"].split(",")[0].split(";")[0])
                )
            except:
                try:
                    if (
                        float(cleanString(tags[i]["layer"].split(",")[0].split(";")[0]))
                        < 0
                    ):
                        height = -1 * height
                except:
                    pass

        for k, y in enumerate(ids):  # go through each node of the Way
            if k == len(ids) - 1:
                continue  # ignore last
            for n, z in enumerate(nodes):  # go though all nodes
                if ids[k] == nodes[n]["id"]:
                    x, y = reprojectToCrs(
                        nodes[n]["lat"], nodes[n]["lon"], "EPSG:4326", projectedCrs
                    )
                    coords.append({"x": x, "y": y})
                    break

        obj = extrudeBuildings(coords, height)
        objectGroup.append(obj)
        coords = None
        height = None
    return objectGroup


def extrudeBuildings(coords: List[dict], height: float) -> Mesh:
    vertices = []
    faces = []
    colors = []

    color = COLOR_BLD  # (255<<24) + (100<<16) + (100<<8) + 100 # argb

    # bottom
    reversed_vert_indices = list(
        range(int(len(vertices) / 3), int(len(vertices) / 3) + len(coords))
    )
    for c in coords:
        vertices.extend([c["x"], c["y"], 0])
        colors.append(color)

    polyBorder = [
        (vertices[ind * 3], vertices[ind * 3 + 1], vertices[ind * 3 + 2])
        for ind in reversed_vert_indices
    ]
    reversed_vert_indices, inverse = fix_orientation(polyBorder, reversed_vert_indices)
    faces.extend([len(coords)] + reversed_vert_indices)

    # top
    reversed_vert_indices = list(
        range(int(len(vertices) / 3), int(len(vertices) / 3) + len(coords))
    )
    for c in coords:
        vertices.extend([c["x"], c["y"], height])
        colors.append(color)

    polyBorder = [
        (vertices[ind * 3], vertices[ind * 3 + 1], vertices[ind * 3 + 2])
        for ind in reversed_vert_indices
    ]
    reversed_vert_indices, inverse = fix_orientation(polyBorder, reversed_vert_indices)
    reversed_vert_indices.reverse()
    faces.extend([len(coords)] + reversed_vert_indices)

    # sides
    for i, c in enumerate(coords):
        if i != len(coords) - 1:
            nextC = coords[i + 1]  # i+1
        else:
            nextC = coords[0]  # 0

        reversed_vert_indices = list(
            range(int(len(vertices) / 3), int(len(vertices) / 3) + 4)
        )
        faces.extend([4] + reversed_vert_indices)
        if inverse is False:
            vertices.extend(
                [
                    c["x"],
                    c["y"],
                    0,
                    c["x"],
                    c["y"],
                    height,
                    nextC["x"],
                    nextC["y"],
                    height,
                    nextC["x"],
                    nextC["y"],
                    0,
                ]
            )
        else:
            vertices.extend(
                [
                    c["x"],
                    c["y"],
                    0,
                    nextC["x"],
                    nextC["y"],
                    0,
                    nextC["x"],
                    nextC["y"],
                    height,
                    c["x"],
                    c["y"],
                    height,
                ]
            )
        colors.extend([color, color, color, color])

    obj = Mesh.create(faces=faces, vertices=vertices, colors=colors)
    obj.units = "m"
    return obj


def fix_orientation(polyBorder, reversed_vert_indices, positive=True, coef=1):
    sum_orientation = 0
    for k, ptt in enumerate(polyBorder):  # pointTupleList:
        index = k + 1
        if k == len(polyBorder) - 1:
            index = 0
        pt = polyBorder[k * coef]
        pt2 = polyBorder[index * coef]

        sum_orientation += (pt2[0] - pt[0]) * (pt2[1] + pt[1])

    inverse = False
    if sum_orientation < 0:
        reversed_vert_indices.reverse()
        inverse = True
    return reversed_vert_indices, inverse


def getRoads(lat: float, lon: float, r: float):
    # https://towardsdatascience.com/loading-data-from-openstreetmap-with-python-and-the-overpass-api-513882a27fd0

    keyword = "highway"

    projectedCrs = createCRS(lat, lon)
    lonPlus1, latPlus1 = reprojectToCrs(1, 1, projectedCrs, "EPSG:4326")
    scaleX = lonPlus1 - lon
    scaleY = latPlus1 - lat
    # r = RADIUS #meters

    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""[out:json];
    (node["{keyword}"]({lat-r*scaleY},{lon-r*scaleX},{lat+r*scaleY},{lon+r*scaleX});
    way["{keyword}"]({lat-r*scaleY},{lon-r*scaleX},{lat+r*scaleY},{lon+r*scaleX});
    relation["{keyword}"]({lat-r*scaleY},{lon-r*scaleX},{lat+r*scaleY},{lon+r*scaleX});
    );out body;>;out skel qt;"""

    response = requests.get(overpass_url, params={"data": overpass_query})
    data = response.json()
    features = data["elements"]

    ways = []
    tags = []

    rel_outer_ways = []
    rel_outer_ways_tags = []

    ways_part = []
    nodes = []

    for feature in features:
        # ways
        if feature["type"] == "way":
            try:
                feature["id"]
                feature["nodes"]

                tags.append({f"{keyword}": feature["tags"][keyword]})
                ways.append({"id": feature["id"], "nodes": feature["nodes"]})
            except:
                ways_part.append({"id": feature["id"], "nodes": feature["nodes"]})

        # relations
        elif feature["type"] == "relation":
            outer_ways = []
            try:
                outer_ways_tags = {
                    f"{keyword}": feature["tags"][keyword],
                    "area": feature["tags"]["area"],
                }
            except:
                outer_ways_tags = {f"{keyword}": feature["tags"][keyword]}

            for n, x in enumerate(feature["members"]):
                # if several Outer ways, combine them
                if (
                    feature["members"][n]["type"] == "way"
                ):  # and feature['members'][n]['role'] == 'inner':
                    outer_ways.append({"ref": feature["members"][n]["ref"]})

            rel_outer_ways.append(outer_ways)
            rel_outer_ways_tags.append(outer_ways_tags)

        # get nodes (that don't have tags)
        elif feature["type"] == "node":
            try:
                feature["tags"]
                feature["tags"][keyword]
            except:
                # if feature['tags'][keyword] != 'traffic_signals':
                nodes.append(
                    {"id": feature["id"], "lat": feature["lat"], "lon": feature["lon"]}
                )

    # turn relations_OUTER into ways
    for n, x in enumerate(rel_outer_ways):
        # there will be a list of "ways" in each of rel_outer_ways
        full_node_list = []
        for m, y in enumerate(rel_outer_ways[n]):
            # find ways_parts with corresponding ID
            for k, z in enumerate(ways_part):
                if k == len(ways_part):
                    break
                if rel_outer_ways[n][m]["ref"] == ways_part[k]["id"]:
                    full_node_list += ways_part[k]["nodes"]
                    ways_part.pop(k)  # remove used ways_parts
                    k -= 1  # reset index
                    break

            # move inside the loop to separate the sections
            ways.append({"nodes": full_node_list})
            try:
                tags.append(
                    {
                        f"{keyword}": rel_outer_ways_tags[n][keyword],
                        "area": rel_outer_ways_tags[n]["area"],
                    }
                )
            except:
                tags.append({f"{keyword}": rel_outer_ways_tags[n][keyword]})
            # empty the list after each loop to start new part
            full_node_list = []

        roadsCount = len(ways)
        # print(roadsCount)

    # get coords of Ways
    objectGroup = []
    meshGroup = []
    analysisGroup = []

    ways, tags = splitWaysByIntersection(ways, tags)

    for i, x in enumerate(ways):  # go through each Way: 2384
        ids = ways[i]["nodes"]
        coords = []  # replace node IDs with actual coords for each Way

        value = 2
        if tags[i][keyword] in ["primary"]:
            value = 12
        elif tags[i][keyword] in ["secondary"]:
            value = 7
        try:
            if tags[i]["area"] == "yes":
                value = None
                continue
        except:
            pass

        closed = False
        for k, y in enumerate(ids):  # go through each node of the Way
            if k == len(ids) - 1 and y == ids[0]:
                closed = True
                continue
            for n, z in enumerate(nodes):  # go though all nodes
                if ids[k] == nodes[n]["id"]:
                    x, y = reprojectToCrs(
                        nodes[n]["lat"], nodes[n]["lon"], "EPSG:4326", projectedCrs
                    )
                    coords.append({"x": x, "y": y})
                    break

        obj = joinRoads(coords, closed, 0)
        objectGroup.append(obj)

        objMesh = roadBuffer(obj, value)
        # filter out ignored "areas"
        if objMesh is not None:
            meshGroup.append(objMesh)

        coords = None
        height = None

    # objAnalysis, maxCount = colorSegments(lat, lon, r)
    # for ob in objAnalysis:
    #    mesh = lineColorBuffer(ob, maxCount, 2)
    #    analysisGroup.append(mesh)

    return objectGroup, meshGroup, []  # analysisGroup


def lineColorBuffer(poly: Line, maxCount: float, value: float):
    import json
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from shapely import (
        offset_curve,
        buffer,
        to_geojson,
        LineString,
        Point,
        Polygon,
        BufferCapStyle,
        BufferJoinStyle,
    )

    if value is None:
        return
    line = LineString([(p.x, p.y) for p in [poly.start, poly.end]])
    area = to_geojson(buffer(line, value, cap_style="square"))  # POLYGON to geojson
    area = json.loads(area)
    vertices = []
    colors = []
    vetricesTuples = []

    fraction = math.pow(poly.count / maxCount, 0.4)
    # cmap_names = sorted(m for m in plt.colormaps if not m.endswith("_r"))
    # cmap = mpl.cm.RdYlGn.reversed()
    cmap = mpl.colormaps["jet"]
    map = cmap(fraction)
    r = int(map[0] * 255)  # int(poly.count / maxCount)*255
    g = int(map[1] * 255)  # int(poly.count / maxCount)*255
    # if poly.count>=maxCount/2: g = 255 - int(poly.count / maxCount)*255
    b = int(map[2] * 255)  # 255 - int( poly.count / maxCount)*255

    color = (255 << 24) + (r << 16) + (g << 8) + b  # argb

    for i, c in enumerate(area["coordinates"][0]):
        if i != len(area["coordinates"][0]) - 1:
            vertices.extend(c + [0])
            vetricesTuples.append(c)
            colors.append(color)

    face_list = list(range(len(vetricesTuples)))
    face_list, inverse = fix_orientation(vetricesTuples, face_list)
    face_list.reverse()

    mesh = Mesh.create(
        vertices=vertices, colors=colors, faces=[len(vetricesTuples)] + face_list
    )
    mesh.units = "m"
    mesh.count = poly.count / maxCount

    return Base(units="m", displayValue=[mesh], width=2 * value)


def roadBuffer(poly: Polyline, value: float):
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
    face_list, inverse = fix_orientation(vetricesTuples, face_list)
    face_list.reverse()

    mesh = Mesh.create(
        vertices=vertices, colors=colors, faces=[len(vetricesTuples)] + face_list
    )
    mesh.units = "m"

    return Base(units="m", displayValue=[mesh], width=2 * value)


def splitWaysByIntersection(ways: list, tags: list):
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
            wList = fillList(ids, [])
            for item in wList:
                x = copy(w)
                x["nodes"] = item
                splitWays.append(x)
                splitTags.append(tags[i])
        else:
            splitWays.append(w)
            splitTags.append(tags[i])

    return splitWays, splitTags


def joinRoads(coords: List[dict], closed: bool, height: float):
    from specklepy.objects.geometry import Polyline, Point

    points = []

    for i, c in enumerate(coords):
        points.append(Point.from_list([c["x"], c["y"], 0]))

    poly = Polyline.from_points(points)
    poly.closed = closed
    poly.units = "m"
    return poly
