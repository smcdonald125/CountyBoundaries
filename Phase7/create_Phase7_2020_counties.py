import os
import sys
import geopandas as gpd 
import rasterio as rio 
from rasterio.features import shapes
import numpy as np 
from shapely.geometry import MultiPolygon, Polygon


def vectorizeRaster(unique_array, transform):
    """
    Method: vectorizeRaster()
    Purpose: Create polygon geometries for each unique zone in the raster.
    Params: unique_array - numpy array of zones
            transform - rasterio transform of array that is to be vectorized
    Returns: zones_gdf - geodataframe of vectorized raster zones with unique field 'zone'
    """
    if unique_array.dtype != 'uint8':
        unique_array = unique_array.astype(np.uint8) # was 16 - changed 4/12/22

    results = (
        {'properties': {'LC': v}, 'geometry': s}
        for i, (s, v) in enumerate(shapes(unique_array, mask=unique_array.astype(bool), transform=transform))
        )

    # convert to gdf
    geoms = list(results)
    zones_gdf = gpd.GeoDataFrame.from_features(geoms, crs="EPSG:5070") #need to handle if gdf is empty
    del unique_array
    zones_gdf['zone'] = [int(x) for x in range(1, len(zones_gdf)+1)]
    zones_gdf.loc[:, 'LC'] = zones_gdf.LC.astype(int) # ensure the LC value is an int
    return zones_gdf[['zone','geometry']] # don't need cell value

def shared_area(df1, df2):
    """
    Method: shared_area()
    Purpose: Calculate the amount of shared border between border pixel and counties.
    Params: args
                df1 - gdf of counties
                df2 - gdf of border cells
    Returns: geoid - which county to assign the zone to
    """
    # overlay the pixel with original boundaries and calculate area
    new_geo = gpd.overlay(df1, df2, how='intersection')
    new_geo.loc[:, 'area'] = new_geo['geometry'].area
    mx = np.amax(new_geo['area'])

    # select county that shares the most area with the pixel
    geoid = list(new_geo[new_geo['area'] == mx]['GEOID'])[0]

    return geoid

def run(extentRas, countyPath, countyRasPath, county_origPath, outputPath):
    """
    1. Read in extent raster and select pixels < 100 (edge pixels)
    2. Vectorize edge pixels
    3. Read in 2017 county boundaries (rasterized to 10-meters and then vectorized)
    4. Intersect the results from step 2 with county boundaries
    5. Dissolve connections to create updated county boundaries
    """

    # 1. read in extent array and select pixels that are not 100
    print("Reading extent raster...")
    with rio.open(extentRas) as src:
        ary = src.read(1)
        ary = np.where(ary == 100, 0, ary)
        trans = src.meta['transform']

    # read in 10m raster of counties to mask out edges already included
    with rio.open(countyRasPath) as src:
        mask = src.read(1)
        nodata = src.nodatavals[0]
        mask = np.where(mask != nodata, 1, 0).astype(bool)

    # mask edge pixels already accounted for
    ary = np.where(mask, 0, ary)

    # 2. vectorize border cells
    print("Vectorizing border cells...")
    borderCells = vectorizeRaster(ary, trans)
    del ary
    print(f"Created {len(borderCells)} border polygons")

    # 3. Read in county boundaries
    print("Reading counties...")
    cnties = gpd.read_file(countyPath)
    cnties = cnties[['gridcode', 'geometry']]
    cnties.rename(columns={'gridcode':'GEOID'}, inplace=True)
    origCnties = gpd.read_file(county_origPath)
    origCnties = origCnties[['GEOID', 'geometry']]
    origCnties.loc[:, 'GEOID'] = origCnties['GEOID'].astype(int)

    # 4. intersect border cells and counties
    print("Intersecting Border Cells with Counties\n")
    tab = gpd.sjoin(cnties, borderCells, op='intersects', how='inner')

    # 5. Dissolve border cells with adjacent county
    geoids = list(cnties['GEOID'])
    if len(geoids) != 205:
        raise TypeError(f"Invalid county count : {len(geoids)}")
    cnties.set_index('GEOID', inplace=True)
    for g in geoids:
        # select border pixels that are touching current county
        zones = list(set(list(tab[tab['GEOID']==g]['zone'])))
        
        # check if there are border pixels, if not skip
        if len(zones) == 0:
            continue

        # check if any border pixels are touching another county - run shared border for all counties touching the same pixel
        remove_zones = []
        ct = 0
        for z in zones:
            o_cnties = list(set(list(tab[tab['zone']==z]['GEOID'])))
            if len(o_cnties) > 1:
                g_sb = shared_area(origCnties[origCnties['GEOID'].isin(o_cnties)], borderCells[borderCells['zone']==z])
                if g_sb != g: # if there is another county sharing more of a border than current county, don't dissolve with current county
                    remove_zones.append(z)
                    if g_sb == 0:
                        raise TypeError(f"Shared area analysis resulted in 0 border area")
            ct += 1
            if ct > len(zones):
                raise TypeError("Infinite loop?")

        # dissolve zones not intersecting another county
        zones = list( set(list(zones)) - set(remove_zones) ) # zones not touching another county
        if len(zones) != 0:
            print(f"\n{g}")
            print(f"\tDissolving {len(zones)} border polys into county...")
            # dissolve border cells with county
            tmp = cnties.loc[[g]][['geometry']].append(borderCells[borderCells['zone'].isin(zones)][['geometry']])
            tmp.loc[:, 'GEOID'] = g
            tmp = tmp.dissolve(by='GEOID')

            # update geometry of origin county with new geometry
            try:
                cnties.loc[g, 'geometry'] = tmp.loc[g,'geometry'] 
            except:
                cnties.drop(g, axis=index, inplace=True)
                cnties = cnties.append(tmp)
            del tmp

    # write updated counties
    print("Writing results...")
    cnties.to_file(outputPath)

if __name__=="__main__":
    folder = r'C:\Users\smcdonald\Documents\Data\Phase7Counties'
    input_folder = f"{folder}/input/2020"
    output_folder = f"{folder}/output"
    countyPath = f"{input_folder}/census_county_2020_albers_10m.shp"
    countyRasPath = f"{input_folder}/census_county_albers_10m_maskextent.tif"
    county_origPath = f"{input_folder}/census_county_2020_albers.shp"
    extentRasPath = f"{input_folder}/county_2020_10m_mask.tif"
    outputPath = f"{output_folder}/Phase7_county_2020_10m.shp"

    run(extentRasPath, countyPath, countyRasPath, county_origPath, outputPath)