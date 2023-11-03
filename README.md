
# OSM context

## Get OpenStreetMap context and Basemap for your Revit project

This function reads the location of your Revit model (latitude, longitude and angle to True North) and generates a new 
3d model with OSM buildings and roads within specified radius from the model. It also generates a .PNG image with a basemap 
of your selected location. 
![Final model](/assets/sample_result.gif)
![Final basemap](/assets/sample_basemap.png)


### More details
This functon will create a custom Coordinate Reference System based on Traverse Mercator and centered around specified location, 
so that the size distortions of the real-world location are minimized. 3d geometries within specified radius will then be queried from 
[OSM API service](https://wiki.openstreetmap.org/wiki/Overpass_API), and the information for the basemap will be queried from the [OSM raster tiles provider](https://wiki.openstreetmap.org/wiki/Raster_tile_providers). 

Location info from Revit model (lat, lon, angle) will be derived from the following settings under the tab Manage->Location: 
![Revit location settings](/assets/revit_location.PNG)


### Using this Speckle Function

1. [Create](https://automate.speckle.dev/) a new Speckle Automation.
1. Select your Speckle Project and Speckle Model.
1. Select the existing Speckle Function for creating OSM context.
1. Enter the chosen radius from your project location.
1. Click `Create Automation`.
