"""
Attach raster-based flood depth information to road network nodes and edges.

This script samples flood depth rasters at network nodes and along road
segments, storing the maximum sampled depth as an attribute on each
node and edge. The resulting network is saved as a GraphML file and
optionally exported as a GeoDataFrame for GIS analysis.

Intended for reproducible scientific workflows and public release.
"""

import geopandas as gpd
from shapely.geometry import Polygon, Point, LineString
import pandas as pd
import json
import glob
import networkx as nx
from tqdm import tqdm
import numpy as np
# from utils import ray_tracing_numpy_numba
from geopy import distance
import os
import argparse
import warnings
warnings.filterwarnings("ignore")
import rasterio as rs
from shapely.geometry import shape
from rasterio.windows import Window
import pickle
from shapely import wkt

 
def attach_flood(src, G, rp):
    """
    Attach flood depth values from a raster to nodes and edges of a network.

    Parameters
    ----------
    src : rasterio.DatasetReader
        Open raster dataset containing flood depth values.
    G : networkx.MultiDiGraph
        Road network graph with node coordinates stored as 'x' (lon) and
        'y' (lat), and edge lengths stored as 'length'.
    rp : int
        Flood return period (e.g., 10, 50, 100), used in attribute naming.

    Notes
    -----
    - Node flood depth is sampled at the node coordinate.
    - Edge flood depth is defined as the maximum sampled depth along
      interpolated points on the edge geometry.
    """

    # Metadata of the raster
    meta = src.meta

    # Dictionary storing water depth per node
    dict_water_depth_node = {}

    for n in tqdm(G.nodes):
        # Extract raster row/column for the node lat/lon
        rows, cols = rs.transform.rowcol(
            meta['transform'],
            xs=[G.nodes[n]['x']],
            ys=[G.nodes[n]['y']]
        )

        # Read raster pixel at row and col
        w1 = src.read(1, window=Window(cols[0], rows[0], 1, 1))

        # Store flood depth value for node
        dict_water_depth_node[n] = {
            f'FUP_max_rp{rp}': float(w1[0][0])
        }

    # Attach node attributes to graph
    nx.set_node_attributes(G, dict_water_depth_node)

    # Build a GeoDataFrame for the edges
    df = pd.DataFrame()
    ids = []
    e0s = []
    e2s = []
    ekeys = []

    linestrings = []
    lengths = []

    # Extract edge properties
    for e in G.edges:
        ids.append(G.edges[e]['osmid'])
        e0s.append(e[0])
        e2s.append(e[1])
        ekeys.append(e[2])
        lengths.append(G.edges[e]['length'])

        # Use existing geometry if available; otherwise build a straight line
        if 'geometry' in G.edges[e]:
            linestrings.append(wkt.loads(G.edges[e]['geometry']))
        else:
            linestrings.append(
                LineString([
                    [G.nodes[e[0]]['x'], G.nodes[e[0]]['y']],
                    [G.nodes[e[1]]['x'], G.nodes[e[1]]['y']]
                ])
            )

    # Create GeoDataFrame in WGS84
    df['id'] = ids
    df['e0'] = e0s
    df['e1'] = e2s
    df['e2'] = ekeys
    df['length'] = lengths
    gdf = gpd.GeoDataFrame(df, geometry=linestrings, crs="EPSG:4326")

    # Reproject to EPSG:3857 for accurate length measurement in meter
    gdf3857 = gdf.to_crs("EPSG:3857")
    gdf['length2'] = gdf3857.length

    # Dictionary storing water depth per edge
    dict_water_depth = {}

    for i in tqdm(gdf3857.index):
        e = (gdf3857['e0'][i], gdf3857['e1'][i], gdf3857['e2'][i])
        length = gdf3857.length[i]
        line = gdf3857['geometry'][i]



        # Interpolated points along the edge for a given sampling interval
        distance_delta = 90 if length > 180 else length / 2
        distances = np.arange(0, line.length, distance_delta)
        points = [line.interpolate(distance) for distance in distances]

        # Create temporary GeoDataFrame
        gdf1 = gpd.GeoDataFrame(pd.DataFrame(), geometry=points, crs="EPSG:3857")
        gdf_nodes_wgs84 = gdf1.to_crs("EPSG:4326")

        # Extract lats/lons for interpolated points and convert to raster row/col
        lons = [pt.x for pt in gdf_nodes_wgs84['geometry'].tolist()]
        lats = [pt.y for pt in gdf_nodes_wgs84['geometry'].tolist()]
        rows, cols = rs.transform.rowcol(meta['transform'], xs=lons, ys=lats)

        # Collect sampled water depths along edge
        water_depth = [0.0]
        for j in range(len(rows)):
            w1 = src.read(1, window=Window(cols[j], rows[j], 1, 1))
            # Accept depth only if valid and not nodata
            if w1 and 0 <= w1[0][0] < 999:
                water_depth.append(w1[0][0])

        # Assign the maximum depth found along the edge
        dict_water_depth[e] = {
            f'FUP_max_rp{rp}': float(max(water_depth))
        }

    # Attach edge attributes to graph
    nx.set_edge_attributes(G, dict_water_depth)


if __name__=="__main__":
    G = nx.read_graphml("Nanjing_validation/nj_lite_elev.graphml")
    for rp in [5,10,20,50,75,100,200,250,500,1000]:
        src = rs.open(f'Nanjing_validation/Fathom_nj/FUP/nj_FUP_max_1in{rp}.tif')

        # Attach flood depth values to nodes and edges in graph G
        attach_flood(src, G, rp)

        # OPTIONAL DEBUG PRINTS
        for e in list(G.edges)[:100]:
            print(G.edges[e])
            print(G.nodes[e[0]])

    # Save the updated graph
    nx.write_graphml(G, "output.graphml")

edges = []
G = nx.read_graphml("output.graphml")
for e in tqdm(G.edges):
    if 'geometry' in G.edges[e]:
        # Convert the WKT string back into a Shapely object
        G.edges[e]['geometry'] = wkt.loads(G.edges[e]['geometry'])
    else:
        # If no geometry exists, construct a straight LineString
        # between the two node coordinates
        G.edges[e]['geometry'] = LineString([[G.nodes[e[0]]['x'], G.nodes[e[0]]['y']], [G.nodes[e[1]]['x'], G.nodes[e[1]]['y']]])
    edges.append(G.edges[e])
    # print(G.nodes[e[0]])


# Create GeoDataFrame
gdf = gpd.GeoDataFrame(edges, geometry='geometry', crs="EPSG:4326")

# Save as Shapefile
gdf.to_file("edges")