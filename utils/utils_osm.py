import requests
from specklepy.objects.geometry import Mesh

from utils.utils_geometry import (
    extrude_building,
    join_roads,
    road_buffer,
    rotate_pt,
    split_ways_by_intersection,
)
from utils.utils_other import (
    clean_string,
    get_degrees_bbox_from_lat_lon_rad,
)
from utils.utils_pyproj import create_crs, reproject_to_crs


def get_features_from_osm_server(
    keyword: str, min_lat_lon: tuple[float], max_lat_lon: tuple[float]
) -> list[dict]:
    """Get OSM features via Overpass API."""
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""[out:json];
    (node["{keyword}"]({min_lat_lon[0]},{min_lat_lon[1]},{max_lat_lon[0]},{max_lat_lon[1]});
    way["{keyword}"]({min_lat_lon[0]},{min_lat_lon[1]},{max_lat_lon[0]},{max_lat_lon[1]});
    relation["{keyword}"]({min_lat_lon[0]},{min_lat_lon[1]},{max_lat_lon[0]},{max_lat_lon[1]});
    );out body;>;out skel qt;"""

    response = requests.get(overpass_url, params={"data": overpass_query})
    data = response.json()
    features = data["elements"]

    return features


def get_buildings(lat: float, lon: float, r: float, angle_rad: float) -> list[Mesh]:
    """Get a list of 3d Meshes of buildings by lat&lon (degrees) and radius (meters)."""
    # https://towardsdatascience.com/loading-data-from-openstreetmap-with-python-and-the-overpass-api-513882a27fd0

    keyword = "building"
    min_lat_lon, max_lat_lon = get_degrees_bbox_from_lat_lon_rad(lat, lon, r)
    features = get_features_from_osm_server(keyword, min_lat_lon, max_lat_lon)

    ways = []
    tags = []
    rel_outer_ways = []
    rel_outer_ways_tags = []
    rel_inner_ways = []
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
                            f"{keyword}": feature["tags"][keyword],
                            "height": feature["tags"]["height"],
                        }
                    )
                except:
                    try:
                        tags.append(
                            {
                                f"{keyword}": feature["tags"][keyword],
                                "levels": feature["tags"]["building:levels"],
                            }
                        )
                    except:
                        try:
                            tags.append(
                                {
                                    f"{keyword}": feature["tags"][keyword],
                                    "layer": feature["tags"]["layer"],
                                }
                            )
                        except:
                            tags.append({f"{keyword}": feature["tags"][keyword]})
                ways.append(
                    {
                        "nodes": feature["nodes"],
                        "inner_nodes": [],
                    }  # "id": feature["id"],
                )
            except:
                ways_part.append({"id": feature["id"], "nodes": feature["nodes"]})

        # relations
        elif feature["type"] == "relation":
            outer_ways = []
            inner_ways = []
            try:
                outer_ways_tags = {
                    f"{keyword}": feature["tags"][keyword],
                    "height": feature["tags"]["height"],
                }
            except:
                try:
                    outer_ways_tags = {
                        f"{keyword}": feature["tags"][keyword],
                        "levels": feature["tags"]["building:levels"],
                    }
                except:
                    try:
                        outer_ways_tags = {
                            f"{keyword}": feature["tags"][keyword],
                            "layer": feature["tags"]["layer"],
                        }
                    except:
                        outer_ways_tags = {f"{keyword}": feature["tags"][keyword]}

            for n, x in enumerate(feature["members"]):
                # if several Outer ways, combine them
                if (
                    feature["members"][n]["type"] == "way"
                    and feature["members"][n]["role"] == "outer"
                ):
                    outer_ways.append({"ref": feature["members"][n]["ref"]})
                elif (
                    feature["members"][n]["type"] == "way"
                    and feature["members"][n]["role"] == "inner"
                ):
                    inner_ways.append({"ref": feature["members"][n]["ref"]})
            rel_outer_ways.append(outer_ways)
            rel_outer_ways_tags.append(outer_ways_tags)
            rel_inner_ways.append(inner_ways)

        # get nodes (that don't have tags)
        elif feature["type"] == "node":
            try:
                feature["tags"]
            except:
                nodes.append(
                    {"id": feature["id"], "lat": feature["lat"], "lon": feature["lon"]}
                )

    # turn relations_OUTER into ways
    for n, x in enumerate(rel_outer_ways):  # just 1
        # there will be a list of "ways" in each of rel_outer_ways
        full_node_list = []
        full_node_inner_list = []
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
        for m, y in enumerate(rel_inner_ways[n]):
            # find ways_parts with corresponding ID
            local_node_list = []
            for k, z in enumerate(ways_part):
                if k == len(ways_part):
                    break
                if rel_inner_ways[n][m]["ref"] == ways_part[k]["id"]:
                    local_node_list += ways_part[k]["nodes"]
                    ways_part.pop(k)  # remove used ways_parts
                    k -= 1  # reset index
                    break
            full_node_inner_list.append(local_node_list)

        ways.append({"nodes": full_node_list, "inner_nodes": full_node_inner_list})
        try:
            tags.append(
                {
                    f"{keyword}": rel_outer_ways_tags[n][keyword],
                    "height": rel_outer_ways_tags[n]["height"],
                }
            )
        except:
            try:
                tags.append(
                    {
                        f"{keyword}": rel_outer_ways_tags[n][keyword],
                        "levels": rel_outer_ways_tags[n]["levels"],
                    }
                )
            except:
                try:
                    tags.append(
                        {
                            f"{keyword}": rel_outer_ways_tags[n][keyword],
                            "layer": rel_outer_ways_tags[n]["layer"],
                        }
                    )
                except:
                    tags.append({f"{keyword}": rel_outer_ways_tags[n][keyword]})

    projected_crs = create_crs(lat, lon)

    # get coords of Ways
    objectGroup = []
    for i, x in enumerate(ways):
        ids = ways[i]
        coords = []  # replace node IDs with actual coords for each Way
        coords_inner = []
        height = 9
        try:
            height = (
                float(clean_string(tags[i]["levels"].split(",")[0].split(";")[0])) * 3
            )
        except:
            try:
                height = float(
                    clean_string(tags[i]["height"].split(",")[0].split(";")[0])
                )
            except:
                try:
                    if (
                        float(
                            clean_string(tags[i]["layer"].split(",")[0].split(";")[0])
                        )
                        < 0
                    ):
                        height *= -1
                except:
                    pass

        # go through each external node of the Way
        for k, y in enumerate(ids["nodes"]):
            if k == len(ids["nodes"]) - 1:
                continue  # ignore last
            for n, z in enumerate(nodes):  # go though all nodes
                if ids["nodes"][k] == nodes[n]["id"]:
                    x, y = reproject_to_crs(
                        nodes[n]["lat"], nodes[n]["lon"], "EPSG:4326", projected_crs
                    )
                    coords.append({"x": x, "y": y})
                    break

        # go through each internal node of the Way
        for l, void_nodes in enumerate(ids["inner_nodes"]):
            coords_per_void = []
            for k, y in enumerate(void_nodes):
                if k == len(ids["inner_nodes"][l]) - 1:
                    continue  # ignore last
                for n, z in enumerate(nodes):  # go though all nodes
                    if ids["inner_nodes"][l][k] == nodes[n]["id"]:
                        x, y = reproject_to_crs(
                            nodes[n]["lat"], nodes[n]["lon"], "EPSG:4326", projected_crs
                        )
                        coords_per_void.append({"x": x, "y": y})
                        break
            coords_inner.append(coords_per_void)

        if angle_rad == 0:
            obj = extrude_building(coords, coords_inner, height)
        else:
            rotated_coords = [rotate_pt(c, angle_rad) for c in coords]
            rotated_coords_inner = [
                [rotate_pt(c_void, angle_rad) for c_void in c] for c in coords_inner
            ]
            obj = extrude_building(rotated_coords, rotated_coords_inner, height)
        if obj is not None:
            objectGroup.append((obj, tags[i]["building"]))
        coords = None
        height = None
    return objectGroup


def get_roads(lat: float, lon: float, r: float, angle_rad: float) -> tuple[list]:
    """Get a list of Polylines and Meshes of roads by lat&lon (degrees) and radius (meters)."""
    keyword = "highway"
    min_lat_lon, max_lat_lon = get_degrees_bbox_from_lat_lon_rad(lat, lon, r)
    features = get_features_from_osm_server(keyword, min_lat_lon, max_lat_lon)

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
                if feature["members"][n]["type"] == "way":
                    outer_ways.append({"ref": feature["members"][n]["ref"]})

            rel_outer_ways.append(outer_ways)
            rel_outer_ways_tags.append(outer_ways_tags)

        # get nodes (that don't have tags)
        elif feature["type"] == "node":
            try:
                feature["tags"]
                feature["tags"][keyword]
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

    projected_crs = create_crs(lat, lon)

    # get coords of Ways
    objectGroup = []
    meshGroup = []

    ways, tags = split_ways_by_intersection(ways, tags)

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
                    x, y = reproject_to_crs(
                        nodes[n]["lat"], nodes[n]["lon"], "EPSG:4326", projected_crs
                    )
                    coords.append({"x": x, "y": y})
                    break

        if angle_rad == 0:
            obj = join_roads(coords, closed, 0)
        else:
            rotated_coords = [rotate_pt(c, angle_rad) for c in coords]
            obj = join_roads(rotated_coords, closed, 0)
        objectGroup.append(obj)

        objMesh = road_buffer(obj, value)
        if objMesh is not None:  # filter out ignored "areas"
            meshGroup.append(objMesh)

    return objectGroup, meshGroup
