# data_preparation.py - Script to prepare and check data files

import os
import pandas as pd
import geopandas as gpd
import json
from shapely.geometry import Point
import sys

def check_data_files():
    """Check if all required data files exist"""
    required_files = [
        'data/municipalities.qmd',  # or geojson
        'data/income_by_municipality.csv',
        'data/public_hotspots.geojson',
        'data/publicity_locations.geojson'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("The following required data files are missing:")
        for file in missing_files:
            print(f" - {file}")
        print("\nPlease make sure all data files are in the correct location.")
        return False
    
    return True

def create_sample_data():
    """Create sample data files for testing if they don't exist"""
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # 1. Sample income data CSV
    if not os.path.exists('data/income_by_municipality.csv'):
        print("Creating sample income data...")
        
        # Create a sample dataframe based on your example
        data = {
            'region_id': list(range(1, 12)),
            'region_name': [
                'Aeugst am Albis', 'Affoltern am Albis', 'Bonstetten', 
                'Hausen am Albis', 'Hedingen', 'Kappel am Albis',
                'Knonau', 'Maschwanden', 'Mettmenstetten', 
                'Obfelden', 'Ottenbach'
            ],
            'income_total_mio': [
                111, 412, 231, 164, 167, 55, 91, 22, 221, 194, 107
            ],
            'income_per_taxpayer': [
                115286, 74896, 91023, 97382, 94955, 97090, 
                86992, 72427, 90336, 79419, 83296
            ]
        }
        
        # Add header rows to match your format
        with open('data/income_by_municipality.csv', 'w') as f:
            f.write('"Durchschnittliches steuerbares Einkommen* pro Steuerpflichtigem/-r, 2020",,,27598\n')
            f.write(',,,\n')
            f.write(',,"Steuerbares Einkommen, in Mio. Franken","Steuerbares Einkommen pro Steuerpflichtigem/-r, in Franken"\n')
            f.write('Regions-ID,Regionsname,,\n')
            f.write(',,,\n')
            f.write(',Schweiz,"309,266","79,015"\n')
            
        # Append the actual data
        df = pd.DataFrame(data)
        df.to_csv('data/income_by_municipality.csv', mode='a', index=False, header=False)
        
    # 2. Sample municipalities geojson (simplified for testing)
    if not os.path.exists('data/municipalities.geojson'):
        print("Creating sample municipality boundaries...")
        
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
                    'id': i,
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
    
    # 3. Sample hotspots
    if not os.path.exists('data/public_hotspots.geojson'):
        print("Creating sample hotspot data...")
        
        # Create points for hotspots
        hotspots = []
        for i in range(20):
            # Create random points across Switzerland
            x = 7.5 + (i % 5) * 0.3
            y = 46.8 + (i // 5) * 0.3
            
            hotspots.append({
                'type': 'Feature',
                'properties': {
                    'id': i,
                    'name': f'Hotspot {i}',
                    'type': 'Public WiFi'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [x, y]
                }
            })
        
        # Create GeoJSON structure
        geojson = {
            'type': 'FeatureCollection',
            'features': hotspots
        }
        
        # Save to file
        with open('data/public_hotspots.geojson', 'w') as f:
            json.dump(geojson, f)
    
    # 4. Sample publicity locations
    if not os.path.exists('data/publicity_locations.geojson'):
        print("Creating sample publicity location data...")
        
        # Create points for publicity locations
        publicity = []
        for i in range(15):
            # Create random points across Switzerland
            x = 7.8 + (i % 5) * 0.25
            y = 47.0 + (i // 5) * 0.25
            
            publicity.append({
                'type': 'Feature',
                'properties': {
                    'id': i,
                    'name': f'Ad Space {i}',
                    'type': 'Billboard'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [x, y]
                }
            })
        
        # Create GeoJSON structure
        geojson = {
            'type': 'FeatureCollection',
            'features': publicity
        }
        
        # Save to file
        with open('data/publicity_locations.geojson', 'w') as f:
            json.dump(geojson, f)

def convert_qmd_to_geojson():
    """Convert QMD file to GeoJSON if needed"""
    if os.path.exists('data/municipalities.qmd') and not os.path.exists('data/municipalities.geojson'):
        try:
            # Note: This is placeholder code - actual QMD processing depends on the specific format
            # You might need to use a specialized library or conversion process
            print("Attempting to convert QMD to GeoJSON...")
            
            # Placeholder - in a real scenario, you'd use appropriate libraries to parse QMD
            # For testing purposes, we'll create a sample GeoJSON if conversion fails
            create_sample_data()
            
            print("Warning: QMD to GeoJSON conversion is a placeholder. Please verify the data.")
        except Exception as e:
            print(f"Error converting QMD to GeoJSON: {e}")
            print("Please convert your QMD file to GeoJSON manually.")
            create_sample_data()

def test_data_loading():
    """Test loading and processing the data"""
    try:
        # Try loading the GeoJSON files
        print("Testing data loading...")
        
        # Municipalities
        if os.path.exists('data/municipalities.geojson'):
            municipalities = gpd.read_file('data/municipalities.geojson')
            print(f"✓ Successfully loaded municipalities data with {len(municipalities)} records")
        elif os.path.exists('data/municipalities.qmd'):
            print("! QMD file exists but conversion to GeoJSON might be needed")
        else:
            print("✗ Missing municipality boundaries data")
        
        # Income data
        if os.path.exists('data/income_by_municipality.csv'):
            # Skip header rows based on your format
            income_data = pd.read_csv('data/income_by_municipality.csv', skiprows=3)
            print(f"✓ Successfully loaded income data with {len(income_data)} records")
        else:
            print("✗ Missing income data")
        
        # Hotspots
        if os.path.exists('data/public_hotspots.geojson'):
            hotspots = gpd.read_file('data/public_hotspots.geojson')
            print(f"✓ Successfully loaded hotspots data with {len(hotspots)} records")
        else:
            print("✗ Missing hotspots data")
        
        # Publicity locations
        if os.path.exists('data/publicity_locations.geojson'):
            publicity = gpd.read_file('data/publicity_locations.geojson')
            print(f"✓ Successfully loaded publicity locations data with {len(publicity)} records")
        else:
            print("✗ Missing publicity locations data")
        
        print("\nData loading test completed.")
        
    except Exception as e:
        print(f"Error testing data: {e}")
        return False
    
    return True

def detect_csv_encoding():
    """Detect and fix encoding issues in CSV file"""
    import chardet
    
    if not os.path.exists('data/income_by_municipality.csv'):
        print("CSV file not found")
        return
    
    # Read the raw bytes
    with open('data/income_by_municipality.csv', 'rb') as f:
        raw_data = f.read()
    
    # Detect encoding
    result = chardet.detect(raw_data)
    print(f"Detected encoding: {result['encoding']} with confidence {result['confidence']}")
    
    # Try to decode with detected encoding
    try:
        text = raw_data.decode(result['encoding'])
        print("Successfully decoded with detected encoding")
        
        # Write back with UTF-8 encoding
        with open('data/income_by_municipality_utf8.csv', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Created UTF-8 encoded version at 'data/income_by_municipality_utf8.csv'")
        
        # Update your code to use this file instead
        print("Use this file instead by changing:")
        print("income_data = pd.read_csv('data/income_by_municipality_utf8.csv', skiprows=3, encoding='utf-8')")
        
    except UnicodeDecodeError as e:
        print(f"Failed to decode with detected encoding: {e}")

if __name__ == "__main__":
    print("=== Geomarketing Data Preparation Tool ===")
    
    # Check if files exist
    if not check_data_files():
        print("\nWould you like to create sample data files for testing? (y/n)")
        choice = input().strip().lower()
        if choice == 'y':
            create_sample_data()
        else:
            print("Please prepare the required data files manually.")
            sys.exit(1)
    
    # Convert QMD to GeoJSON if needed
    convert_qmd_to_geojson()
    
    print("\nWould you like to detect CSV encoding issues? (y/n)")
    choice = input().strip().lower()
    if choice == 'y':
        # Install chardet if not available
        try:
            import chardet
        except ImportError:
            print("Installing chardet package for encoding detection...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "chardet"])
            import chardet
        
        detect_csv_encoding()