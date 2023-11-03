
# OSM context

## Get OpenStreetMap context and Basemap for your Revit project

This function reads the location of your Revit model (latitude, longitude and angle to True North) and generates a new 
3d model with OSM buildings and roads within specified radius from the model. It also generates a .PNG image with a basemap 
of your selected location. 
![Final model](/assets/sample_result.gif)
![Final basemap](/assets/sample_basemap.gif)


### More details
This functon will create a custom Coordinate Reference System based on Traverse Mercator and centered around specified location, 
so that the size distortions of the real-world location are minimized. 3d geometries within specified radius will then be queried from 
[OSM API service](https://wiki.openstreetmap.org/wiki/Overpass_API), and the information for the basemap will be queried from the [OSM raster tiles provider](https://wiki.openstreetmap.org/wiki/Raster_tile_providers). 


### Using this Speckle Function

1. [Create](https://automate.speckle.dev/) a new Speckle Automation.
1. Select your Speckle Project and Speckle Model.
1. Select the existing Speckle Function for creating OSM context.
1. Enter a phrase to use in the comment.
1. Click `Create Automation`.

### Getting Started with creating your own Speckle Function

1. [Fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo) this repository.
1. [Clone](https://docs.github.com/en/get-started/quickstart/fork-a-repo#cloning-your-forked-repository) your forked repository to your development environment, or use [GitHub CodeSpaces](https://github.com/features/codespaces).
1. [Register](https://automate.speckle.dev/) your Function with [Speckle Automate](https://automate.speckle.dev/).
1. After completing the registration of the Function you will be shown a Function Publish Token and a Function ID. You will need these later.
1. Save your Function Publish Token as a [GitHub Action Secret](https://docs.github.com/en/actions/security-guides/encrypted-secrets#creating-encrypted-secrets-for-a-repository) named `SPECKLE_AUTOMATE_FUNCTION_PUBLISH_TOKEN`.
1. Save your Function ID as a [GitHub Action Secret](https://docs.github.com/en/actions/security-guides/encrypted-secrets#creating-encrypted-secrets-for-a-repository) named `SPECKLE_AUTOMATE_FUNCTION_ID`.
1. Make changes to your Function in `main.py`. See below for the Developer Requirements, and instructions on how to test.
1. Every commit to `main` branch will create a new version of your Speckle Function.

### Developer Requirements

1. Install the following:
    - [Python 3](https://www.python.org/downloads/)
    - [Poetry](https://python-poetry.org/docs/#installing-with-the-official-installer)
1. Run `poetry shell && poetry install` to install the required Python packages.

### Building and Testing

The code can be tested locally by running `poetry run pytest`.
The code should also be packaged into the format required by Speckle Automate, a Docker Container Image, and that should also be tested.

### Resources

- [Learn](https://speckle.guide/dev/python.html) more about SpecklePy, and interacting with Speckle from Python.
