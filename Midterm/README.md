# Bokeh Midterm Project — Nepal Earthquake Explorer

This repository contains the deliverables for the OIM 7502 Spring 2025 midterm project: **Exploring a Third-Party Python Package (Bokeh)**.

## 1. Project Description
We use **Bokeh** to build an **interactive, geospatial dashboard** that visualizes earthquakes in and around Nepal between **2015–2025**. The dashboard demonstrates Bokeh's core strengths:

- `ColumnDataSource` as the shared data model
- **linked widgets** (slider, date range, dropdown)
- **GeoJSON rendering** for district boundaries
- **server app** pattern using `bokeh serve`
- **data-science framing** (why would a DS care?)

Data sources (included):

- `nepal_earthquakes_2015_2025.csv`
- `nepal_districts.csv`
- `nepal-districts-new.geojson`

## 2. How to Run

```bash
# 0) create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# 1) install dependencies
pip install -r requirements.txt

# 2) run the Bokeh server
bokeh serve --show nepal_explorer.py
```

This will open the app in your browser at http://localhost:5006/nepal_explorer.

## 3. Files

- `nepal_explorer.py` — main Bokeh server app (with required docstring)
- `tutorial.md` — step-by-step explanation of Bokeh concepts we used
- `slides-outline.md` — outline for an in-class 10–12 minute presentation
- `requirements.txt` — Python packages to install
- `data/` — (optional) put your CSV/GeoJSON here if you don't want them in root

## 4. GitHub Submission
Push this whole folder to GitHub and submit the **repo URL** to Canvas, as required in the assignment.
