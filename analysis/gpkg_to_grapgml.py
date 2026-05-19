"""
Convert a GeoPackage-based road network into a directed NetworkX graph
with preserved node and edge attributes.

This script reads node and edge layers from a GeoPackage-formatted OSM
network, constructs a directed multigraph, and transfers spatial and
non-spatial attributes to NetworkX-compatible formats. Geometry objects
are serialized as WKT strings, invalid or empty attributes are removed,
and the resulting graph is exported as a GraphML file for downstream
network analysis.
"""
from tqdm import tqdm
import pandas as pd
import geopandas as gpd
import networkx as nx

# Load node and edge layers from the GeoPackage
#   - "nodes": point features representing network nodes (intersections)
#   - "edges": line features representing directed road segments
nodes = gpd.read_file("LA_lite_elev.gpkg", layer="nodes")
edges = gpd.read_file("LA_lite_elev.gpkg", layer="edges")

# Create a directed multigraph
# MultiDiGraph allows:
#   - directionality (one-way streets)
#   - multiple parallel edges between the same node pair
G = nx.MultiDiGraph()

# -------------------------------------------------------------------
# Add nodes to the graph
# -------------------------------------------------------------------
for row in tqdm(nodes.itertuples(index=False), total=len(nodes)):
    data = row._asdict()

    # Extract required node id and coords
    osmid = data.pop("osmid")
    x = data.pop("x")
    y = data.pop("y")

    # Remove geometry 
    data.pop("geometry")

    # Drop empty, None, or NaN attributes
    data = {
        k: v
        for k, v in data.items()
        if v not in ("", None) and not pd.isna(v)
    }

    # Add node with coords and attributes
    G.add_node(osmid, x=x, y=y, **data)

# -------------------------------------------------------------------
# Add edges to the graph
# -------------------------------------------------------------------
for row in tqdm(edges.itertuples(index=False), total=len(edges)):
    data = row._asdict()

    # Extract required edge endpoints and id
    u = data.pop("u")                 
    v = data.pop("v")                 
    osmid = data.pop("osmid")          
    key = data.pop("key", None)        

    # Remove duplicate endpoint
    data.pop("from", None)
    data.pop("to", None)

    # Convert geometry to WKT string
    geom = data.pop("geometry", None)
    if geom is not None:
        data["geometry"] = geom.wkt

    # Drop empty, None, or NaN attributes
    data = {
        k: v
        for k, v in data.items()
        if v not in ("", None) and not pd.isna(v)
    }

    # Add edge with attributes
    G.add_edge(u, v, key=key, osmid=osmid, **data)

# Export graph to GraphML 
nx.write_graphml(G, "LA_lite_elev.graphml")