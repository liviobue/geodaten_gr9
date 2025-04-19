# main.py - Flask application for the geomarketing platform
from flask import Flask, render_template, request, jsonify
import geopandas as gpd
import pandas as pd
import json
import folium
from folium.plugins import HeatMap, MarkerCluster
import numpy as np
import os
from shapely.geometry import Point
from fuzzywuzzy import process
import pandas as pd

app = Flask(__name__)

def load_and_merge_income_data(municipalities):
    """Load income data and merge with municipalities using fuzzy matching, ignoring invalid income values."""
    try:
        # Load income data
        income_df = pd.read_csv('data/income_by_municipality_utf8.csv', header=None)
        income_df.columns = ['id', 'municipality_name', 'population', 'income']
        
        # Clean income data: remove quotes and commas
        income_df['income'] = income_df['income'].str.replace('"', '').str.replace(',', '')
        
        # Filter out rows where income is non-numeric (e.g., 'X')
        income_df = income_df[income_df['income'].str.replace('.', '', 1).str.isnumeric()]
        
        # Convert income to float
        income_df['income'] = income_df['income'].astype(float)
        
        # Normalize income for coloring (scale between 0 and 1)
        income_min = income_df['income'].min()
        income_max = income_df['income'].max()
        income_df['income_normalized'] = (
            (income_df['income'] - income_min) / (income_max - income_min)
            if income_max != income_min else 0
        )
        
        # Fuzzy matching to align municipality names
        municipality_names = municipalities['Gemeindename'].tolist()
        income_df['matched_name'] = income_df['municipality_name'].apply(
            lambda x: process.extractOne(x, municipality_names)[0] if pd.notna(x) else None
        )
        
        # Merge with municipalities GeoDataFrame
        merged = municipalities.merge(
            income_df[['matched_name', 'income', 'income_normalized']],
            left_on='Gemeindename',
            right_on='matched_name',
            how='left'
        )
        
        return merged
    
    except Exception as e:
        print(f"Error loading or merging income data: {e}")
        # Return municipalities without income data to prevent map failure
        return municipalities

def load_hotspots():
    """Load public hotspot locations"""
    hotspots = gpd.read_file('data/public_hotspots.geojson')
    return hotspots

def load_publicity_locations():
    """Load publicity/advertising locations"""
    publicity = gpd.read_file('data/publicity_locations.geojson')
    return publicity

def load_competitors():
    """Load competitor locations from JSON file"""
    with open('data/competitors.json') as f:
        competitors = json.load(f)
    
    # Convert to GeoDataFrame
    competitor_list = []
    for comp in competitors:
        competitor_list.append({
            'name': comp['name'],
            'address': comp['formatted_address'],
            'type': ', '.join(comp['types']),
            'rating': comp.get('rating', None),
            'geometry': Point(comp['geometry']['location']['lng'], 
                             comp['geometry']['location']['lat'])
        })
    
    return gpd.GeoDataFrame(competitor_list, crs="EPSG:4326")

# ----- Visualization Functions -----

def create_heatmap(data=None, weight_column=None, hotspots=None, publicity=None, competitors=None):
    """Create a base map with German-speaking Swiss municipalities and optional layers."""
    # Create a base map centered on Switzerland
    m = folium.Map(location=[46.8, 8.2], zoom_start=8)

    try:
        # Load municipalities from CSV
        csv_path = 'data/alle_deutschschweiz_gemeinden.csv'
        municipalities_df = pd.read_csv(csv_path)

        # Create geometry from Longitude and Latitude
        municipalities_df['geometry'] = municipalities_df.apply(
            lambda row: Point(row['Longitude'], row['Latitude']), axis=1
        )

        # Convert to GeoDataFrame
        german_municipalities = gpd.GeoDataFrame(
            municipalities_df,
            geometry='geometry',
            crs='EPSG:4326'
        )

        # Keep only the needed columns
        german_municipalities = german_municipalities[
            ['BFS-Nr', 'Gemeindename', 'Kantonskürzel', 'geometry']
        ].copy()
        german_municipalities['BFS-Nr'] = german_municipalities['BFS-Nr'].astype(str)

        # Merge with income data
        german_municipalities = load_and_merge_income_data(german_municipalities)

        # Define columns for GeoJSON based on available data
        geojson_columns = ['BFS-Nr', 'Gemeindename', 'Kantonskürzel', 'geometry']
        tooltip_fields = ['BFS-Nr', 'Gemeindename', 'Kantonskürzel']
        tooltip_aliases = ['BFS Number:', 'Name:', 'Canton:']

        # Check if income data is available
        if 'income' in german_municipalities.columns and 'income_normalized' in german_municipalities.columns:
            geojson_columns.extend(['income', 'income_normalized'])
            tooltip_fields.append('income')
            tooltip_aliases.append('Income (CHF):')

        # Add municipalities as CircleMarkers (since CSV provides points)
        fg_municipalities = folium.FeatureGroup(name="German-Speaking Municipalities")
        for _, row in german_municipalities.iterrows():
            if pd.notna(row.geometry):
                folium.CircleMarker(
                    location=[row.geometry.y, row.geometry.x],
                    radius=5,
                    color='#3388ff',
                    fill=True,
                    fill_color=(
                        '#FF0000' if pd.notna(row.get('income_normalized')) else '#D3D3D3'
                    ),
                    fill_opacity=(
                        row['income_normalized'] * 0.7 + 0.2
                        if pd.notna(row.get('income_normalized')) else 0.2
                    ),
                    weight=1,
                    popup=folium.Popup(
                        f"""
                        <b>{row['Gemeindename']}</b><br>
                        BFS Number: {row['BFS-Nr']}<br>
                        Canton: {row['Kantonskürzel']}<br>
                        Income (CHF): {row['income'] if pd.notna(row.get('income')) else 'N/A'}
                        """,
                        max_width=250
                    )
                ).add_to(fg_municipalities)
        fg_municipalities.add_to(m)

        # Add hotspots
        if hotspots is not None:
            fg_hotspots = folium.FeatureGroup(name="Public Hotspots")
            for _, row in hotspots.iterrows():
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

        # Add competitor locations
        if competitors is not None:
            fg_competitors = folium.FeatureGroup(name="Competitors")
            competitor_cluster = MarkerCluster(name="Competitor Cluster")
            for _, row in competitors.iterrows():
                folium.CircleMarker(
                    location=[row.geometry.y, row.geometry.x],
                    radius=5,
                    color='purple',
                    fill=True,
                    fill_opacity=0.7,
                    popup=f"""
                        <b>{row['name']}</b><br>
                        Address: {row['address']}<br>
                        Type: {row['type']}<br>
                        Rating: {row['rating'] if pd.notna(row['rating']) else 'N/A'}
                    """
                ).add_to(competitor_cluster)
            competitor_cluster.add_to(fg_competitors)
            fg_competitors.add_to(m)

        # Layer control
        folium.LayerControl().add_to(m)

    except Exception as e:
        print(f"Error processing municipalities from CSV: {e}")
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
    competitors = load_competitors()
    
    # Create map with layers
    m = create_heatmap(hotspots=hotspots, publicity=publicity, competitors=competitors)
    
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