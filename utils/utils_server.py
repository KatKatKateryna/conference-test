from specklepy.api.wrapper import StreamWrapper
from gql import gql
from specklepy.logging.exceptions import SpeckleException


def query_version_info(automate_context):
    automation_run_data = automate_context.automation_run_data
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
    client = automate_context.speckle_client
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
            raise SpeckleException("Not a valid 'Revit.ProjectInfo' provided")

    return projInfo
