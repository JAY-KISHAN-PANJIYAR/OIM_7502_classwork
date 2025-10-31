"""Name:        Jay Kishan Panjiyar
Library:     Bokeh
URL:         https://docs.bokeh.org/en/latest/
Description:
This Bokeh app demonstrates how to build an interactive geospatial dashboard for Nepal
earthquakes (2015–2025). It loads tabular seismic data, joins it with district centroids,
renders a choropleth-style map over a GeoJSON boundary file, and links filters to update
both the map and a district-frequency bar chart. The goal is to show Bokeh's strengths for
data-science storytelling: ColumnDataSource, GeoJSONDataSource, callbacks, and layout.
"""




import json
import numpy as np
import pandas as pd

from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import (
    ColumnDataSource, Select, Slider, Div,
    GeoJSONDataSource, ColorBar, WMTSTileSource, HoverTool
)
from bokeh.plotting import figure
from bokeh.transform import linear_cmap
from bokeh.palettes import Viridis
from pyproj import Transformer

# ---------------------------------------------------------------------
# FILE PATHS
# ---------------------------------------------------------------------
QUAKE_CSV = "nepal_earthquakes_2015_2025.csv"
DISTRICT_CSV = "nepal_districts.csv"
NEPAL_GEOJSON = "nepal-districts-new.geojson"

NEPAL_LAT_MIN, NEPAL_LAT_MAX = 26.5, 30.7
NEPAL_LON_MIN, NEPAL_LON_MAX = 80.2, 88.3

WGS84_TO_WEBM = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------
def make_osm_tile():
    return WMTSTileSource(
        url="https://tile.openstreetmap.org/{Z}/{X}/{Y}.png",
        attribution="© OpenStreetMap contributors",
    )


def load_geojson(path: str) -> GeoJSONDataSource:
    with open(path, "r") as f:
        data = json.load(f)
    return GeoJSONDataSource(geojson=json.dumps(data))


def assign_district_by_nearest(quake_df: pd.DataFrame, dist_df: pd.DataFrame) -> pd.Series:
    dist_df = dist_df.copy()
    dist_df["lat"] = pd.to_numeric(dist_df["lat"], errors="coerce")
    dist_df["lon"] = pd.to_numeric(dist_df["lon"], errors="coerce")
    dist_df = dist_df.dropna(subset=["lat", "lon"])

    dist_lats = dist_df["lat"].to_numpy()
    dist_lons = dist_df["lon"].to_numpy()
    dist_names = dist_df["District"].astype(str).str.strip().tolist()

    assigned = []
    for lat, lon in zip(quake_df["Latitude"], quake_df["Longitude"]):
        # lon scaled so east-west isn’t over-weighted
        lat_rad = np.deg2rad(lat)
        lon_scale = np.cos(lat_rad)
        d2 = (dist_lats - lat) ** 2 + ((dist_lons - lon) * lon_scale) ** 2
        idx = int(np.argmin(d2))
        assigned.append(dist_names[idx])
    return pd.Series(assigned, index=quake_df.index)


