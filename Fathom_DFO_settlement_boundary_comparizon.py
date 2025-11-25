import glob
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
import matplotlib.pyplot as plt
import gc
from shapely.ops import unary_union
import os
from tqdm import tqdm

def extract_points_from_polygons(polygons):
    '''
    Extract centroid coordinates from a list of polygon geometries.
    
    input:
    - polygons:  a list of polygon geometries

    output:
    - points_list: a list of centroid coordinates

    '''
    points_list = []
    for poly in polygons:
        points_list.append((poly.centroid.x, poly.centroid.y))
    return points_list

def boundary_watershed():
    '''
    Find the inundated watershed for each events with GFD data
    '''

    #  Load watershed boundaries and shrink them slightly to reduce edge noise.
    merged_gdf = gpd.read_file("lev07_v1c_merged")
    shrunk_gdf = merged_gdf.copy()
    shrunk_gdf['geometry'] = shrunk_gdf['geometry'].buffer(-0.01)
    shrunk_gdf = shrunk_gdf[~shrunk_gdf.is_empty & shrunk_gdf.is_valid]

    # Create spatial index for fast intersection lookup
    sindex = shrunk_gdf.sindex

    for tiff_path in glob.glob("unzipped/*/DFO_*.tif"):
        tmp = tiff_path.split("/")[-1].split(".")[0]
        if os.path.exists(f"plots/{tmp}.png"):
            continue
        print(f"Processing: {tmp}")

        # Load flood footprint polygons (from GFD)
        gdf = gpd.read_file(f"gfd_footprints/{tmp}_nonzero_polygons.geojson", driver="GeoJSON")

        polygons_gdf = gdf.to_crs(shrunk_gdf.crs)

        # Compute total flooded area
        areas = polygons_gdf.to_crs(epsg=3857).area
        total_area_km2 = areas.sum() / 1e6
        print(f"Total area: {total_area_km2:.2f} km²")

        
        # Identify intersecting watershed polygons
        intersecting_indices = set()
        for poly in polygons_gdf.geometry:
            possible_matches_index = list(sindex.intersection(poly.bounds))
            possible_matches = shrunk_gdf.iloc[possible_matches_index]
            for idx, candidate in possible_matches.geometry.items():
                if poly.intersects(candidate):
                    intersecting_indices.add(idx)
        
        # Identify which watersheds intersect with the flood
        intersecting_gdf = shrunk_gdf.loc[list(intersecting_indices)]

        # Collect all intersecting watershed polygons
        intersecting_gdf['geometry'] = intersecting_gdf['geometry'].buffer(0.02)

        # Slightly expand polygons to ensure a clean merge and then merge into one unioned watershed polygon
        merged_polygon = unary_union(intersecting_gdf.geometry)
        merged_polygon_gdf = gpd.GeoDataFrame(geometry=[merged_polygon], crs=intersecting_gdf.crs)

        # Save the watershed boundary
        merged_polygon_gdf.to_file(f"dfo_basins/{tmp}_merged_polygon.geojson", driver="GeoJSON")


        # Plot centroids of original GFD polygons
        polygons_list = polygons_gdf.geometry.to_list()
        points = extract_points_from_polygons(polygons_list)
        points = [Point(x, y) for x, y in points]
        points_gdf = gpd.GeoDataFrame(geometry=points, crs=intersecting_gdf.crs)
        if len(intersecting_gdf) > 0:
            fig, ax = plt.subplots(figsize=(10, 10))
            intersecting_gdf.plot(ax=ax, facecolor='lightblue', edgecolor='black', alpha=0.5)
            polygons_gdf.plot(ax=ax, facecolor='none', edgecolor='red', linewidth=1.5)
            points_gdf.plot(ax=ax, color='green', markersize=20)
            plt.savefig(f"plots/{tmp}.png", dpi=150)
            plt.close(fig)  # free memory

        del gdf, polygons_gdf, intersecting_gdf, points_gdf, points
        gc.collect()

        print(f"Finished {tmp}\n")

