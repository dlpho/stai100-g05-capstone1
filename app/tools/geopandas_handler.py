import geopandas as gpd

brgy_path = "philippines-psgc-shapefiles/data/2023/BgySubMuns/phl_admbnda_adm4_psa_namria_20231106.shp"
brgy_gdf = gpd.read_file(brgy_path)

municities_path = "philippines-psgc-shapefiles/data/2023/Municities/phl_admbnda_adm3_psa_namria_20231106.shp"
municities_gdf = gpd.read_file(municities_path)

provdists_path = "philippines-psgc-shapefiles/data/2023/Provdists/phl_admbnda_adm2_psa_namria_20231106.shp"
provdists_gdf = gpd.read_file(provdists_path)


# BARANGAYS ------------------
brgy_gdf_proj = brgy_gdf.to_crs(epsg=32651)
projected_centroids = brgy_gdf_proj['geometry'].centroid

# Convert the centroids back to standard Lat/Lng (WGS 84 / EPSG:4326)
lng_lat_centroids = projected_centroids.to_crs(epsg=4326)

# Extract
brgy_gdf['latitude'] = lng_lat_centroids.y
brgy_gdf['longitude'] = lng_lat_centroids.x

# Get & Rename
brgy_final = brgy_gdf[['ADM4_EN', 'ADM3_EN', 'ADM2_EN', 'ADM1_EN', 'latitude', 'longitude']]
brgy_final = brgy_final.rename(columns={
    'ADM4_EN': 'barangay',
    'ADM3_EN': 'municipality_city',
    'ADM2_EN': 'province',
    'ADM1_EN': 'region',
})

# Export
brgy_final.to_csv("data/philippines_barangay_coordinates_2023.csv", index=False)





# MUNICITIES ------------------
municities_gdf_proj = municities_gdf.to_crs(epsg=32651)
projected_centroids = municities_gdf_proj['geometry'].centroid

# Convert the centroids back to standard Lat/Lng (WGS 84 / EPSG:4326)
lng_lat_centroids = projected_centroids.to_crs(epsg=4326)

# Extract
municities_gdf['latitude'] = lng_lat_centroids.y
municities_gdf['longitude'] = lng_lat_centroids.x

# Get & Rename
municities_final = municities_gdf[['ADM3_EN', 'ADM2_EN', 'ADM1_EN', 'latitude', 'longitude']]
municities_final = municities_final.rename(columns={
    'ADM3_EN': 'municipality_city',
    'ADM2_EN': 'province',
    'ADM1_EN': 'region',
})

# Export
municities_final.to_csv("data/philippines_municities_coordinates_2023.csv", index=False)





# PROVDISTS ------------------
provdists_gdf_proj = provdists_gdf.to_crs(epsg=32651)
projected_centroids = provdists_gdf_proj['geometry'].centroid

# Convert the centroids back to standard Lat/Lng (WGS 84 / EPSG:4326)
lng_lat_centroids = projected_centroids.to_crs(epsg=4326)

# Extract
provdists_gdf['latitude'] = lng_lat_centroids.y
provdists_gdf['longitude'] = lng_lat_centroids.x

# Get & Rename
provdists_final = provdists_gdf[['ADM2_EN', 'ADM1_EN', 'latitude', 'longitude']]
provdists_final = provdists_final.rename(columns={
    'ADM2_EN': 'province',
    'ADM1_EN': 'region',
})

# Export
provdists_final.to_csv("data/philippines_provdists_coordinates_2023.csv", index=False)