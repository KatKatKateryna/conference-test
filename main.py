"""This module contains the business logic of the function.

use the automation_context module to wrap your function in an Autamate context helper
"""

from datetime import datetime
import numpy as np
from pydantic import Field
from speckle_automate import (
    AutomateBase,
    AutomationContext,
    execute_automate_function,
)
from specklepy.objects.other import Collection
from specklepy.api.wrapper import StreamWrapper

from utils.utils_osm import get_buildings, get_roads
from utils.utils_other import RESULT_BRANCH
from utils.utils_png import create_image_from_bbox
from gql import gql


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
        time_start = datetime.now()

        # get branch name
        query = gql(
            """
            query Stream($project_id: String!, $model_id: String!, $version_id: String!) {
                project(id:$project_id) {
                    model(id: $model_id) {
                        version(id: $version_id) {
                            referencedObject
                        }
                    }
                }
            }
        """
        )
        sw = StreamWrapper(
            f"{automation_run_data.speckle_server_url}/projects/{automation_run_data.project_id}"
        )
        client = sw.get_client()
        params = {
            "project_id": automation_run_data.project_id,
            "model_id": automation_run_data.model_id,
            "version_id": automation_run_data.version_id,
        }
        project = client.httpclient.execute(query, params)
        try:
            ref_obj = project["project"]["model"]["version"]["referencedObject"]
            # get Project Info
            query = gql(
                """
                query Stream($project_id: String!, $ref_id: String!) {
                    stream(id: $project_id){
                        object(id: $ref_id){
                        data
                        }
                    }
                }
            """
            )
            params = {
                "project_id": automation_run_data.project_id,
                "ref_id": ref_obj,
            }
            project = client.httpclient.execute(query, params)
            projInfo = project["stream"]["object"]["data"]["info"]

        except KeyError:
            base = automate_context.receive_version()

            projInfo = base["info"]
            if not projInfo.speckle_type.endswith("Revit.ProjectInfo"):
                automate_context.mark_run_failed(
                    "Not a valid 'Revit.ProjectInfo' provided"
                )

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
        roads_lines, roads_meshes = [], []  # get_roads(
        #    lat, lon, function_inputs.radius_in_meters, angle_rad
        # )

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
            commit_obj, RESULT_BRANCH + "_local", "Context from Automate"
        )

        # create and add a basemap png file
        # print("Create 2d image")
        # path = create_image_from_bbox(lat, lon, function_inputs.radius_in_meters)
        # print(path)
        # automate_context.store_file_result(path)

        time_end = datetime.now()
        print(f"Total time: {time_end - time_start}")
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

##########################################################################


from specklepy.api.credentials import get_local_accounts
from specklepy.core.api.client import SpeckleClient
from speckle_automate.schema import AutomationRunData
from specklepy.transports.server import ServerTransport
from pydantic import BaseModel, ConfigDict, Field
from stringcase import camelcase

project_id = "23c31c18f5"  # "aeb6aa8a6c"
radius_in_meters = 50

# get client
account = get_local_accounts()[1]
client = SpeckleClient(account.serverInfo.url)
client.authenticate_with_token(account.token)
speckle_client: SpeckleClient = client
server_transport = ServerTransport(project_id, client)

# create automation run data
automation_run_data = AutomationRunData(
    project_id=project_id,
    model_id="3080ebb3c8",  # "02e4c63027",
    branch_name="main",
    version_id="c26b96d649",  # "33e62b9536",
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
function_inputs = FunctionInputs(radius_in_meters=radius_in_meters)

# execute_automate_function(automate_function, FunctionInputs)
automate_function(automate_context, function_inputs)

exit()
# local testing 2

from specklepy.api.credentials import get_local_accounts
from specklepy.api.operations import send
from specklepy.transports.server import ServerTransport
from specklepy.core.api.client import SpeckleClient
from specklepy.api.models import Branch
from specklepy.api.operations import receive, send

r"""
lat = 51.500639115906935  # 52.52014  # 51.500639115906935
lon = -0.12688576809010643  # 13.40371  # -0.12688576809010643
radius_in_meters = 100
angle_rad = 1
project_id = "8ef52c7aa7"
"""
server_url = "https://latest.speckle.dev/"  # "https://speckle.xyz/" # project_data.speckle_server_url
project_id = "aeb6aa8a6c"  # project_data.project_id
model_id = "main"
radius_in_meters = 300  # float(project_data.radius)

account = get_local_accounts()[0]
client = SpeckleClient(server_url)
client.authenticate_with_token(account.token)
branch: Branch = client.branch.get(project_id, model_id, 1)

commit = branch.commits.items[0]
server_transport = ServerTransport(project_id, client)
base = receive(branch.commits.items[0].referencedObject, server_transport)


acc = get_local_accounts()[1]
client = SpeckleClient(acc.serverInfo.url, acc.serverInfo.url.startswith("https"))
client.authenticate_with_account(acc)
transport = ServerTransport(client=client, stream_id=project_id)

#############################

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
    stream_id=project_id,
    object_id=objId,
    branch_name="main",
    message="Sent objects from Automate tests",
    source_application="Automate tests",
)


path = create_image_from_bbox(lat, lon, radius_in_meters)
print(path)


# TO DEBUG LOCALLY run this file #3
from specklepy.api.models import Branch
from specklepy.api.client import SpeckleClient
from specklepy.transports.server import ServerTransport
from specklepy.api.credentials import get_local_accounts
from specklepy.api.operations import receive, send


def run(client, server_transport, base, radius_in_meters):
    import numpy as np

    project_id = server_transport.stream_id
    projInfo = base[
        "info"
    ]  # [o for o in objects if o.speckle_type.endswith("Revit.ProjectInfo")][0]

    lon = np.rad2deg(projInfo["longitude"])
    lat = np.rad2deg(projInfo["latitude"])
    try:
        angle_rad = projInfo["locations"][0]["trueNorth"]
    except:
        angle_rad = 0

    crsObj = None
    commitObj = Collection(
        elements=[], units="m", name="Context", collectionType="BuildingsLayer"
    )

    blds = get_buildings(lat, lon, radius_in_meters, angle_rad)
    # bases = [Base(units = "m", displayValue = [b]) for b in blds]
    bldObj = Collection(
        elements=blds, units="m", name="Context", collectionType="BuildingsLayer"
    )

    # create branch if needed
    existing_branch = client.branch.get(project_id, "Automate_only_buildings", 1)
    if existing_branch is None:
        br_id = client.branch.create(
            stream_id=project_id, name="Automate_only_buildings", description=""
        )

    # commitObj.elements.append(base)
    commitObj.elements.append(bldObj)
    # commitObj.elements.append(roadObj)

    objId = send(commitObj, transports=[server_transport])
    commit_id = client.commit.create(
        stream_id=project_id,
        object_id=objId,
        branch_name="Automate_only_buildings",
        message="Context from Automate_local",
        source_application="Python",
    )


server_url = "https://latest.speckle.dev/"  # "https://speckle.xyz/" # project_data.speckle_server_url
project_id = "aeb6aa8a6c"  # project_data.project_id
model_id = "main"
radius_in_meters = 300  # float(project_data.radius)

account = get_local_accounts()[0]
client = SpeckleClient(server_url)
client.authenticate_with_token(account.token)
branch: Branch = client.branch.get(project_id, model_id, 1)

commit = branch.commits.items[0]
server_transport = ServerTransport(project_id, client)
base = receive(branch.commits.items[0].referencedObject, server_transport)

run(client, server_transport, base, radius_in_meters)