def substitue(dfo):
    '''
    Substitue the geometry to the boundary of watersheds if it exists

    input:
    - dfo: GeoDataFrame of DFO dataset
    '''
    for i in tqdm(dfo.index):
        id = dfo['ID'][i]

        # Search for matching watershed boundary files
        tmp = glob.glob(f"dfo_basins/DFO_{id}_*_merged_polygon.geojson")
        if len(tmp)>0:
            # Merge into one unioned polygon
            gdfs = [gpd.read_file(shp) for shp in tmp]
            merged_gdf = pd.concat(gdfs, ignore_index=True)
            merged_polygon = unary_union(merged_gdf.geometry)
            # Replace original flood polygon
            dfo['geometry'][i] = merged_polygon


def proportion(dfo, hulls, merged_polygon):
    '''
    Check the proportion of the settlement’s area that has historically
    overlapped with reported flood-affected regions.
    
    input:
    - dfo: GeoDataFrame of DFO flood dataset.
    - hulls: GeoDataFrame of settlement convex hulls.
    - merged_polygon: shapely Polygon of global land area.
    
    Computes historical flood exposure for each hull and adds fields:
    - 'covered' (max overlap)
    - 'avg_covered' (mean overlap)
    - 'count' (# events)

    '''
    ratios = []
    avg_ratios = []
    counts = []

    dfo_sindex = dfo.sindex

    for i in tqdm(hulls.index):
        hull = hulls['geometry'][i]

        # Fix invalid geometry
        if not hull.is_valid:
            hull = hull.buffer(0)

        # Restrict to land
        hull = hull.intersection(merged_polygon)
        
        max_area = 0

        # Retrieve candidate DFO events by spatial index
        possible_matches_index = list(dfo_sindex.intersection(hull.bounds))
        possible_matches = dfo.iloc[possible_matches_index]

        n = 0
        sum_max = 0
        for _, flood in possible_matches.iterrows():
            flood = flood['geometry']
            if not flood.is_valid:
                flood = flood.buffer(0)

            intersection = hull.intersection(flood)

            # Skip negligible overlaps
            if intersection.area/hull.area < 0.15 and intersection.area/flood.area <0.15:
                continue

            # Track largest overlap ratio
            max_area = max(max_area, intersection.area)
            n += 1
            sum_max += intersection.area


        ratios.append(max_area / hull.area)
        avg_ratios.append( sum_max/hull.area/max(n,1) )
        counts.append(n)

    hulls['covered'] = ratios
    hulls['avg_covered'] = avg_ratios
    hulls['count'] = counts

def save_with_centroid(gdf):
    """
    Save hulls with centroid geometry instead of polygon geometry.

    input:
    - dfo: GeoDataFrame of with polygon as geometry.
    """

    gdf["polygon"] = gdf.geometry

    # Replace geometry column with centroid
    gdf["centroid"] = gpd.GeoSeries(gdf.geometry.centroid, crs=gdf.crs)
    gdf = gpd.GeoDataFrame(gdf.drop(columns="geometry"), geometry=gdf["centroid"], crs=gdf.crs)
    
    # Save polygon as WKT string
    gdf["polygon"] = gdf["polygon"].to_wkt()
    gdf = gdf.drop(columns=['geometry'])

    gdf.to_file("convex_hull_remove_sea_combine_dfo_gfd_centroid")


if __name__ == "__main__":

    # find the inundated watershed for each events with GFD data
    boundary_watershed()

    dfo = gpd.read_file("dfo_2025").to_crs("EPSG:4326")
    # substitue the geometry to the boundary of watersheds if it exists
    substitue(dfo)

    # get the land boundary
    all_gdf = pd.DataFrame()
    for fn in glob.glob("WB_regions_polygons/*.shp"):
        gdf = gpd.read_file(fn).to_crs("EPSG:4326")
        all_gdf = pd.concat([all_gdf, gdf], axis=0)
    merged_polygon = all_gdf.geometry.unary_union

    # check the portion of the settlement’s area that has historically
    # overlapped with reported flood-affected regions.
    hulls = gpd.read_file("convex_hulls_global").to_crs("EPSG:4326")
    proportion(dfo, hulls, merged_polygon)


    # find the settlements' centroid and save
    save_with_centroid(hulls)