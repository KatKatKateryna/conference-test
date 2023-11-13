from specklepy.api.credentials import get_local_accounts
from specklepy.api.operations import send
from specklepy.transports.server import ServerTransport
from specklepy.core.api.client import SpeckleClient
from specklepy.api.models import Branch
from specklepy.api.operations import receive, send
from specklepy.objects.geometry import Mesh

server_url = "https://latest.speckle.dev/"  # "https://speckle.xyz/" # project_data.speckle_server_url
project_id = "23c31c18f5"  # project_data.project_id
model_id = "tree"
radius_in_meters = 300  # float(project_data.radius)

account = get_local_accounts()[0]
client = SpeckleClient(server_url)
client.authenticate_with_token(account.token)
branch: Branch = client.branch.get(project_id, model_id, 1)

commit = branch.commits.items[0]
server_transport = ServerTransport(project_id, client)
base1 = receive(branch.commits.items[0].referencedObject, server_transport)
mesh = base1["@Data"]["@{0}"][0]
# print(mesh.vertices)
# print(mesh.faces)
# print(mesh.colors)


f = open("assets/trees.py", "w")
f.write(
    "VERTICES=" + str(mesh.vertices) + "\n\n"
    "FACES=" + str(mesh.faces) + "\n\n"
    "COLORS=" + str(mesh.colors) + "\n\n"
    "TEXTURE_COORDS=" + str(mesh.textureCoordinates)
)
f.close()

obj = Mesh.create(
    faces=mesh.faces,
    vertices=mesh.vertices,
    colors=mesh.colors,
    texture_coordinates=mesh.textureCoordinates,
)
obj.units = "m"

# base_id = send(obj, [server_transport])
# print(base_id)
