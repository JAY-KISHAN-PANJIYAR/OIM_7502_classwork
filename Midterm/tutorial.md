# Tutorial: Building an Interactive Bokeh App (Nepal Earthquake Dashboard)

## Goal
Show how to go from raw CSV + GeoJSON to a **Bokeh server app** with filters, an interactive map, and a linked bar chart.

---

## 1. Why Bokeh for Data Scientists?
- Native **Python-first** API (no JS required for 90% of use-cases)
- **Server mode** (`bokeh serve`) for apps that react to widgets
- Great for **explaining** models or geo patterns to non-technical stakeholders
- Integrates with `pandas` easily

---

## 2. Data Inputs
We use 3 files:

1. `nepal_earthquakes_2015_2025.csv` — has columns like:
   - `Date`, `Time`, `Magnitude`, `Depth_km`, `Longitude`, `Latitude`, `Place`
2. `nepal_districts.csv` — district **centroids** (`District`, `lat`, `lon`)
3. `nepal-districts-new.geojson` — polygon boundaries for districts (for the map)

We load them with `pandas.read_csv(...)` and `json.load(...)`.

---

## 3. Key Bokeh Concepts We Used

### 3.1 ColumnDataSource
- Central data container in Bokeh
- Lets multiple plots/widgets **share** the same data
- Updating `.data` triggers UI refresh

```python
MASTER_SOURCE = ColumnDataSource(df)      # never touched
VIEW_SOURCE = ColumnDataSource(df.copy()) # filtered
```

### 3.2 GeoJSONDataSource
- Special source for polygons / shapes
- Perfect for district-level maps
- Works well with `patches(...)`

```python
from bokeh.models import GeoJSONDataSource
geo_source = GeoJSONDataSource(geojson=geojson_string)
p.patches("xs", "ys", source=geo_source, ...)
```

### 3.3 Widgets + Callbacks
We used:
- `Slider` for minimum magnitude
- `DateRangeSlider` for time window
- `Select` for district

All 3 call **one** function: `update_data(...)`.

```python
for w in (magnitude_slider, date_slider, district_select):
    w.on_change("value", update_data)
```

### 3.4 Linked Views
After filtering the quake rows, we **recalculate** the district-frequency dataframe and push it into the bar chart source.

---

## 4. App Layout
We used `column(...)` and `row(...)` from `bokeh.layouts`:

- Header (title + presenter)
- Left: filters
- Right: map + bar chart


---

## 5. How to Extend
- Add a **tile provider** (OSM) for nicer basemap
- Add **magnitude-size** encoding on circles
- Add **export** button using `CustomJS`
- Deploy to Heroku / Render with `bokeh serve`

---

## 6. Mapping to Midterm Rubric
- **Slide deck** → use `slides-outline.md`
- **Tutorial** → this file
- **README with install** → done
- **Code examples** → in `nepal_explorer.py` (clean, PEP-8-ish)
- **Data-science relevance** → spatial patterns, frequency, filters
