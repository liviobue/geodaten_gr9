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

def load_municipality_data():
    """Load municipality boundaries and demographic data"""
    # Try to load a GeoJSON first if it exists
    if os.path.exists('data/municipalities.geojson'):
        try:
            municipalities = gpd.read_file('data/municipalities.geojson')
            return municipalities
        except Exception as e:
            print(f"Error loading municipalities GeoJSON: {e}")
    
    # If QMD file exists but GeoJSON doesn't, create sample data
    if os.path.exists('data/municipalities.qmd'):
        print("QMD file found but GeoJSON format is required.")
        print("Creating sample municipality data...")
        
        # Create simple polygon geometries for testing
        municipalities = []
        for i in range(1, 12):
            # Create a simple square polygon for each municipality
            x_base = 8.0 + (i % 4) * 0.2
            y_base = 47.0 + (i // 4) * 0.2
            
            # Simple polygon (square)
            polygon_coords = [
                [x_base, y_base],
                [x_base + 0.1, y_base],
                [x_base + 0.1, y_base + 0.1],
                [x_base, y_base + 0.1],
                [x_base, y_base]  # Close the polygon
            ]
            
            municipalities.append({
                'type': 'Feature',
                'properties': {
                    'id': str(i),  # Convert ID to string for consistent data types
                    'name': f'Municipality {i}'
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [polygon_coords]
                }
            })
        
        # Create GeoJSON structure
        geojson = {
            'type': 'FeatureCollection',
            'features': municipalities
        }
        
        # Save to file
        with open('data/municipalities.geojson', 'w') as f:
            json.dump(geojson, f)
        
        # Load the created GeoJSON
        municipalities = gpd.read_file('data/municipalities.geojson')
        return municipalities
    
    # If no data exists, create a minimal sample
    print("No municipality data found. Creating minimal sample...")
    # Create a simple square for Switzerland
    polygon = {
        'type': 'Polygon',
        'coordinates': [[[6.0, 46.0], [10.0, 46.0], [10.0, 48.0], [6.0, 48.0], [6.0, 46.0]]]
    }
    municipalities = gpd.GeoDataFrame(
        {'id': ['1'], 'name': ['Switzerland']},
        geometry=[gpd.GeoSeries.from_wkt(['POLYGON ((6 46, 10 46, 10 48, 6 48, 6 46))'])[0]]
    )
    return municipalities

def load_income_data():
    """Load income data from CSV"""
    try:
        # Try different encodings common for German text files
        income_data = pd.read_csv('data/income_by_municipality.csv', 
                                 skiprows=3,
                                 encoding='latin1')  # Try latin1 (ISO-8859-1) encoding
    except Exception as e:
        print(f"Error with latin1 encoding: {e}")
        try:
            # Try with a different encoding if latin1 fails
            income_data = pd.read_csv('data/income_by_municipality.csv', 
                                     skiprows=3,
                                     encoding='ISO-8859-15')
        except Exception as e:
            print(f"Error with ISO-8859-15 encoding: {e}")
            try:
                # As a last resort, try with utf-8 and error handling
                income_data = pd.read_csv('data/income_by_municipality.csv', 
                                         skiprows=3,
                                         encoding='utf-8',
                                         errors='replace')
            except Exception as e:
                print(f"Fatal error loading income data: {e}")
                # Return an empty DataFrame with the expected columns
                return pd.DataFrame(columns=['region_id', 'region_name', 'income_total_mio', 'income_per_taxpayer'])
    
    # Clean column names and handle the format from your example
    income_data.columns = ['region_id', 'region_name', 'income_total_mio', 'income_per_taxpayer']
    
    # Convert region_id to string to match municipality id data type
    income_data['region_id'] = income_data['region_id'].astype(str)
    
    # Handle missing values and non-numeric data
    # Remove currency symbols and commas in numbers
    if 'income_total_mio' in income_data.columns:
        income_data['income_total_mio'] = income_data['income_total_mio'].astype(str).str.replace('"', '').str.replace(',', '').str.replace('\'', '')
        income_data['income_total_mio'] = pd.to_numeric(income_data['income_total_mio'], errors='coerce')
    
    if 'income_per_taxpayer' in income_data.columns:
        income_data['income_per_taxpayer'] = income_data['income_per_taxpayer'].astype(str).str.replace('"', '').str.replace(',', '').str.replace('\'', '')
        income_data['income_per_taxpayer'] = pd.to_numeric(income_data['income_per_taxpayer'], errors='coerce')
    
    return income_data

def load_hotspots():
    """Load public hotspot locations"""
    hotspots = gpd.read_file('data/public_hotspots.geojson')
    return hotspots

def load_publicity_locations():
    """Load publicity/advertising locations"""
    publicity = gpd.read_file('data/publicity_locations.geojson')
    return publicity

# ----- Data Processing Functions -----

def merge_datasets():
    """Merge all datasets for analysis"""
    municipalities = load_municipality_data()
    income_data = load_income_data()
    
    # Ensure ID columns are strings
    municipalities['id'] = municipalities['id'].astype(str)
    income_data['region_id'] = income_data['region_id'].astype(str)
    
    # Merge income data with municipality boundaries
    try:
        merged_data = municipalities.merge(income_data, left_on='id', right_on='region_id', how='left')
        return merged_data
    except Exception as e:
        print(f"Error merging datasets: {e}")
        # If there's an error in merging, return just the municipalities data
        municipalities['income_per_taxpayer'] = 80000  # Default value
        return municipalities

def normalize_data(data, column):
    """Normalize data column to 0-1 range"""
    min_val = data[column].min()
    max_val = data[column].max()
    return (data[column] - min_val) / (max_val - min_val)

def calculate_distance_weight(points_gdf, target_gdf, max_distance=10000):
    """Calculate weight based on distance to points of interest"""
    # Convert distance to weight (closer = higher weight)
    results = []
    
    for idx, municipality in target_gdf.iterrows():
        distances = []
        for _, point in points_gdf.iterrows():
            distance = municipality.geometry.distance(point.geometry)
            distances.append(distance)
        
        # Get minimum distance to any point
        min_distance = min(distances) if distances else max_distance
        
        # Convert to weight (inverse relationship)
        weight = 1 - (min(min_distance, max_distance) / max_distance)
        results.append(weight)
    
    return results

# ----- Weighting Models for Different Customer Segments -----

def kmu_weighting(data, hotspots, publicity):
    """Weight calculation for SMEs and Commercial Businesses"""
    # Normalize income (middle to upper income areas are target)
    data['income_normalized'] = normalize_data(data, 'income_per_taxpayer')
    
    # Preference for middle to upper income areas (bell curve)
    data['income_weight'] = 1 - 2 * abs(data['income_normalized'] - 0.7)
    data['income_weight'] = data['income_weight'].clip(0, 1)
    
    # Distance to hotspots (business centers)
    data['hotspot_weight'] = calculate_distance_weight(hotspots, data)
    
    # Calculate final weight
    data['kmu_weight'] = (
        0.5 * data['income_weight'] +
        0.5 * data['hotspot_weight']
    )
    
    return data

def handwerk_weighting(data, hotspots, publicity):
    """Weight calculation for Craft Businesses"""
    # Normalize income (middle income areas are target)
    data['income_normalized'] = normalize_data(data, 'income_per_taxpayer')
    
    # Bell curve centered on middle income
    data['income_weight'] = 1 - 2 * abs(data['income_normalized'] - 0.5)
    data['income_weight'] = data['income_weight'].clip(0, 1)
    
    # Distance to residential areas (using hotspots as proxy)
    data['residential_weight'] = calculate_distance_weight(hotspots, data)
    
    # Calculate final weight
    data['handwerk_weight'] = (
        0.6 * data['income_weight'] +
        0.4 * data['residential_weight']
    )
    
    return data

def retail_gastro_weighting(data, hotspots, publicity):
    """Weight calculation for Retail & Gastronomy"""
    # High foot traffic areas are most important
    data['hotspot_weight'] = calculate_distance_weight(hotspots, data)
    
    # Income is less important but still relevant
    data['income_normalized'] = normalize_data(data, 'income_per_taxpayer')
    
    # Calculate final weight
    data['retail_gastro_weight'] = (
        0.7 * data['hotspot_weight'] +
        0.3 * data['income_normalized']
    )
    
    return data

def service_weighting(data, hotspots, publicity):
    """Weight calculation for Service Providers"""
    # Higher income areas
    data['income_normalized'] = normalize_data(data, 'income_per_taxpayer')
    
    # Business districts (using hotspots as proxy)
    data['business_weight'] = calculate_distance_weight(hotspots, data)
    
    # Calculate final weight
    data['service_weight'] = (
        0.6 * data['income_normalized'] +
        0.4 * data['business_weight']
    )
    
    return data

def tourism_weighting(data, hotspots, publicity):
    """Weight calculation for Tourism Industry"""
    # Tourist hotspots (using public hotspots as proxy)
    data['tourist_weight'] = calculate_distance_weight(hotspots, data)
    
    # Income is less relevant for tourism
    data['income_normalized'] = normalize_data(data, 'income_per_taxpayer')
    
    # Calculate final weight
    data['tourism_weight'] = (
        0.8 * data['tourist_weight'] +
        0.2 * data['income_normalized']
    )
    
    return data

def startup_weighting(data, hotspots, publicity):
    """Weight calculation for Startups and Young Companies"""
    # Innovation hubs (using hotspots as proxy)
    data['innovation_weight'] = calculate_distance_weight(hotspots, data)
    
    # Income (middle to upper-middle)
    data['income_normalized'] = normalize_data(data, 'income_per_taxpayer')
    data['income_weight'] = 1 - 2 * abs(data['income_normalized'] - 0.6)
    data['income_weight'] = data['income_weight'].clip(0, 1)
    
    # Calculate final weight
    data['startup_weight'] = (
        0.5 * data['innovation_weight'] +
        0.5 * data['income_weight']
    )
    
    return data

# ----- Visualization Functions -----

def create_heatmap(data, weight_column, hotspots=None, publicity=None):
    """Create a folium heatmap for a given weight column"""
    # Create a base map centered on Switzerland
    m = folium.Map(location=[46.8, 8.2], zoom_start=8)
    
    # Add municipality choropleth as a base layer
    folium.Choropleth(
        geo_data=data.__geo_interface__,
        data=data,
        columns=['id', weight_column],  # Make sure this matches your data columns
        key_on='feature.properties.id',
        fill_color='YlOrRd',
        fill_opacity=0.5,
        line_opacity=0.2,
        legend_name=f'Weight for {weight_column}'
    ).add_to(m)
    
    # Create heatmap data - we need to convert polygon data to points with weights
    heatmap_data = []
    
    # Add centroids of municipalities with their weights to the heatmap
    for idx, row in data.iterrows():
        try:
            # Use centroid of each municipality
            centroid = row.geometry.centroid
            # Get weight value - handle potential missing values
            if weight_column in row and pd.notnull(row[weight_column]):
                weight = float(row[weight_column])  # Ensure it's a float
            else:
                weight = 0.5  # Default weight
            
            # Add point with its weight
            heatmap_data.append([float(centroid.y), float(centroid.x), weight])
        except Exception as e:
            print(f"Error processing row {idx}: {e}")
            continue
    
    # Add hotspots with high weight if provided
    if hotspots is not None:
        for _, row in hotspots.iterrows():
            try:
                if row.geometry.geom_type == 'Point':
                    location = [float(row.geometry.y), float(row.geometry.x)]
                else:
                    centroid = row.geometry.centroid
                    location = [float(centroid.y), float(centroid.x)]
                # Give hotspots a high weight
                heatmap_data.append([location[0], location[1], 0.8])
            except Exception as e:
                print(f"Error processing hotspot: {e}")
                continue
    
    # Add publicity locations with medium weight if provided
    if publicity is not None:
        for _, row in publicity.iterrows():
            try:
                if row.geometry.geom_type == 'Point':
                    location = [float(row.geometry.y), float(row.geometry.x)]
                else:
                    centroid = row.geometry.centroid
                    location = [float(centroid.y), float(centroid.x)]
                # Give publicity locations a medium weight
                heatmap_data.append([location[0], location[1], 0.6])
            except Exception as e:
                print(f"Error processing publicity location: {e}")
                continue
    
    # Add the actual heatmap layer if we have data
    if heatmap_data:
        try:
            HeatMap(
                data=heatmap_data,  # Explicitly name the parameter
                radius=15,
                max_zoom=13,
                min_opacity=0.5,
                blur=10
            ).add_to(m)
        except Exception as e:
            print(f"Error creating heatmap: {e}")
    else:
        print("No heatmap data available")
    
    # Add markers for hotspots
    if hotspots is not None:
        for _, row in hotspots.iterrows():
            if row.geometry.geom_type == 'Point':
                location = [row.geometry.y, row.geometry.x]
            else:
                centroid = row.geometry.centroid
                location = [centroid.y, centroid.x]
                
            folium.CircleMarker(
                location=location,
                radius=5,
                color='blue',
                fill=True,
                fill_color='blue',
                fill_opacity=0.7
            ).add_to(m)
    
    # Add markers for publicity locations
    if publicity is not None:
        for _, row in publicity.iterrows():
            if row.geometry.geom_type == 'Point':
                location = [row.geometry.y, row.geometry.x]
            else:
                centroid = row.geometry.centroid
                location = [centroid.y, centroid.x]
                
            folium.CircleMarker(
                location=location,
                radius=5,
                color='green',
                fill=True,
                fill_color='green',
                fill_opacity=0.7
            ).add_to(m)
    
    return m

# ----- Flask Routes -----

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/get_map')
def get_map():
    """Generate and return map for selected customer segment"""
    segment = request.args.get('segment', 'kmu')
    
    # Load all data
    merged_data = merge_datasets()
    hotspots = load_hotspots()
    publicity = load_publicity_locations()
    
    # Apply appropriate weighting based on segment
    if segment == 'kmu':
        data = kmu_weighting(merged_data, hotspots, publicity)
        weight_column = 'kmu_weight'
    elif segment == 'handwerk':
        data = handwerk_weighting(merged_data, hotspots, publicity)
        weight_column = 'handwerk_weight'
    elif segment == 'retail_gastro':
        data = retail_gastro_weighting(merged_data, hotspots, publicity)
        weight_column = 'retail_gastro_weight'
    elif segment == 'service':
        data = service_weighting(merged_data, hotspots, publicity)
        weight_column = 'service_weight'
    elif segment == 'tourism':
        data = tourism_weighting(merged_data, hotspots, publicity)
        weight_column = 'tourism_weight'
    elif segment == 'startup':
        data = startup_weighting(merged_data, hotspots, publicity)
        weight_column = 'startup_weight'
    else:
        # Default
        data = kmu_weighting(merged_data, hotspots, publicity)
        weight_column = 'kmu_weight'
    
    # Create map
    m = create_heatmap(data, weight_column, hotspots, publicity)
    
    # Save map to HTML and return it
    map_path = f'templates/maps/{segment}_map.html'
    os.makedirs('templates/maps', exist_ok=True)
    m.save(map_path)
    
    return render_template(f'maps/{segment}_map.html')

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