# import packages 

import requests
import json
from geopy.geocoders import Nominatim
import pandas as pd
import ast
from pandas import json_normalize
from shapely.geometry import LineString
import math 
import geopandas as gpd
import seaborn as sns
import os
import numpy as np 
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join


def getAreaofSearch(local_name):
    '''
    based on location name local_name use nominatim to find a relation and area bounds. 
    return area_id
    '''
    # Geocoding request via Nominatim
    geolocator = Nominatim(user_agent="city_compare")
    geo_results = geolocator.geocode(local_name, exactly_one=False, limit=3)

    # Searching for relation in result set
    for r in geo_results:
        # print(r.address, r.raw.get("osm_type"))
        if r.raw.get("osm_type") == "relation":
            city = r
            break

    # Calculating area id
    area_id = int(city.raw.get("osm_id")) + 3600000000

    return area_id

def overpassQuery(area_id, waterway_type1, waterway_type2):
    '''
    calls on overpass api to search osm for specific waterway features within search area 
    return data as json format 
    '''
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = """
    [out:json];
        area(%s)->.searchArea;
        (
        way["waterway"= %s](area.searchArea);
        way["waterway"= %s](area.searchArea);
        );
        out geom;
    """ % (area_id, waterway_type1, waterway_type2)
    response = requests.get(overpass_url, 
                            params={'data': overpass_query})
    response.raise_for_status()
    data = response.json()
    return data 

def saveOutJSON(data, pathnm, filename):
    '''
    filters to get key 'elements' from queried data 
    save into .json into specified path
    returns pandas dataframe 
    '''
    lst = []
    for i in range(0, len(data['elements'])): 
        lst.append(data['elements'][i])

    with open(os.path.join(pathnm, filename + '.json'), 'w') as outfile:
        json.dump(lst, outfile)

    print(f"JSON file: {filename} has now been saved!")

def normalize_pivotTags(pathnm, filename):
    '''
    expand all tags from dict into separate columns, keep only tags of interest (i.e. layer, waterway, source, etc.)
    clean up layer values and conver to int
    returns new df with added tag columns
    '''
    df = pd.read_json(os.path.join(pathnm, filename + '.json'), orient ='records')
    tags_df = json_normalize(df['tags'])
    tags_df = tags_df[['layer', 'name', 'waterway', 'source', 'name:en', 'note', 'note:ja', 'source_ref']]
    tags_df = tags_df[tags_df['layer'] != '-.']
    tags_df['layer'] = tags_df['layer'].fillna('0').astype('int64')

    df_full = pd.concat([df, tags_df], axis=1)
    df_full['layer'] = df_full['layer'].fillna('0').astype('int64')

    return df_full

def convertToLineString(lat_lon_dict):
    '''
    convert lat/lon list of dictionary from json file to a more readable format 
    returns a WKT linestring format from a list of zipped lon,lat coordinates 
    '''
    lat = [] 
    lon = [] 
    if isinstance(lat_lon_dict, list) == False:
        return None
    else: 
        for i in range(0, len(lat_lon_dict)):
            lat.append(lat_lon_dict[i]['lat'])
            lon.append(lat_lon_dict[i]['lon'])

    return LineString(zip(lon,lat))

def filter_df(df):
    df = df[['type', 'id', 'layer',
        'name', 'waterway', 'source', 'name:en', 'note', 'note:ja',
        'source_ref', 'geo']]

    df.columns = ['type', 'osm_id', 'layer',
        'name', 'waterway', 'source', 'name:en', 'note', 'note:ja',
        'source_ref', 'geometry']
    return df

def create_geodf(df):
    df = filter_df(df)
    df_gpd = gpd.GeoDataFrame(df, geometry='geometry')
    df_gpd['layer'] = df_gpd['layer'].astype(str)
    df_gpd['source'] = np.where(
        ((df_gpd['source'] != 'KSJ2') & (df_gpd.source.str.contains("KSJ2"))), 'KSJ2-related', 
        np.where(df_gpd['source'] == 'KSJ2', 'KSJ2', 
                np.where((df_gpd.source.str.contains("GSI")), 'GSI-related', 'Other')))

    return df_gpd

def saveJSON(city_name, waterway_type1, waterway_type2, rootPath, filenm):
    area_id = getAreaofSearch(city_name)
    raw_data = overpassQuery(area_id, waterway_type1, waterway_type2)
    saveOutJSON(raw_data, rootPath, filenm)

def plotvisual(city_name, waterway_type1, waterway_type2, rootPath, filenm, column_name):
    df = normalize_pivotTags(rootPath, filenm)
    df['geo'] = [convertToLineString(df['geometry'][i]) for i in range(0,len(df['geometry']))] 
    gdf = create_geodf(df)
    if column_name == 'layer':
        layerPalette = {'-5' : 'blue',
                  '-4' : 'blue',
                  '-3': 'blue',
                  '-2': 'blue',
                  '-1': 'red',
                  '0': 'grey',
                  '1': 'green',
                  '2': 'green',
                  '3' : 'green',
                  '4': 'green'}

    elif column_name == 'source':
        layerPalette = {'KSJ2-related': 'blue',
               'KSJ2': 'red',
               'GSI-related': 'purple',
               'Other': 'grey'}

    # Plot data
    fig, ax = plt.subplots(figsize=(10, 10))

    grouped = gdf.groupby(column_name)

    for key, group in grouped:
        group.plot(ax=ax, label=key, color=layerPalette[key], linewidth=0.75)

    ax.legend()
    ax.set(title= f'{city_name}: OSM {waterway_type1}s and {waterway_type2}s by {column_name}')

    ax.set_axis_off()
    plt.show()

    return plt

def barplotvisual(city_name, rootPath, filenm):
    df = normalize_pivotTags(rootPath, filenm)
    df['geo'] = [convertToLineString(df['geometry'][i]) for i in range(0,len(df['geometry']))] 
    gdf = create_geodf(df)

    layerPalette = {'-5' : 'blue',
                    '-4' : 'blue',
                    '-3': 'blue',
                    '-2': 'blue',
                    '-1': 'red',
                    '0': 'grey',
                    '1': 'green',
                    '2': 'green',
                    '3' : 'green',
                    '4': 'green'}

    fig, ax = plt.subplots(figsize=(10,10))
    ax = sns.histplot(x='source', hue='layer', data=gdf, 
                    ax=ax, multiple="dodge", shrink=.8, 
                    legend = True, palette=layerPalette)


    # ax.legend()
    ax.set(title= f'{city_name}: Feature Count of Layers by Source Type')

    return plt

def savegeoData_as(input_path, filenm, dataType, output_path):
    df = normalize_pivotTags(input_path, filenm)
    df['geo'] = [convertToLineString(df['geometry'][i]) for i in range(0,len(df['geometry']))] 
    gdf = create_geodf(df)
    if dataType == 'geojson':
        gdf.to_file(os.path.join(output_path, filenm + '.geojson'), driver='GeoJSON')

    elif dataType == 'shapefile':
        new_outpath = os.path.join(output_path, filenm)
        if os.path.isdir(new_outpath) == False: 
            os.mkdir(new_outpath)
        gdf.to_file(os.path.join(new_outpath, filenm + '.shp'))
  
    print(f"file save {filenm} complete!")

def getFiles_asList(user_path):
    userPath = user_path.value
    onlyfiles = [f for f in listdir(userPath) if isfile(join(userPath, f))]
    return onlyfiles