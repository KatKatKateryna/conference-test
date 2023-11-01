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
from specklepy.objects import Base
from specklepy.objects.other import Collection

from flatten import flatten_base
from utils.utils_osm import getBuildings, getRoads
from utils.utils_other import RESULT_BRANCH
from utils.utils_png import createImageFromBbox


class FunctionInputs(AutomateBase):
    """These are function author defined values.

    Automate will make sure to supply them matching the types specified here.
    Please use the pydantic model schema to define your inputs:
    https://docs.pydantic.dev/latest/usage/models/
    """

    radius_in_meters: float = Field(
        title="Radius in meters",
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
        data = automate_context.automation_run_data

        project_id = data.project_id
        projInfo = base[
            "info"
        ]  # [o for o in objects if o.speckle_type.endswith("Revit.ProjectInfo")][0]

        lon = np.rad2deg(projInfo["longitude"])
        lat = np.rad2deg(projInfo["latitude"])
        angle_deg = 0
        try:
            angle_rad = projInfo["locations"][0]["trueNorth"]
            angle_deg = np.rad2deg(angle_rad)
        except:  # noqa: E722
            pass

        commitObj = Collection(
            elements=[], units="m", name="Context", collectionType="ContextLayer"
        )

        blds = getBuildings(lat, lon, function_inputs.radius_in_meters, angle_rad)
        bases = [Base(units="m", displayValue=[b], building=tag) for b, tag in blds]
        bldObj = Collection(
            elements=bases, units="m", name="Context", collectionType="BuildingsLayer"
        )

        roads, meshes, analysisMeshes = getRoads(
            lat, lon, function_inputs.radius_in_meters, angle_rad
        )
        roadObj = Collection(
            elements=roads, units="m", name="Context", collectionType="RoadsLayer"
        )
        roadMeshObj = Collection(
            elements=meshes, units="m", name="Context", collectionType="RoadMeshesLayer"
        )

        # add objects to new Collection
        commitObj.elements.append(bldObj)
        commitObj.elements.append(roadObj)
        commitObj.elements.append(roadMeshObj)

        # create branch if needed
        existing_branch = automate_context.speckle_client.branch.get(
            project_id, RESULT_BRANCH, 1
        )
        if existing_branch is None:
            br_id = automate_context.speckle_client.branch.create(
                stream_id=project_id, name=RESULT_BRANCH, description=""
            )
        else:
            br_id = existing_branch.id

        automate_context.create_new_version_in_project(
            commitObj, br_id, "Context from Automate"
        )

        automate_context._automation_result.result_view = f"{data.speckle_server_url}/projects/{data.project_id}/models/{data.model_id},{br_id}"

        # create and add basemape png file
        path = createImageFromBbox(lat, lon, function_inputs.radius_in_meters)
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
from specklepy.api.credentials import get_local_accounts
from specklepy.api.operations import send
from specklepy.transports.server import ServerTransport
from specklepy.core.api.client import SpeckleClient

lat = 51.500639115906935  # 52.52014  # 51.500639115906935
lon = -0.12688576809010643  # 13.40371  # -0.12688576809010643
radius_in_meters = 200
angle_rad = 1
streamId = "8ef52c7aa7"

acc = get_local_accounts()[1]
client = SpeckleClient(acc.serverInfo.url, acc.serverInfo.url.startswith("https"))
client.authenticate_with_account(acc)
transport = ServerTransport(client=client, stream_id=streamId)

blds = getBuildings(lat, lon, radius_in_meters, angle_rad)
base_blds = [Base(units="m", displayValue=[b], building=tag) for b, tag in blds]

commit_obj = Collection(
    elements=base_blds,
    units="m",
    name="Context",
    collectionType="BuildingsLayer",
)
objId = send(base=commit_obj, transports=[transport])
commit_id = client.commit.create(
    stream_id=streamId,
    object_id=objId,
    branch_name="main",
    message="Sent objects from Automate tests",
    source_application="Automate tests",
)


# path = createImageFromBbox(lat, lon, radius_in_meters)
# print(path)
"""
