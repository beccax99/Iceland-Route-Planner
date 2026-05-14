This repository contains all files related to my project Overtourism in Iceland - Spatial Quantification and Alternative Routes.

All files related to the analysis and preparation of the prototype are in the main folder. The files needed to run the prototype 
(on streamlit) are in the app folder.
Please note that the scraped data resulting from two of the notebooks is not included here due to size limitations. All other data 
is present and should run.

Here is an overview of what each notebook does, what inputs (if any) it needs, and what outputs (if any) it produces:

Data Retrieval and Pre-Processing -- Overnight Stays

This notebook reads in and pre-processes the data related to the overnight stays.

Inputs: 
- Overnight_stays_per_muncip_Iceland_2024.xlsx
- LMI WFS for boundaries (not a local file)
- population_per_mucipality_iceland_2024.xlsx

Outputs:
- iceland_overnight_geo_df.geojson


Data Retrieval and Pre-Processing -- Road Traffic Data

The notebook reads in and pre-processes the data related to the road traffic counts.

Inputs:
- road_traffic_data_2024.xlsx
- Geoserver API geometries (not a local file)

Outputs:
- iceland_traffic_summer_ratio.geojson


Analysis and Visualization -- Overnight Stays

This notebook uses the pro-processed data related to overnight stays for analysis and visuals.

Inputs:
- iceland_overnight_geo_df.geojson

Outputs:
- Visual for report
- No files as output


Analysis and Visualization -- Road Traffic Data

This notebook uses the pro-processed data related to road traffic counts for analysis and visuals.

Inputs:
- iceland_traffic_summer_ratio.geojson

Outputs:
- Visual for report
- No files as output


Data Retrieval -- Tripadvisor Scraping

This notebook scrapes the result pages containing the attractions in Iceland from Tripadvisor.

Inputs:
- None

Outputs:
- Folder tripadvisor_pages with html files of search pages


Data Pre-Processing -- TripAdvisor Pages

The data uses the html files scraped from Tripadvisor and creates a dataframe of attractions.

Inputs:
- 98 html files contained in folder tripadvisor_pages

Outputs:
- tripadvisor_attractions.json (before filtering out categories not needed, saved as backup)
- tripadvisor_attractions_filtered.json


Data Retrieval -- TripAdvisor Attractions

This notebook uses the link to each attraction contained in the dataframe above to scrape the page of each attraction.

Inputs:
- tripadvisor_attractions_filtered.json

Outputs:
- Folder attraction_pages with html files of attraction pages


Data Pre-Processing -- Tripadvisor Attractions

This notebook creates a geodataframe of attractions including their geocoordinates.

Inputs:
- tripadvisor_attractions_filtered
- Html files from folder attraction_pages

Outputs:
- tripadvisor_attractions_geo.json (df with geoinformation but no geometries)
- tripadvisor_attractions_geo.geojson


Analysis and Visualization -- KDE Plot and DBSCAN on Tripadvisor Data

This notebook uses the pre-processed Tripadvisor data and uses it for analysis and visualization.

Inputs:
- tripadvisor_attractions_geo.geojson

Outputs:
- tripadvisor_attractions_geo_cleaned.geojson


Data Pre-Processing -- Groups of Categories from TripAdvisor Data

This notebook creates groups of categories for the Tripadvisor data. 

Inputs:
- tripadvisor_attractions_geo_cleaned.geojson

Outputs:
- tripadvisor_attractions_geo_prepared.geojson


Routing App - Preprocessing

This notebook does all pre-processing needed for the routing app.

Inputs:
- tripadvisor_attractions_geo_prepared.geojson
- iceland_overnight_geo_df.geojson
- OSMnx data retrieved using ox.graph_from_place function

Outputs:
- alternative_attractions_processed.geojson
- config.json (contains Keflavik node)
- distance_matrix.csv
- iceland_drive_accessible.graphml


Routing App - Routing

This notebook contains the routing algorithm, but to be run in Python (the app.py file in the app folder is for the actual streamlit app
with the prototype).

Inputs:
- iceland_drive_accessible.graphml
- distance_matrix.csv
- config.json (contains Keflavik node)
- alternative_attractions_processed.geojson
- User input for parameters
Outputs:
- reordered_itinerary (not saved locally)

