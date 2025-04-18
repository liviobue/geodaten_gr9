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
    """Load income data and match with municipalities using the last income value for similar names."""
    try:
        # Load income data
        income_df = pd.read_csv('data/income_by_municipality_utf8.csv', header=None)
        income_df.columns = ['id', 'municipality_name', 'population', 'income']
        
        # Clean income data: remove quotes and commas
        income_df['income'] = income_df['income'].str.replace('"', '').str.replace(',', '')
        
        # Log raw income data for debugging
        print(f"Raw income sample: {income_df['income'].head().tolist()}")
        
        # Filter out rows where income is non-numeric
        income_df = income_df[income_df['income'].str.isnumeric()]
        
        # Convert income to float
        income_df['income'] = income_df['income'].astype(float)
        
        # Log basic statistics for debugging
        print(f"Income data loaded: {len(income_df)} rows")
        print(f"Income range: min={income_df['income'].min()}, max={income_df['income'].max()}")
        
        # Keep only the last row for each municipality name
        income_df = income_df.sort_values(by=['municipality_name', 'id']).groupby('municipality_name').last().reset_index()
        
        # Normalize income for coloring (scale between 0 and 1)
        income_min = income_df['income'].min()
        income_max = income_df['income'].max()
        income_df['income_normalized'] = (
            (income_df['income'] - income_min) / (income_max - income_min)
            if income_max != income_min else 0
        )
        
        # Log normalization results
        print(f"Normalized income range: min={income_df['income_normalized'].min()}, max={income_df['income_normalized'].max()}")
        
        # Fuzzy matching to align municipality names
        municipality_names = municipalities['NAME'].tolist()
        def match_name(x):
            if pd.notna(x):
                match = process.extractOne(x, municipality_names, score_cutoff=80)
                return match[0] if match else None
            return None
        
        income_df['matched_name'] = income_df['municipality_name'].apply(match_name)
        
        # Log matching results
        unmatched = income_df[income_df['matched_name'].isna()]
        if not unmatched.empty:
            print(f"Warning: {len(unmatched)} municipalities could not be matched: {unmatched['municipality_name'].tolist()}")
        
        # Merge with municipalities GeoDataFrame using matched names
        merged = municipalities.merge(
            income_df[['matched_name', 'income', 'income_normalized']],
            left_on='NAME',
            right_on='matched_name',
            how='left'
        )
        
        # Log merge results
        missing_income = merged[merged['income'].isna()]
        if not missing_income.empty:
            print(f"Warning: {len(missing_income)} municipalities have no income data: {missing_income['NAME'].tolist()}")
        
        return merged
    
    except Exception as e:
        print(f"Error loading or merging income data: {e}")
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

        # Merge with income data
        german_municipalities = load_and_merge_income_data(german_municipalities)

        # Define columns for GeoJson based on available data
        geojson_columns = ['BFS_NUMMER', 'NAME', 'KANTONSNUMMER', 'geometry']
        tooltip_fields = ['BFS_NUMMER', 'NAME', 'KANTONSNUMMER']
        tooltip_aliases = ['BFS Number:', 'Name:', 'Canton:']

        # Check if income data is available
        if 'income' in german_municipalities.columns and 'income_normalized' in german_municipalities.columns:
            geojson_columns.extend(['income', 'income_normalized'])
            tooltip_fields.append('income')
            tooltip_aliases.append('Income (CHF):')

        # Add municipalities with income-based coloring
        folium.GeoJson(
            german_municipalities[geojson_columns],
            style_function=lambda x: {
                'fillColor': (
                    # Continuous red gradient: light red (#FF9999) to dark red (#8B0000)
                    '#{:02x}0000'.format(
                        int(255 - (x['properties']['income_normalized'] * (255 - 139)))  # 139 for #8B0000
                    ) if pd.notna(x['properties'].get('income_normalized')) else '#D3D3D3'
                ),
                'fillOpacity': 0.7,  # Fixed opacity for consistency
                'color': '#3388ff',  # Border color
                'weight': 1,
            },
            name='German-Speaking Municipalities',
            tooltip=folium.features.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=tooltip_aliases,
                localize=True
            )
        ).add_to(m)

        # Add continuous color scale legend
        if 'income' in german_municipalities.columns:
            income_min = german_municipalities['income'].min()
            income_max = german_municipalities['income'].max()
            colormap = folium.LinearColormap(
                colors=['#FF9999', '#FF3333', '#8B0000'],  # Light to dark red
                vmin=income_min,
                vmax=income_max,
                caption='Income (CHF)'
            )
            colormap.add_to(m)

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