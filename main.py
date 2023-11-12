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

from utils.utils_osm import get_buildings, get_nature, get_roads
from utils.utils_other import RESULT_BRANCH
from utils.utils_png import create_image_from_bbox
from utils.utils_server import query_version_info


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
    include_nature: bool = Field(
        title="Include natural elements",
        description=("Include natural elements (grass, trees etc.)"),
    )
    generate_image: bool = Field(
        title="Generate a 2d map",
        description=(
            "Enable or disable generation of 2d map, in addition to the 3d model"
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
        projInfo = query_version_info(automate_context)
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
        if function_inputs.include_nature is True:
            nature_base_objects = get_nature(
                lat, lon, function_inputs.radius_in_meters, angle_rad
            )
        else:
            nature_base_objects = []

        # create layers for buildings and roads
        building_layer = Collection(
            elements=building_base_objects,
            units="m",
            name="Context: Buildings",
            collectionType="BuildingsMeshesLayer",
            source_data="© OpenStreetMap",
            source_url="https://www.openstreetmap.org/",
        )
        r"""
        roads_line_layer = Collection(
            elements=roads_lines,
            units="m",
            name="Context: Roads (Polylines)",
            collectionType="RoadPolyinesLayer",
            source_data="© OpenStreetMap",
            source_url="https://www.openstreetmap.org/",
        )
        """
        roads_mesh_layer = Collection(
            elements=roads_meshes,
            units="m",
            name="Context: Roads (Meshes)",
            collectionType="RoadMeshesLayer",
            source_data="© OpenStreetMap",
            source_url="https://www.openstreetmap.org/",
        )
        nature_layer = Collection(
            elements=nature_base_objects,
            units="m",
            name="Context: Nature",
            collectionType="NatureMeshesLayer",
            source_data="© OpenStreetMap",
            source_url="https://www.openstreetmap.org/",
        )

        # add layers to a commit Collection object
        commit_obj = Collection(
            elements=[building_layer, roads_mesh_layer, nature_layer],
            units="m",
            name="Context",
            collectionType="ContextLayer",
            source_data="© OpenStreetMap",
            source_url="https://www.openstreetmap.org/",
        )

        # create a commit
        new_model_id, _ = automate_context.create_new_version_in_project(
            commit_obj, RESULT_BRANCH, "Context from Automate"
        )

        # create and add a basemap png file
        if function_inputs.generate_image is True:
            path = create_image_from_bbox(lat, lon, function_inputs.radius_in_meters)
            automate_context.store_file_result(path)

        # automate_context.set_context_view(
        #    resource_ids=[automate_context.automation_run_data.model_id, new_model_id]
        # )
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
if __name__ == "__main__11":
    # NOTE: always pass in the automate function by its reference, do not invoke it!

    # pass in the function reference with the inputs schema to the executor
    execute_automate_function(automate_function, FunctionInputs)

    # if the function has no arguments, the executor can handle it like so
    # execute_automate_function(automate_function_without_inputs)

from specklepy.api.credentials import get_local_accounts
from specklepy.core.api.client import SpeckleClient
from speckle_automate.schema import AutomationRunData
from specklepy.transports.server import ServerTransport
from specklepy.api.models import Branch
from pydantic import BaseModel, ConfigDict, Field
from stringcase import camelcase

project_id = "23c31c18f5"  # "aeb6aa8a6c"
model_id = "3080ebb3c8"
radius_in_meters = 200

# get client
account = get_local_accounts()[1]
client = SpeckleClient(account.serverInfo.url)
client.authenticate_with_token(account.token)
speckle_client: SpeckleClient = client
server_transport = ServerTransport(project_id, client)

branch: Branch = client.branch.get(project_id, model_id, 1)
version_id = branch.commits.items[0].id

# create automation run data
automation_run_data = AutomationRunData(
    project_id=project_id,
    model_id=model_id,  # "02e4c63027",
    branch_name="main",
    version_id=version_id,  # "c26b96d649",  # "33e62b9536",
    speckle_server_url=account.serverInfo.url,
    automation_id="",
    automation_revision_id="",
    automation_run_id="",
    function_id="",
    function_name="function_name",
    function_logo="",
    model_config=ConfigDict(
        alias_generator=camelcase, populate_by_name=True, protected_namespaces=()
    ),
)

# initialize Automate variables
automate_context = AutomationContext(
    automation_run_data, speckle_client, server_transport, account.token
)
function_inputs = FunctionInputs(
    radius_in_meters=radius_in_meters, include_nature=True, generate_image=False
)

# execute_automate_function(automate_function, FunctionInputs)
automate_function(automate_context, function_inputs)
