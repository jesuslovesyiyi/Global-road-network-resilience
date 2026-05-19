"""
Assign speed limits and travel times to OSM road network edges based on
highway classification.

This script parses heterogeneous OSM 'highway' tags, assigns free-flow
speeds (m/s) using a reference dictionary, removes unsupported road
types, and computes edge-level travel times.
"""

import ast
import networkx as nx
import pickle

def extract_highway(items):
    """
    Normalize a list of OSM highway attributes into a flat list of strings.

    Parameters
    ----------
    items : iterable
        Collection of highway attribute values (strings, lists, or list-strings).

    Returns
    -------
    list
        Flattened list of highway type strings.
    """    
    result = []
    for item in items:
        if isinstance(item, str):
            item = item.strip()

            # Case 1: string looks like a Python list
            if item.startswith("[") and item.endswith("]"):
                try:
                    parsed = ast.literal_eval(item)  # safely parse list-string
                    # extend only if parsed result is iterable
                    if isinstance(parsed, (list, tuple)):
                        result.extend(parsed)
                    else:
                        result.append(parsed)
                except Exception:
                    # fallback: treat as plain string
                    result.append(item)
            else:
                # Case 2: plain string
                result.append(item)

        else:
            # Non-string items (real lists, tuples)
            if isinstance(item, (list, tuple)):
                result.extend(item)
            else:
                result.append(item)

    return result

def extract_types(item):
    """
    Return a list of candidate highway types from a single highway attribute.

    Handles both plain strings and string-encoded lists.
    """
    if isinstance(item, str) and item.startswith("[") and item.endswith("]"):
        try:
            return ast.literal_eval(item)   # safely parse list-like string
        except Exception:
            return [item]
    return [item]  # plain string

def pick_highway_type(item, lookup_dict):
    """
    Select the first highway type that appears in the reference speed dictionary.

    Parameters
    ----------
    item : str | list
        Raw highway attribute from OSM.
    lookup_dict : dict
        Dictionary mapping highway types to reference speeds.

    Returns
    -------
    str or None
        Matched highway type, or None if no match is found.
    """
    candidates = extract_types(item)
    for t in candidates:
        if t in highway_ms_dict.keys():
            return t
    return None   # nothing matched

if __name__ == "__main__":
    # Set home directory
    home_dir = '/Users/yiyi/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology/Research/Global road network resilience/01_data' # CURA
    home_dir = '/Users/yiyi/Library/CloudStorage/OneDrive-GeorgiaInstituteofTechnology(2)/Research/Global road network resilience/01_data' # SCARP

    # Load nanjing road network
    G_nj_flooded = nx.read_graphml(home_dir + '/Nanjing_validation/nj_lite_elev_fathom10.graphml')

    # Highway class unique values
    highway_class_dict = nx.get_edge_attributes(G_nj_flooded,'highway')
    highway_class_lst = []
    for item in highway_class_dict.values():
        highway_class_lst.append(item)
    
    # Reference free-flow speeds by OSM highway class (units: m/s)
    # Values correspond to typical design speeds
    highway_ms_dict = {
        'motorway': 33.33, # m/s =120mph
        'motorway_link': 33.33, #m/s =120mph
        'trunk': 27.78, #m/s =100mph
        'trunk_link': 27.78, #m/s =100mph
        'primary': 25, #m/s =90kph
        'primary_link': 25, #m/s =90kph
        'secondary': 22.22, #m/s =80kph
        'secondary_link': 22.22, #m/s =80kph
        'tertiary': 16.67, #m/s =60kph
        'tertiary_link': 16.67 #m/s =60kph
    }

    # Add speed limit to edges
    for i,j, data in G_nj_flooded.edges.data():
        highway = data['highway']
        highway_type = pick_highway_type(highway, highway_ms_dict)
        
        # Skip road segments without a recognized highway type
        if highway_type == None:
            continue
        else:
            highway_speed = highway_ms_dict[highway_type]
            data['ms'] = highway_speed

    # Remove edges that does not have 'ms' speed attribute, that is the road types does not belong to the highway speed reference dict
    G_nj_flooded_speed = G_nj_flooded.copy()

    # Check if all edges have speed
    for i,j,data in G_nj_flooded.edges.data():
        try:
            a = data['ms']
        except KeyError:
            G_nj_flooded_speed.remove_edge(i, j)
    
    # Save intermediate graphs
    with open(home_dir + '/Nanjing_validation/G_nj_flooded.pk', 'wb') as handle:
        pickle.dump(G_nj_flooded, handle, protocol=2)

    with open(home_dir + '/Nanjing_validation/G_nj_flooded_speed.pk', 'wb') as handle:
        pickle.dump(G_nj_flooded_speed, handle, protocol=2)

    # Add travel time (unit: seconds)
    for i,j, data in G_nj_flooded_speed.edges.data():
        data['travel_time'] = float(data['length'])/data['ms']
    
    # Save final graph with travel time attribute
    with open(home_dir + '/Nanjing_validation/G_nj_flooded_speed_time.pk', 'wb') as handle:
        pickle.dump(G_nj_flooded_speed, handle, protocol=2)