def top_counts(df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame({"District": ["No Data"], "Count": [0]})
    c = df.groupby("District").size().reset_index(name="Count")
    return c.sort_values("Count", ascending=False).head(n)


# ---------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------
MAP_SOURCE = load_geojson(NEPAL_GEOJSON)

district_df = pd.read_csv(DISTRICT_CSV)
district_df["District"] = district_df["District"].astype(str).str.strip()

quake_df = pd.read_csv(QUAKE_CSV)

# datetime
if "Date" in quake_df.columns and "Time" in quake_df.columns:
    quake_df["Date"] = pd.to_datetime(
        quake_df["Date"] + " " + quake_df["Time"], errors="coerce"
    )
elif "Date" in quake_df.columns:
    quake_df["Date"] = pd.to_datetime(quake_df["Date"], errors="coerce")
else:
    quake_df["Date"] = pd.NaT

# keep only needed cols
quake_df = quake_df[["Latitude", "Longitude", "Magnitude", "Date"]].dropna()

# filter to nepal
quake_df = quake_df[
    (quake_df["Latitude"].between(NEPAL_LAT_MIN, NEPAL_LAT_MAX))
    & (quake_df["Longitude"].between(NEPAL_LON_MIN, NEPAL_LON_MAX))
].copy()

# year
quake_df["Year"] = quake_df["Date"].dt.year.fillna(-1).astype(int)

# assign district from CSV centroids
quake_df["District"] = assign_district_by_nearest(quake_df, district_df)

# project to web mercator
x_merc, y_merc = WGS84_TO_WEBM.transform(
    quake_df["Longitude"].to_numpy(),
    quake_df["Latitude"].to_numpy(),
)
quake_df["x_mercator"] = x_merc
quake_df["y_mercator"] = y_merc

EARTHQUAKE_DATA = quake_df

SOURCE = ColumnDataSource(EARTHQUAKE_DATA)
HISTO_SOURCE = ColumnDataSource(pd.DataFrame({"District": [], "Count": []}))

xmin = EARTHQUAKE_DATA["x_mercator"].min() - 30_000
xmax = EARTHQUAKE_DATA["x_mercator"].max() + 30_000
ymin = EARTHQUAKE_DATA["y_mercator"].min() - 80_000
ymax = EARTHQUAKE_DATA["y_mercator"].max() + 80_000
x_range = (xmin, xmax)
y_range = (ymin, ymax)


# ---------------------------------------------------------------------
# PLOTS
# ---------------------------------------------------------------------
def create_map_plot():
    mag_min = float(EARTHQUAKE_DATA["Magnitude"].min())
    mag_max = float(EARTHQUAKE_DATA["Magnitude"].max())
    mapper = linear_cmap("Magnitude", Viridis[7], mag_min, mag_max)

    p = figure(
        title="Earthquake Epicenters (2015–2025)",
        x_range=x_range,
        y_range=y_range,
        x_axis_type="mercator",
        y_axis_type="mercator",
        height=520,
        width=780,
        tools="pan,wheel_zoom,box_select,reset,save",
    )

    try:
        p.add_tile(make_osm_tile())
    except Exception as e:
        print("tile load failed:", e)

    p.patches(
        "xs",
        "ys",
        source=MAP_SOURCE,
        line_color="black",
        line_width=0.5,
        fill_color="#D9D9D9",
        fill_alpha=0.35,
    )

    r = p.scatter(
        "x_mercator",
        "y_mercator",
        source=SOURCE,
        size=7,
        color=mapper,
        line_color="black",
        line_width=0.2,
        alpha=0.9,
    )

    hover = HoverTool(
        renderers=[r],
        tooltips=[
            ("District", "@District"),
            ("Magnitude", "@Magnitude{0.0}"),
            ("Date", "@Date{%F %H:%M}"),
            ("Lat, Lon", "(@Latitude, @Longitude)"),
        ],
        formatters={"@Date": "datetime"},
    )
    p.add_tools(hover)

    p.add_layout(ColorBar(color_mapper=mapper["transform"], location=(0, 0)), "right")

    p.grid.grid_line_color = None
    p.xaxis.visible = False
    p.yaxis.visible = False

    return p


def create_histogram_plot():
    df_counts = top_counts(SOURCE.to_df(), 15)
    HISTO_SOURCE.data = df_counts.to_dict(orient="list")
    p_hist = figure(
        x_range=df_counts["District"].tolist(),
        height=300,
        width=780,
        title="Top Districts by Quake Count",
    )
    p_hist.vbar(x="District", top="Count", width=0.6, source=HISTO_SOURCE, color="#324784")
    p_hist.y_range.start = 0
    p_hist.xaxis.major_label_orientation = 0.9
    return p_hist


p_map = create_map_plot()
p_hist = create_histogram_plot()


# ---------------------------------------------------------------------
# FILTERS
# ---------------------------------------------------------------------
def apply_all_filters():
    df = EARTHQUAKE_DATA.copy()
    if year_select.value != "ALL":
        df = df[df["Year"] == int(year_select.value)]
    df = df[df["Magnitude"] >= magnitude_slider.value]
    if district_select.value != "ALL":
        df = df[df["District"] == district_select.value]
    return df


def update_from_widgets(attr, old, new):
    df = apply_all_filters()
    SOURCE.data = df.to_dict(orient="list")
    df_counts = top_counts(df, 15)
    HISTO_SOURCE.data = df_counts.to_dict(orient="list")
    p_hist.x_range.factors = df_counts["District"].tolist()


def selection_callback(attr, old, new):
    if SOURCE.selected.indices:
        df = SOURCE.to_df().iloc[SOURCE.selected.indices]
    else:
        df = SOURCE.to_df()
    df_counts = top_counts(df, 15)
    HISTO_SOURCE.data = df_counts.to_dict(orient="list")
    p_hist.x_range.factors = df_counts["District"].tolist()


# ---------------------------------------------------------------------
# WIDGETS
# ---------------------------------------------------------------------
year_vals = sorted([int(y) for y in EARTHQUAKE_DATA["Year"].unique() if y > 0])
year_select = Select(
    title="Filter by Year",
    value="ALL",
    options=["ALL"] + [str(y) for y in year_vals],
)

magnitude_slider = Slider(
    start=float(EARTHQUAKE_DATA["Magnitude"].min()),
    end=float(EARTHQUAKE_DATA["Magnitude"].max()) + 0.1,
    value=float(EARTHQUAKE_DATA["Magnitude"].min()),
    step=0.1,
    title="Minimum Magnitude",
)

district_options = ["ALL"] + sorted(
    district_df["District"].astype(str).str.strip().unique().tolist()
)
district_select = Select(
    title="Filter by District",
    value="ALL",
    options=district_options,
)

year_select.on_change("value", update_from_widgets)
magnitude_slider.on_change("value", update_from_widgets)
district_select.on_change("value", update_from_widgets)
SOURCE.selected.on_change("indices", selection_callback)


# ---------------------------------------------------------------------
# LAYOUT / HEADER
# ---------------------------------------------------------------------
header = Div(
    text="""
    <div style="background:#006747; color:white; padding:18px 22px; border-radius:10px; margin-bottom:10px;">
        <h1 style="margin:0; font-size:24px;">Nepal Geospatial Earthquake Explorer</h1>
        <p style="margin:4px 0 0 0; font-size:14px;">
            Advanced Programming Assignment: <b>Midterm</b> &nbsp;|&nbsp; Presenter: <b>Jay Kishan Panjiyar</b>
        </p>
    </div>
    """,
    width=1100,
)

filters_col = column(
    Div(text="<h3 style='margin-top:0;'>Filters</h3>"),
    year_select,
    magnitude_slider,
    district_select,
    width=250,
)

right_col = column(
    Div(text="<h3 style='margin-top:0;'>Interactive Map</h3>"),
    p_map,
    Div(text="<h3>District Frequency</h3>"),
    p_hist,
)

layout = column(
    header,
    row(filters_col, right_col),
)

curdoc().add_root(layout)
curdoc().title = "Nepal Earthquake Dashboard"
