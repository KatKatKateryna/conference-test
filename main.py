"""This module contains the business logic of the function.

use the automation_context module to wrap your function in an Autamate context helper
"""

import numpy as np
from pydantic import Field
from speckle_automate import (
    AutomateBase,
    AutomationContext,
    execute_automate_function,
)
from specklepy.objects.other import Collection

from utils.utils_osm import get_buildings, get_roads
from utils.utils_other import RESULT_BRANCH
from utils.utils_png import create_image_from_bbox


class FunctionInputs(AutomateBase):
    """These are function author defined values.

    Automate will make sure to supply them matching the types specified here.
    Please use the pydantic model schema to define your inputs:
    https://docs.pydantic.dev/latest/usage/models/
    """

    radius_in_meters: float = Field(
        title="Radius in meters",
        ge=50,
        le=1000,
        description=(
            "Radius from the Model location," " derived from Revit model lat, lon."
        ),
    )


def automate_function(
    automate_context: AutomationContext,
    function_inputs: FunctionInputs,
) -> None:
    """This is an example Speckle Automate function.

    Args:
        automate_context: A context helper object, that carries relevant information
            about the runtime context of this function.
            It gives access to the Speckle project data, that triggered this run.
            It also has conveniece methods attach result data to the Speckle model.
        function_inputs: An instance object matching the defined schema.
    """
    # the context provides a conveniet way, to receive the triggering version
    try:
        base = automate_context.receive_version()

        projInfo = base["info"]
        if not projInfo.speckle_type.endswith("Revit.ProjectInfo"):
            automate_context.mark_run_failed("Not a valid 'Revit.ProjectInfo' provided")

        lon = np.rad2deg(projInfo["longitude"])
        lat = np.rad2deg(projInfo["latitude"])
        try:
            angle_rad = projInfo["locations"][0]["trueNorth"]
        except:
            angle_rad = 0

        # get OSM buildings and roads in given area
        building_base_objects = get_buildings(
            lat, lon, function_inputs.radius_in_meters, angle_rad
        )
        roads_lines, roads_meshes = get_roads(
            lat, lon, function_inputs.radius_in_meters, angle_rad
        )

        # create layers for buildings and roads
        building_layer = Collection(
            elements=building_base_objects,
            units="m",
            name="Context: Buildings",
            collectionType="BuildingsMeshesLayer",
            source_data="© OpenStreetMap",
            source_url="https://www.openstreetmap.org/",
        )
        roads_line_layer = Collection(
            elements=roads_lines,
            units="m",
            name="Context: Roads (Polylines)",
            collectionType="RoadPolyinesLayer",
            source_data="© OpenStreetMap",
            source_url="https://www.openstreetmap.org/",
        )
        roads_mesh_layer = Collection(
            elements=roads_meshes,
            units="m",
            name="Context: Roads (Meshes)",
            collectionType="RoadMeshesLayer",
            source_data="© OpenStreetMap",
            source_url="https://www.openstreetmap.org/",
        )

        # add layers to a commit Collection object
        commit_obj = Collection(
            elements=[building_layer, roads_line_layer, roads_mesh_layer],
            units="m",
            name="Context",
            collectionType="ContextLayer",
            source_data="© OpenStreetMap",
            source_url="https://www.openstreetmap.org/",
        )

        # create a commit
        automate_context.create_new_version_in_project(
            commit_obj, RESULT_BRANCH, "Context from Automate"
        )

        # create and add a basemap png file
        path = create_image_from_bbox(lat, lon, function_inputs.radius_in_meters)
        automate_context.store_file_result(path)

        automate_context.mark_run_success("Created 3D context")
    except Exception as ex:
        automate_context.mark_run_failed(f"Failed to create 3d context cause: {ex}")


def automate_function_without_inputs(automate_context: AutomationContext) -> None:
    """A function example without inputs.

    If your function does not need any input variables,
     besides what the automation context provides,
     the inputs argument can be omitted.
    """
    pass


# make sure to call the function with the executor
if __name__ == "__main__":
    # NOTE: always pass in the automate function by its reference, do not invoke it!

    # pass in the function reference with the inputs schema to the executor
    execute_automate_function(automate_function, FunctionInputs)

    # if the function has no arguments, the executor can handle it like so
    # execute_automate_function(automate_function_without_inputs)

##########################################################################

r"""
# local testing

from specklepy.api.credentials import get_local_accounts
from specklepy.api.operations import send
from specklepy.transports.server import ServerTransport
from specklepy.core.api.client import SpeckleClient

lat = 51.500639115906935  # 52.52014  # 51.500639115906935
lon = -0.12688576809010643  # 13.40371  # -0.12688576809010643
radius_in_meters = 100
angle_rad = 1
streamId = "8ef52c7aa7"

acc = get_local_accounts()[1]
client = SpeckleClient(acc.serverInfo.url, acc.serverInfo.url.startswith("https"))
client.authenticate_with_account(acc)
transport = ServerTransport(client=client, stream_id=streamId)

#############################

# get OSM buildings and roads in given area
building_base_objects = get_buildings(lat, lon, radius_in_meters, angle_rad)
roads_lines, roads_meshes = get_roads(lat, lon, radius_in_meters, angle_rad)

# create layers for buildings and roads
building_layer = Collection(
    elements=building_base_objects,
    units="m",
    name="Context",
    collectionType="BuildingsLayer",
    source_data="© OpenStreetMap",
    source_url="https://www.openstreetmap.org/",
)
roads_line_layer = Collection(
    elements=roads_lines,
    units="m",
    name="Context",
    collectionType="RoadLinesLayer",
    source_data="© OpenStreetMap",
    source_url="https://www.openstreetmap.org/",
)
roads_mesh_layer = Collection(
    elements=roads_meshes,
    units="m",
    name="Context",
    collectionType="RoadMeshesLayer",
    source_data="© OpenStreetMap",
    source_url="https://www.openstreetmap.org/",
)

# add layers to a commit Collection object
commit_obj = Collection(
    elements=[building_layer, roads_line_layer, roads_mesh_layer],
    units="m",
    name="Context",
    collectionType="ContextLayer",
    source_data="© OpenStreetMap",
    source_url="https://www.openstreetmap.org/",
)

#################################
objId = send(base=commit_obj, transports=[transport])
commit_id = client.commit.create(
    stream_id=streamId,
    object_id=objId,
    branch_name="main",
    message="Sent objects from Automate tests",
    source_application="Automate tests",
)


path = create_image_from_bbox(lat, lon, radius_in_meters)
print(path)
"""
