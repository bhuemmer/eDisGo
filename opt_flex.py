# -*- coding: utf-8 -*-
"""
@author: huemmer
"""

import os
import requests
import sys

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import geopandas as gpd
from shapely import wkt

from edisgo import EDisGo
#from edisgo.io.timeseries import set_time_series_active_power_predefined
from edisgo.tools.logger import setup_logger
from edisgo.tools.config import Config
from edisgo.io.db import engine as Engine, sql_grid_geom, session_scope_egon_data
from edisgo.flex_opt.battery_storage_operation import apply_reference_operation


# check possible input data
eDisGo_dir = r"C:\FlexIMa\eDisGo\eDisGo"
file_path1 = r"D:\Ablage\FlexIMa\ding0_v0.3\grids\_overview\ding0_mv_grid_districts.gpkg"
file_path2 = r"D:\Ablage\FlexIMa\ding0_v0.3\MaStR_analysis\grid_structure_EPSG_25832.csv"
gdf = gpd.read_file(file_path1)

df = pd.read_csv(file_path2, encoding="utf-8")
df = df[df["DSO"]=="N-ERGIE Netz GmbH"]
df["geometry"] = df["geometry"].apply(wkt.loads)
gdf_gridarea = gpd.GeoDataFrame(df, geometry="geometry", crs=25832).to_crs("EPSG:4326")
gdf_gridarea = gdf_gridarea.unary_union

gdf_intersections = gdf[gdf.intersects(gdf_gridarea)]
gdf_inside = gdf[gdf.within(gdf_gridarea)]

# set up logger that streams edisgo logging messages with level info and above 
# and other logging messages with level warning and above to stdout
setup_logger(
    loggers=[
        {"name": "root", "file_level": None, "stream_level": "warning"},
        {"name": "edisgo", "file_level": None, "stream_level": "info"}
    ]
)


# create eDisGo object
r = gdf_inside["name"].iloc[0]
ding0_example_grid_path = fr"D:\Ablage\FlexIMa\ding0_v0.3\grids\{r}\topology"
config_path = fr"D:\Ablage\FlexIMa\ding0_v0.3\grids\{r}"

timeindex = pd.date_range('2011-01-01', periods=8760, freq='H')

edisgo_obj = EDisGo(ding0_grid=ding0_example_grid_path,legacy_ding0_grids=False)
edisgo_obj.import_generators(generator_scenario="eGon2035")

# generators and conventional loads
edisgo_obj.set_time_series_active_power_predefined(
    fluctuating_generators_ts = "oedb", # df_res
    dispatchable_generators_ts=pd.DataFrame(data=1, columns=["other"], index=timeindex),
    conventional_loads_ts = "demandlib"
)


## flexibility allocation
# ind cts dsm
edisgo_obj.import_dsm(scenario = "eGon2035")

# heat pumps
edisgo_obj.import_heat_pumps(scenario = "eGon2035")

# allocation of emob
edisgo_obj.import_electromobility(data_source="oedb",
                                  scenario = "eGon2035")

# allocation of home batteries
edisgo_obj.import_home_batteries(scenario = "eGon2035")



## flexibility timeseries
# heat pumps
edisgo_obj.apply_heat_pump_operating_strategy(strategy="uncontrolled")

# emob
edisgo_obj.apply_charging_strategy(strategy="dumb")

# home batteries
soe_df = apply_reference_operation(edisgo_obj, storage_units_names=None, soe_init=0.0, freq=1)

# reactive power time series
edisgo_obj.set_time_series_reactive_power_control()

# check consistency of topology
edisgo_obj.check_integrity()

# opf and grid reinforcement
edisgo_obj.analyze(troubleshooting_mode = "lpf")
edisgo_obj.reinforce()


edisgo_obj.save(directory="C:\FlexIMa\eDisGo\results",
                save_electromobility=True,
                save_opf_results=True,
                save_heatpump=True,
                save_overlying_grid=True,
                save_dsm=True,
                reduce_memory=True
                )



cases = ["load_case", "feed-in_case"]
edisgo_obj.set_time_series_worst_case_analysis(cases=cases)

