# A global evaluation of flood impacts on road networks informs resilience investments

## Our team:
Yiyi He, Georgia Tech<br>
Jun Rentschler, The World Bank<br>
Paolo Avner, The World Bank<br>
Zhengyang Wei, Stanford University<br>
Jianxi Gao, Rensselaer Polytechnic Institute<br>
Jenny Suckale, Stanford University<br>

## Research gaps that we found:

Anthropogenic climate change and rapid urbanization, combined with increasing interdependencies among various critical infrastructure systems, are forcing road transportation networks under climatic pressure more than ever in human history. With the European floods as the backdrop, we have witnessed the growing fragility and interconnectivity of road infrastructure networks in the face of catastrophic events. Although three decades of studies attempted to understand the infrastructure vulnerability and flood risks, we discovered two gaps that prohibit us from building a solid understanding of the real impact of flood hazards and generating climate solutions that are genuinely effective after a thorough literature review.

1.	Current policies and regulations for infrastructure networks are skewed heavily towards pure <ins>hazard exposure</ins> since the complexity of global human mobility, particularly through road transportation, makes it increasingly challenging to develop effective management and mitigation strategies. To this day, a global evaluation of the indirect impact that considers <ins>the movement of people</ins> on these networks is still absent.
2.	Although many countries and regions have set forth climate action plans and disaster risk reduction protocols, the <ins>governing factors</ins> determining road networks' resilience to flood hazards remain a mystery. Consequently, investments made without a fundamental understanding of the drivers behind road network resilience will render futile.

## Our contribution:

In this study, we provide the first global evaluation of direct and, more importantly, indirect flood impact on road networks for <span style="color:navy">**2,564**</span> human settlements representing over <span style="color:navy">**14 million kilometers**</span> of road networks spanning <span style="color:navy">**177 countries**</span> and regions under ten flood intensities. The main contributions of our study are threefold:

1.	We look <ins>beyond infrastructure exposure</ins> and simulate the impact of floods on <ins>mobility</ins> concerning road transportation networks <ins>worldwide</ins>, comparing and contrasting network resilience between countries and regions worldwide.

2.	We identified <ins>ten global hot spots</ins> with statistically significant clusters of networks of high indirect impact levels. These areas merit considerable attention since the interconnectivity between networks could ignite a domino-like effect causing individual failures in one network to propagate to other networks in close spatial proximity.

3.	We pinpoint three underlying drivers: <ins>exposure</ins>, <ins>connectivity</ins>, and <ins>travel pattern</ins> that influence the resilience of road networks based on global data. The result facilitates the development of <ins>region-specific</ins> hazard mitigation objectives and investigation plans, effectively reducing the indirect repercussions of floods.

In sum, the study has its genesis rooted in publications in this journal, warranting a broad impact among audiences in the academic fields, policy-makers, governments, and beyond. The paper will fundamentally enrich the tools scientists and engineers use to approach infrastructure resilience to natural disasters.

## Datasets we used in this study:
### [Open Street Map](https://www.openstreetmap.org/about)
OSM provides a free, openly licensed, volunteer-contributed repository of geographic information with a focus on streets and roads.  As of April 2025, approximately 10 million contributors had created this database with more than 1.1 billion roads, coastlines, administrative boundaries, and other linear features known as “ways”. We extract road networks from the OSM dataset using convex hulls created from settlement cluster boundaries as spatial masks.<br>

### [Fathom Global flood maps](https://www.fathom.global/product/global-flood-map/)
To understand the exposure of road networks to floods, we use the latest high-resolution (90 meters) pluvial and fluvial flood map products (in raster spatial data format) for 10 flood return periods (5, 10, 20, 50, 75, 100, 200, 250, 500, 1000) from Fathom. 

### [GHS Global Human Settlement Layer](https://human-settlement.emergency.copernicus.eu/ghs_smod2023.php)
The global human settlement model grid (GHS-SMOD) dataset developed and maintained by the European Commission provides a validated and complete representation of the spatial distribution of the population with global coverage. Specifically, it delineates and classifies 1x1 km grid cell into eight settlement classes defined based on population size and built-up area densities, thus refining Eurostat’s “degree of urbanization” method. These settlement typologies include water (class 10), very low-density rural (class 11), low-density rural (class 12), rural cluster (class 13), suburban or peri-urban (class 21), semi-dense urban cluster (class 22), dense urban cluster (class 23), urban center (class 30). We leverage this dataset to We extract boundaries for a total of 2,564 settlement clusters worldwide.

### [GHS Global Population Grid](https://human-settlement.emergency.copernicus.eu/ghs_pop2023.php)
The spatial raster dataset depicts the distribution of residential population, expressed as the number of people per cell. We use the clusters’ spatial boundaries as spatial masks in the extraction process and apply the min-max scaler to the resulting population raster. By doing so, all headcount values from the original GHS-POP raster are transformed into the range [0, 1]. In the simulation process, OD points are sampled based on the normalized population raster. Pixels with a higher population count will therefore have a higher chance of housing an origin or destination point location.

### [Project Dataset Repository – OneDrive Access](https://gtvault-my.sharepoint.com/:f:/g/personal/yhe603_gatech_edu/EqT8fsXe8lFCqAlv-F0wrvYBbSk28cIUrIVlhRRU4vf0Iw?e=u1fhx2)
Click the link above to access the project datasets associated with this project. Below is a list of what is stored inside the shared folder. If you have any questions, need additional information, or encounter any issues, please don’t hesitate to get in touch. You can reach us by sending an email to yiyi.he@design.gatech.edu—just include your name, affiliation, and a brief description of your inquiry so we can assist you more effectively.
- Original convex hull shapefiles(4299 polygons) 
    - Filename: *"4229_bnd_convex"*
- Eight giant cluster boundaries
    - Filename: *"Giant_cluster_boundary"*
- Selected convex hull shapefiles (2564 polygons with added attributes: number of simulations, average travel time under dry and 10 wet  conditions)
    - Filename: *"Convex_2654_avg_travel_time"*
- Routing simulation results (dry condition)
    - Filename: *"dry_OD_routing"*