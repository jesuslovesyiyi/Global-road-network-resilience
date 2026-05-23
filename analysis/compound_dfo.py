"""
Overview
--------
For each flood event in the Dartmouth Flood Observatory (DFO) archive, this
script extracts co-located fluvial (river discharge) and pluvial (rainfall)
time series from pre-computed station/pixel datasets, then computes a suite of
compound-flood statistics that quantify the **joint intensity and temporal
co-occurrence** of the two hazard drivers.
 
Pipeline
--------
1.  Load the DFO flood polygon archive (FloodArchive_region.shp).
2.  Load discharge (dis24) and rainfall (rain) time series for all continental
    sub-regions and concatenate into global arrays.
3.  For each DFO event:
        a. Identify the event's temporal window [BEGAN, ENDED].
        b. Spatially filter stations/pixels whose coordinates fall inside the
           event polygon.
        c. Slice the time series to the event window.
        d. Compute per-event summary statistics (global, per-pixel, per-day).
        e. Serialize the raw array pair as a compressed .npz file.
4.  Join computed stats back to DFO metadata and export a summary CSV.
5.  Optionally filter to events whose polygons intersect a set of study-area
    convex hulls (convex_hull_2566.shp).
 
Input Data
----------
DFO archive
    /scratch/users/zywei/flood_map/DFO/FloodArchive_region.shp
    Fields used: ID (int), BEGAN (YYYY-MM-DD), ENDED (YYYY-MM-DD), geometry
 
Discharge time series (one file per continental prefix)
    .../syn_station_ts_rp/{ct}_instant_glofas_all_rp_gumble.csv
    Columns: lon, lat, [metadata cols], {YYYY_MM_DD}...
    Values  : return-period exceedance probabilities (float); 1.5 sentinel
              encodes "exactly at the 2-year RP threshold" → recoded to 1.
 
Rainfall time series
    .../syn_station_ts_rain_rp/{ct}_rain_station_timeseries_rp_gumble.csv
    Same column convention as discharge files.
 
Study-area convex hulls (optional spatial filter)
    /scratch/users/zywei/convex_hulls_global/convex_hull_2566.shp
 
Outputs
-------
Per-event .npz files
    dfo_{ID:04d}_confusion_matrices_median_pair.npz
    Arrays: max_dis24 (fluvial RP matrix), rain_ts (pluvial RP matrix)
    Shape : (n_pixels, n_days)
 
Summary CSV (all processed events)
    dfo_compound_stats.csv
 
Summary CSV (events intersecting the 2,566 study-area hulls)
    dfo_compound_stats_in_2566.csv

Documentation Note: Portions of this documentation were drafted with the assistance of Claude (Anthropic)
and subsequently reviewed, edited, and verified for technical accuracy by the authors.
"""
import argparse
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from scipy.ndimage import maximum_filter1d
from tqdm import tqdm

# ── Helper Functions ──────────────────────────────────────────────────────────
def parse_col(c):
    """
    Parse a date column name of the form 'YYYY_MM_DD' into a pd.Timestamp.
 
    Column names in the discharge and rainfall CSVs encode daily timestamps as
    underscore-separated integers (e.g. '2010_08_15'). This function converts
    such a string to a pandas Timestamp for temporal filtering.
 
    Parameters
    ----------
    c : str
        Column name string, expected format 'YYYY_MM_DD'.
 
    Returns
    -------
    pd.Timestamp or None
        Parsed timestamp if the format is valid; None otherwise.
        Returning None (rather than raising) allows silent skipping of
        non-date metadata columns during bulk column parsing.
    """
    try:
        y, m, d = map(int, c.split("_"))
        return pd.Timestamp(year=y, month=m, day=d)
    except:
        return None

# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":

    # ── Argument parsing ──────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="Compute confusion matrices per DFO flood event")
    parser.add_argument("--size",
                        type=int,
                        default=10,
                        help="Size of maximum filter")
    
    args = parser.parse_args()
    
    size = args.size

    records = []  # one dict per DFO event

    # ── Load DFO Flood Archive ────────────────────────────────────────────────
    # The DFO Global Active Archive of Large Flood Events (Dartmouth Flood Observatory)
    # provides polygon boundaries, start/end dates, and metadata for major flood events worldwide. 
    # Each record represents a distinct flood event with a unique integer ID.
    dfo = gpd.read_file("/scratch/users/zywei/flood_map/DFO/FloodArchive_region.shp")

    # ── Load and Concatenate Discharge & Rainfall Time Series ─────────────────
    # Data are split by continental sub-region prefix. Both datasets store
    # return-period exceedance probabilities derived from GloFAS reanalysis
    # (discharge) and ERA5 (rainfall), fitted with a Gumbel distribution.
    #
    # Prefixes:
    #   af = Africa,  au = Australia/Oceania,  as = Asia,  eu = Europe,
    #   si = Siberia, sa = South America,       na = North America
    all_lists = ["af", "au", "as", "eu", "si", "sa", "na"]
    dis24_all = []
    rain_all = []
    for ct in tqdm(all_lists, desc="Loading data"):
        try:
            # Discharge: GloFAS instantaneous discharge return-period series
            d = pd.read_csv(
                f"/scratch/users/zywei/download_era_glofas/syn_station_ts_rp/{ct}_instant_glofas_all_rp_gumble.csv"
            )

            # Drop auto-generated pandas index columns from intermediate saves
            d = d.drop(columns=[col for col in ["Unnamed: 0.2", "Unnamed: 0.1", "Unnamed: 0"] if col in d.columns])
            dis24_all.append(d)

            # Rainfall: ERA5 daily rainfall return-period series
            r = pd.read_csv(
                f"/scratch/users/zywei/download_era_glofas/syn_station_ts_rain_rp/{ct}_rain_station_timeseries_rp_gumble.csv"
            )
            r = r.drop(columns=[col for col in ["Unnamed: 0.1", "Unnamed: 0"] if col in r.columns])
            rain_all.append(r)

        except FileNotFoundError:
            print(f"Skipping {ct}: file not found")


    # Concatenate all regions into single global DataFrames.
    # Row index is reset so spatial masking by boolean array aligns correctly.
    dis24_combined = pd.concat(dis24_all, ignore_index=True)
    rain_combined = pd.concat(rain_all, ignore_index=True)
    print(f"dis24 combined: {dis24_combined.shape}, rain combined: {rain_combined.shape}")

    # ── Pre-parse Date Columns ────────────────────────────────────────────────
    # Only columns present in BOTH datasets can be jointly sliced, so the
    # intersection of column names is used. Columns in dis24 beyond the first 7
    # (which are metadata: e.g. lon, lat, station ID, RP thresholds) are
    # treated as potential date columns.
    #
    # Parsed once here and reused inside the per-event loop for efficiency,
    # since this list is constant across all events.
    all_date_cols = [col for col in dis24_combined.columns[7:] if col in rain_combined.columns]
    date_ts = {} # Maps column name → pd.Timestamp
    for col in all_date_cols:
        try:
            date_ts[col] = parse_col(col)
        except Exception:
            pass
    
    parseable_date_cols = list(date_ts.keys())
    parsed_timestamps = sorted(date_ts.values())

    if parsed_timestamps:
        print(f"Date columns range: {parsed_timestamps[0].date()} -> {parsed_timestamps[-1].date()} ({len(parseable_date_cols)} columns)")
    else:
        raise ValueError("No parseable date columns found in combined data.")

    # ── Pre-build Global GeoSeries for Spatial Filtering ─────────────────────
    # Converting all station lon/lat coordinates to Point geometries once here
    # avoids recreating them inside the per-event loop (~4,000+ iterations).
    # The .within(polygon) call is then a vectorised operation over this
    # pre-built GeoSeries.
    dis24_points = gpd.GeoSeries([Point(xy) for xy in zip(dis24_combined["lon"], dis24_combined["lat"])])
    rain_points = gpd.GeoSeries([Point(xy) for xy in zip(rain_combined["lon"], rain_combined["lat"])])

    # Spatial resolution of the ERA5 rainfall grid (degrees).
    # Retained here for reference; used if grid-cell area weighting is added later.
    rain_pixel_size = 0.25


    # ═════════════════════════════════════════════════════════════════════════
    # Main Loop: Per-DFO-Event Processing
    # ═════════════════════════════════════════════════════════════════════════
    for i in tqdm(dfo.index, desc="DFO events"):
        event_id = int(dfo["ID"][i])

        # ── Parse event temporal window ───────────────────────────────────────
        # DFO dates are stored as 'YYYY-MM-DD' strings. Parse to Timestamp for
        # comparison against the pre-parsed date column timestamps.
        start_str = dfo["BEGAN"][i]
        y, m, d = map(int, start_str.split("-"))
        start = pd.Timestamp(year=y, month=m, day=d)

        end_str = dfo["ENDED"][i]
        y, m, d = map(int, end_str.split("-"))
        end = pd.Timestamp(year=y, month=m, day=d)

        polygon = dfo["geometry"][i]

        # ── Temporal filter: select columns within event window ────────────────
        # Only include date columns whose timestamp falls within [start, end]
        # (inclusive). Events outside the archive's date range are skipped.
        date_cols = [col for col in parseable_date_cols if start <= date_ts[col] <= end]
        if not date_cols:
            print(f"DFO {event_id:04d}: no date columns in [{start.date()}, {end.date()}], skipping")
            continue

        # ── Spatial filter: select stations/pixels inside event polygon ───────
        # .within() returns a boolean Series; .values converts to numpy array
        # for use as a boolean index on the combined DataFrame.
        dis_mask = dis24_points.within(polygon).values
        rain_mask = rain_points.within(polygon).values

        dis24 = dis24_combined[dis_mask].reset_index(drop=True)
        rain = rain_combined[rain_mask].reset_index(drop=True)

        # ── Extract time series arrays ────────────────────────────────────────
        # Shape: (n_pixels, n_days)
        # NaN entries indicate missing or masked data; replaced with 0.0 so
        # they do not influence peak/aggregation statistics.
        #
        # Sentinel value 1.5: used in the source data to flag pixels where the
        # return-period value equals exactly the 2-year RP threshold boundary.
        # Recoded to 1 (i.e., "at threshold") to avoid inflating statistics.
        dis_ts = dis24.loc[:, date_cols].to_numpy(dtype=float)
        dis_ts = np.where(np.isfinite(dis_ts), dis_ts, 0.0)
        dis_ts[dis_ts == 1.5] = 1

        # Aggregate multiple dis24 rows per rain pixel using median
        rain_ts = rain.loc[:, date_cols].to_numpy(dtype=float)
        rain_ts = np.where(np.isfinite(rain_ts), rain_ts, 0.0)
        rain_ts[rain_ts == 1.5] = 1

        # Skip events with no valid pixels after spatial/temporal filtering
        if dis_ts.size == 0 or rain_ts.size == 0:
            print(f"DFO {event_id:04d}: empty array after date filter (dis={dis_ts.shape}, rain={rain_ts.shape}), skipping")
            continue


        # ── Compute Summary Statistics ─────────────────────────────────────────
        # Four views of the data are computed for both hazard types:
        #
        #   f_flat / r_flat : full flattened array (all pixels × all days)
        #       → captures the global distribution across the entire event
        #
        #   f_px / r_px     : per-pixel maximum over time  (shape: n_pixels,)
        #       → characterises which locations experienced the most severe event
        #
        #   f_day / r_day   : per-day maximum over pixels  (shape: n_days,)
        #       → characterises the temporal evolution of peak intensity
        #
        # Statistics are computed at 4 levels: mean, median, max, 95th percentile.
        f_flat = dis_ts.flatten()
        r_flat = rain_ts.flatten()
        f_px   = dis_ts.max(axis=1)   # per-fluvial-pixel peak over time
        r_px   = rain_ts.max(axis=1)  # per-rain-pixel peak over time
        f_day  = dis_ts.max(axis=0)   # per-day peak over fluvial pixels
        r_day  = rain_ts.max(axis=0)  # per-day peak over rain pixels

        rec = {

            # ── Event identifier ──────────────────────────────────────────────
            "event_id": event_id,

            # ── Global statistics (all pixels × all days) ─────────────────────
            # Describe the overall intensity distribution of each hazard driver
            # across the entire spatial and temporal extent of the event.
            "fluvial_global_max":    f_flat.max(),
            "pluvial_global_max":    r_flat.max(),
            "fluvial_global_mean":   f_flat.mean(),
            "pluvial_global_mean":   r_flat.mean(),
            "fluvial_global_median": np.median(f_flat),
            "pluvial_global_median": np.median(r_flat),
            "fluvial_global_p95":    np.percentile(f_flat, 95),
            "pluvial_global_p95":    np.percentile(r_flat, 95),


            # ── Per-pixel peak statistics ─────────────────────────────────────
            # Summarise the distribution of *worst-day* RP values across pixels.
            # High values here indicate that many locations within the polygon
            # experienced a high-return-period event at some point.
            "fluvial_pixel_peak_mean":   f_px.mean(),
            "pluvial_pixel_peak_mean":   r_px.mean(),
            "fluvial_pixel_peak_median": np.median(f_px),
            "pluvial_pixel_peak_median": np.median(r_px),
            "fluvial_pixel_peak_max":    f_px.max(),
            "pluvial_pixel_peak_max":    r_px.max(),
            "fluvial_pixel_peak_p95":    np.percentile(f_px, 95),
            "pluvial_pixel_peak_p95":    np.percentile(r_px, 95),


            # ── Per-day peak statistics ───────────────────────────────────────
            # Summarise the distribution of *worst-pixel* RP values across days.
            # High values here indicate that on the most severe days, at least one
            # location had very high RP exceedance.
            "fluvial_day_peak_mean":     f_day.mean(),
            "pluvial_day_peak_mean":     r_day.mean(),
            "fluvial_day_peak_median":   np.median(f_day),
            "pluvial_day_peak_median":   np.median(r_day),
            "fluvial_day_peak_max":      f_day.max(),
            "pluvial_day_peak_max":      r_day.max(),
            "fluvial_day_peak_p95":      np.percentile(f_day, 95),
            "pluvial_day_peak_p95":      np.percentile(r_day, 95),


            # ── Compound and co-occurrence metrics ────────────────────────────
            # compound_day_frac     : fraction of event days on which BOTH a
            #   fluvial AND a pluvial signal are active (RP > 0) somewhere in
            #   the polygon. This is the primary compound-flood indicator.
            # fluvial_active_day_frac  : fraction of days with any fluvial signal.
            # pluvial_active_day_frac  : fraction of days with any pluvial signal.
            # fluvial_active_pixel_frac: fraction of pixels with any fluvial signal
            #   over the full event window.
            # pluvial_active_pixel_frac: analogous for rainfall pixels.
            # corr_temporal         : Pearson correlation between the daily
            #   fluvial and pluvial peak time series. Positive values indicate
            #   that discharge and rainfall peaks tend to occur on the same days
            #   (typical of flash floods); near-zero or negative values suggest
            #   asynchronous drivers (e.g., slow snowmelt vs. convective rain).
            #   Set to NaN if either series has zero variance (constant signal).
            "compound_day_frac":         float(np.mean((f_day > 0) & (r_day > 0))),
            "fluvial_active_day_frac":   float(np.mean(f_day > 0)),
            "pluvial_active_day_frac":   float(np.mean(r_day > 0)),
            "fluvial_active_pixel_frac": float(np.mean(f_px > 0)),
            "pluvial_active_pixel_frac": float(np.mean(r_px > 0)),
            "corr_temporal":             float(np.corrcoef(f_day, r_day)[0, 1]) if f_day.std() > 0 and r_day.std() > 0 else np.nan,

            # ── Dimensionality metadata ───────────────────────────────────────
            # Retained for quality control: very small pixel counts or very short
            # windows may yield unreliable statistics.
            "n_fluvial_pixels": dis_ts.shape[0],
            "n_pluvial_pixels": rain_ts.shape[0],
            "n_days":           dis_ts.shape[1],
        }
        records.append(rec)


        # ── Serialize raw array pair ───────────────────────────────────────────
        # The full (n_pixels × n_days) arrays are saved for downstream analysis
        # (e.g., confusion matrix computation, spatial visualisation).
        # Compressed NPZ format keeps file sizes manageable.
        out_path = f"/scratch/users/zywei/download_era_glofas/cms/dfo_{event_id:04d}_confusion_matrices_median_pair.npz"
        np.savez_compressed(out_path, max_dis24=dis_ts, rain_ts=rain_ts)
        print(f"DFO {event_id:04d}: saved -> {out_path}")


    # ═════════════════════════════════════════════════════════════════════════
    # Post-Processing: Assemble and Export Summary CSV
    # ═════════════════════════════════════════════════════════════════════════
 
    # Join computed compound-flood statistics with the original DFO metadata
    # (area, duration, severity, country, etc.) using event ID as the key.
    # geometry column is dropped to produce a plain tabular CSV.
    dfo_attrs = dfo.drop(columns="geometry").set_index("ID")

    df = pd.DataFrame(records)
    df = df.join(dfo_attrs, on="event_id")

    csv_path = "/scratch/users/zywei/download_era_glofas/dfo_compound_stats.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved summary DataFrame ({len(df)} events) -> {csv_path}")

    # ── Spatial Subset: Events Intersecting Study-Area Convex Hulls ───────────
    # Filter to DFO events whose polygon spatially intersects at least one of
    # the 2,566 urban study-area convex hulls. This subset is used in the
    # road-network resilience analysis where per-city flood exposure is needed.
    #
    # Method: spatial join (inner, predicate='intersects') between the processed
    # DFO event polygons and the convex hull polygons. Any DFO event touching at
    # least one hull is retained. Both layers are projected to EPSG:4326 first
    # to ensure CRS consistency.
    gis_data = gpd.read_file("/scratch/users/zywei/convex_hulls_global/convex_hull_2566.shp")
    gis_data = gis_data.to_crs("EPSG:4326")

    # Subset DFO to only events that were successfully processed (i.e., in df)
    dfo_processed = dfo[dfo["ID"].isin(df["event_id"])].copy().to_crs("EPSG:4326")

    # Spatial join: inner join keeps only DFO events that intersect ≥1 hull
    joined = gpd.sjoin(
        dfo_processed[["ID", "geometry"]],
        gis_data[["geometry"]],
        how="inner",
        predicate="intersects",
    )

    # Deduplicate: a single DFO polygon may intersect multiple hulls,
    # so unique() ensures each event appears only once in the filtered table.
    intersecting_ids = joined["ID"].unique()

    df_intersect = df[df["event_id"].isin(intersecting_ids)].copy()

    csv_path_intersect = "/scratch/users/zywei/download_era_glofas/dfo_compound_stats_in_2566.csv"
    df_intersect.to_csv(csv_path_intersect, index=False)
    print(f"Saved intersecting DataFrame ({len(df_intersect)} events) -> {csv_path_intersect}")
