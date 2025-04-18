# main.py - Flask application for the geomarketing platform

from flask import Flask, render_template, request, jsonify
import geopandas as gpd
import pandas as pd
import json
import folium
from folium.plugins import HeatMap
import numpy as np
import os

app = Flask(__name__)

# ----- Data Loading Functions -----

def load_hotspots():
    """Load public hotspot locations"""
    hotspots = gpd.read_file('data/public_hotspots.geojson')
    return hotspots

def load_publicity_locations():
    """Load publicity/advertising locations"""
    publicity = gpd.read_file('data/publicity_locations.geojson')
    return publicity



# ----- Visualization Functions -----

def create_heatmap(data=None, weight_column=None, hotspots=None, publicity=None):
    """Create a base map with German-speaking Swiss municipalities and optional layers."""
    # Create a base map centered on Switzerland
    m = folium.Map(location=[46.8, 8.2], zoom_start=8)

    try:
        # Load municipalities
        gdb_path = 'data/swissBOUNDARIES3D_1_4_LV95_LN02.gdb'
        municipalities = gpd.read_file(gdb_path, layer='TLM_HOHEITSGEBIET')
        swiss_municipalities = municipalities[municipalities['ICC'] == 'CH']

        # Filter for German-speaking municipalities
        bfs_ranges = [
            (1, 299), (301, 999), (1001, 1199), (1201, 1299), (1301, 1399), (1401, 1499), 
            (1501, 1599), (1601, 1699), (1701, 1999), (2401, 2699), (2701, 2759), 
            (2761, 2899), (2901, 2999), (3001, 3099), (3101, 3199), (3201, 3499), 
            (3501, 3999), (4001, 4399), (4401, 4999),
        ]

        german_filter = False
        for start, end in bfs_ranges:
            german_filter = german_filter | ((swiss_municipalities['BFS_NUMMER'] >= start) & 
                                             (swiss_municipalities['BFS_NUMMER'] <= end))

        # Apply the filter to get German-speaking municipalities
        german_municipalities = swiss_municipalities[german_filter].copy()
        
        # Keep only the needed columns
        german_municipalities = german_municipalities[['BFS_NUMMER', 'NAME', 'KANTONSNUMMER', 'geometry']].copy()
        german_municipalities['BFS_NUMMER'] = german_municipalities['BFS_NUMMER'].astype(str)

        # Add municipalities
        folium.GeoJson(
            german_municipalities[['BFS_NUMMER', 'NAME', 'KANTONSNUMMER', 'geometry']],
            style_function=lambda x: {
                'fillColor': 'transparent',
                'color': '#3388ff',
                'weight': 1,
                'fillOpacity': 0
            },
            name='German-Speaking Municipalities',
            tooltip=folium.features.GeoJsonTooltip(
                fields=['BFS_NUMMER', 'NAME', 'KANTONSNUMMER'],
                aliases=['BFS Number:', 'Name:', 'Canton:'],
                localize=True
            )
        ).add_to(m)

        # Add hotspots
        if hotspots is not None:
            fg_hotspots = folium.FeatureGroup(name="Public Hotspots")
            for _, row in hotspots.iterrows():
                # Get centroid for polygon features or direct coords for points
                if row.geometry.geom_type == 'Point':
                    coords = [row.geometry.y, row.geometry.x]
                else:
                    centroid = row.geometry.centroid
                    coords = [centroid.y, centroid.x]
                
                folium.CircleMarker(
                    location=coords,
                    radius=5,
                    color='red',
                    fill=True,
                    fill_opacity=0.7,
                    popup=str(row.get("name", "Hotspot"))
                ).add_to(fg_hotspots)
            fg_hotspots.add_to(m)

        # Add publicity locations
        if publicity is not None:
            fg_publicity = folium.FeatureGroup(name="Publicity Locations")
            for _, row in publicity.iterrows():
                # Get centroid for polygon features or direct coords for points
                if row.geometry.geom_type == 'Point':
                    coords = [row.geometry.y, row.geometry.x]
                else:
                    centroid = row.geometry.centroid
                    coords = [centroid.y, centroid.x]
                
                folium.CircleMarker(
                    location=coords,
                    radius=5,
                    color='green',
                    fill=True,
                    fill_opacity=0.7,
                    popup=str(row.get("name", "Ad Location"))
                ).add_to(fg_publicity)
            fg_publicity.add_to(m)

        # Layer control
        folium.LayerControl().add_to(m)

    except Exception as e:
        print(f"Error loading municipalities from geodatabase: {e}")
        import traceback
        traceback.print_exc()

    return m

# ----- Flask Routes -----

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/get_map')
def get_map():
    """Generate and return map with German-speaking Swiss municipalities"""
    # Load hotspot and publicity data
    hotspots = load_hotspots()
    publicity = load_publicity_locations()
    
    # Create map with layers
    m = create_heatmap(hotspots=hotspots, publicity=publicity)
    
    # Save map to HTML and return it
    map_path = 'templates/maps/german_municipalities_map.html'
    os.makedirs('templates/maps', exist_ok=True)
    m.save(map_path)
    
    return render_template('maps/german_municipalities_map.html')

@app.route('/api/statistics')
def get_statistics():
    """Get statistics for different segments"""
    # Load all data
    merged_data = merge_datasets()
    hotspots = load_hotspots()
    publicity = load_publicity_locations()
    
    # Apply all weightings
    data = kmu_weighting(merged_data, hotspots, publicity)
    data = handwerk_weighting(data, hotspots, publicity)
    data = retail_gastro_weighting(data, hotspots, publicity)
    data = service_weighting(data, hotspots, publicity)
    data = tourism_weighting(data, hotspots, publicity)
    data = startup_weighting(data, hotspots, publicity)
    
    # Calculate top 10 municipalities for each segment
    top_municipalities = {}
    
    for segment, column in [
        ('KMU', 'kmu_weight'),
        ('Handwerk', 'handwerk_weight'),
        ('Retail & Gastro', 'retail_gastro_weight'),
        ('Dienstleistungen', 'service_weight'),
        ('Tourismus', 'tourism_weight'),
        ('Startups', 'startup_weight')
    ]:
        top = data.sort_values(column, ascending=False).head(10)
        top_municipalities[segment] = [
            {'name': row['region_name'], 'weight': float(row[column])} 
            for _, row in top.iterrows()
        ]
    
    return jsonify(top_municipalities)

if __name__ == '__main__':
    # Create required directories
    os.makedirs('templates/maps', exist_ok=True)
    
    # Start the application
    app.run(debug=True)