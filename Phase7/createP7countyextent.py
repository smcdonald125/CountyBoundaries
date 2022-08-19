"""
Script: aggregate1mLU.py
Purpose: For the 13 Phase 6 classes and 18 General roll up clases, produce bay-wide 10m rasters of 2013-2017 
         Land Use Change and 2017 Land Use.
         The Land Use Change rasters range from -100 to 100, where -100 is total loss of that general class and 
         100 is total gain of that general class (Ex. -100 for crop class would be a pixel that was crop in 2013
         and became forested in 2017)
         The Land Use Change rasters range from 0 to 100, where 0 is that class does not exist in that cell and
         100 is that cell is wholely that general class.
         The cell values are equivalent to area (100 meters squared).
Authors: Sarah McDonald, Geographer, USGS 
         Labeeb Ahmed, Geographer, USGS
Contact: smcdonald@chesapeakebay.net
         lahmed@chesapeakebay.net
"""
import sys
import os
import arcpy
from arcpy import env
from arcpy.sa import *
from pathlib import Path
from timeit import default_timer as timer
import subprocess as sp

class LULC:
    def run10mLU(input_folder, local_out_folder, final_output_folder, cfs):
        """
        Method: run10mLU()
        Purpose: Produce 13, bay-wide, 10m LU rasters. This function reclasses the LU rasters
                at 1m per county, aggregates the 1m county data to 10m, and then uses cell statistics
                to mosaic all counties 10m rasters together for each phase 6 class.
        Params: lu_p6_crosswalk_csv - path to csv containing the full LU names and their phase 6 class name
                p6_dict - dictionary of phase 6 class names and their values
                p6_abbrev_dict - dictionary of phase 6 class names and their abbreviations to use for naming
                input_folder - input root folder where LU rasters exist (nested in their own folders)
                local_out_folder - destination folder to write the output
        Returns: N/A
        """

        # # loop through all counties
        # print(f'no. of counties to run: {len(cfs)}')
        # for cofips in cfs:
        #     st = timer()
        #     print('---------------------------------------------------')
        #     print(cofips)

        #     # create directory
        #     out_path = Path(local_out_folder) / Path(cofips)
        #     out_path.mkdir(parents=True, exist_ok=True)

        #     lu_raster = f"{input_folder}/{cofips}_County_Mask.tif"

        #     # copy from planimetrics to local drive
        #     copy_cmdlet = ["powershell.exe", "Copy-Item", f'"{str(lu_raster).replace(".tif", ".*")}"', "-Destination", f'"{str(out_path)}"']
        #     process = sp.run(copy_cmdlet, check=True) 

        #     # environments
        #     # prepare env for 10m
        #     arcpy.env.snapRaster = "G:\\ImageryServer\\A__Snap\\Phase6_Snap.tif"
        #     arcpy.env.workspace = f"{local_out_folder}/{cofips}"
        #     arcpy.env.compression = "LZW"
        #     p6_cnty_1m_ras = f"{local_out_folder}/{cofips}/{cofips}_County_Mask.tif"
        #     aggregate_raster = f"{local_out_folder}/{cofips}/{cofips}_tmp_lu_10m.tif"

        #     # if class exists at 1m for the county - aggregate to 10m
        #     if not arcpy.Exists(aggregate_raster):
        #         if arcpy.Exists(p6_cnty_1m_ras):
        #             arcpy.env.extent = p6_cnty_1m_ras
        #             print(p6_cnty_1m_ras)
        #             aggregate_2_10m = Aggregate(str(p6_cnty_1m_ras), 10, "SUM", "EXPAND", "DATA")
        #             try:
        #                 arcpy.management.CopyRaster(
        #                     aggregate_2_10m, 
        #                     aggregate_raster, 
        #                     background_value=0, 
        #                     nodata_value=0, 
        #                     pixel_type="1_BIT", 
        #                 )
        #             except exception as error:
        #                 print(error)
        #             # delete 1m once aggregated to 10m
        #             arcpy.Delete_management(p6_cnty_1m_ras)
        #         else:
        #             print(f"ERROR: no local county mask found: {p6_cnty_1m_ras}")

        #     end = round((timer() - st)/60.0, 2)
        #     print("County time: ", end, " minutes")

        # Run mosaics
        try:
            mosaic(local_out_folder, final_output_folder, cfs)
        except Exception as e:
            print(e)

def mosaic(local_out_folder, final_output_folder, cfs):
    fname = '_tmp_lu_10m.tif'
    final_name = 'county_2020_10m_mask.tif'

    arcpy.env.snapRaster = "G:\\ImageryServer\\A__Snap\\Phase6_Snap.tif"
    arcpy.env.compression = "LZW"
    arcpy.env.extent = "MAXOF"
    # mosaic all the aggregate 10m 
    mosaic_rasters = [f"{local_out_folder}/{cf}/{cf}{fname}" for cf in cfs if os.path.isfile(f"{local_out_folder}/{cf}/{cf}{fname}")]
    print(len(mosaic_rasters))
    out_raster = CellStatistics(mosaic_rasters, "SUM", "DATA", "SINGLE_BAND")
    try:
        arcpy.management.CopyRaster(
            out_raster, 
            f"{final_output_folder}/{final_name}", 
            background_value=0, 
            nodata_value=0, 
            pixel_type="1_BIT", 
        )
    except Exception as e:
        print(f"write failed for {final_output_folder}/{final_name}\n{e}")
    

##################
if __name__ == '__main__':

    arcpy.env.overwriteOutput = True

    # extensions
    arcpy.CheckOutExtension("Spatial")

    # folder paths
    folder = r"C:\Users\smcdonald\Documents\2020_county_10m" # local folder to Aggregate_LandUse
    local_out_folder = f"{folder}/output/county"
    final_output_folder = f"{folder}/output"
    input_folder = r"X:\County_Raster\2020\Masks"

    # get list of cofips
    cfs = [f"{x.split('_')[0]}_{x.split('_')[1]}" for x in os.listdir(input_folder) if x[-4:] == '.tif']
    if len(cfs) != 205:
        raise TypeError(f"Invalid county count: {len(cfs)}")

    LULC.run10mLU(input_folder, local_out_folder, final_output_folder, cfs)