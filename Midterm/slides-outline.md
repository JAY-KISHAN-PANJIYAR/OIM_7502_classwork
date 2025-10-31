# Slide Deck Outline — Bokeh Midterm (Jay Kishan Panjiyar)

## Slide 1 — Title & Overview
- **Advanced Programming Assignment: Midterm**
- **Library:** Bokeh
- **Presenter:** Jay Kishan Panjiyar
- **Demo App:** Nepal Earthquake Explorer
- Built using: Python, Pandas, GeoJSON, and Bokeh
- Run with: `bokeh serve --show nepal_explorer.py`

---

## Slide 2 — The Problem We’re Solving
- Nepal lies in a **seismically active zone** with frequent earthquakes.
- Problem: earthquake data is **raw, tabular, and hard to interpret visually.**
- **Goal:** “Turn 10 years of earthquake data into an interactive dashboard for spatial and temporal exploration.”
- **Target user:** Data scientists, analysts, and disaster response planners.

---

## Slide 3 — Datasets Used
### A.  Earthquake Dataset (2015–2025)
- File: `nepal_earthquakes_2015_2025.csv`
- Columns: `Date`, `Time`, `Latitude`, `Longitude`, `Magnitude`, `Depth_km`, `Place`
- Combined into unified `DateTime` column for analysis.

### B.  District Centroids
- File: `nepal_districts.csv`
- Columns: `District`, `lat`, `lon`
- Used to assign each earthquake to its nearest district.

### C. District Boundaries
- File: `nepal-districts-new.geojson`
- Contains polygon shapes for mapping district outlines.

---

## Slide 4 — Why This Matters
- Data scientists need tools combining:
  - **Interactivity** (filters for magnitude, time, district)
  - **Visualization** (maps + charts)
  - **Automation** (real-time updates)
- **Bokeh** enables all of this directly in Python — no JavaScript required.

---

## Slide 5 — Why Bokeh
- **Python-native**, integrates with Pandas
- `bokeh serve` enables live, reactive dashboards
- Built-in **widgets** and **callbacks**
- Great for data storytelling and analysis
- Clean separation between **data**, **UI**, and **logic**

---

## Slide 6 — App Architecture
- **Main script:** `nepal_explorer.py`
- **Core components:** CSVs, GeoJSON, and Bokeh visualizations
- **Workflow:**
  Data → ColumnDataSource → Widgets → Callback → Updated Plots
- **Flow diagram:**
  CSV + GeoJSON → Pandas → ColumnDataSource → Bokeh → Browser

---

## Slide 7 — Data Processing Functions
### Data Loading
```python
def load_earthquakes(), load_district_centroids(), load_geojson()
```
- Loads, cleans, and merges CSVs/GeoJSON.

### Nearest District
```python
def nearest_district(quakes, districts)
```
- Finds closest centroid per earthquake using latitude/longitude distance.

### Aggregation
```python
def aggregate_district_counts(filtered)
```
- Groups filtered data by district for frequency counts.

---

## Slide 8 — Visualization Code Explained
### Interactive Map
```python
p.circle(x="Longitude", y="Latitude", size=7, source=QUAKE_SOURCE)
```
- Circles represent earthquakes
- Color encodes magnitude
- Hover shows district, magnitude, depth, and timestamp

### Bar Chart
```python
p.vbar(x="District", top="Count", source=HIST_SOURCE)
```
- Displays top 15 districts by quake frequency
- Auto-updates when filters change

---

## Slide 9 — Widgets & Callbacks
### Widgets
- Magnitude Slider → filter by strength
- Date Range Slider → filter by time
- District Select → focus on specific area

### Callback
```python
def update_data(attr, old, new)
```
- Re-filters master dataset
- Updates map and bar chart sources dynamically

---

## Slide 10 — Dashboard Layout
- **Left panel:** Filters (magnitude, date, district)
- **Right panel:** Interactive Map and Bar Chart
- **Header:** “Advanced Programming Assignment: Midterm — Presenter: Jay Kishan Panjiyar”
- Layout built with `column()` and `row()`

---

## Slide 11 — Live Demo
1. Run: `bokeh serve --show nepal_explorer.py`
2. Adjust magnitude, date range, and district
3. Observe live updates in map and chart
4. Hover to inspect details
*(3–4 minutes total demo)*

---

## Slide 12 — Outcome & Learnings
- Built a fully interactive **geospatial dashboard**
- Demonstrated:
  - Linking Pandas data to visuals
  - Using GeoJSON in Bokeh
  - Real-time filtering with callbacks
- Showcases **data storytelling** for real-world applications

---

## Slide 13 — Future Enhancements
- Add OpenStreetMap basemap
- Scale circle size by magnitude
- Add export/download options
- Connect to real-time API
- Deploy on Render or Heroku

---

## Slide 14 — Closing & Q&A
- **Recap:**
  - Data: Earthquakes in Nepal (2015–2025)
  - Problem: Identify spatial & temporal patterns
  - Solution: Interactive Bokeh dashboard
- **Thank You!**
- Questions?
