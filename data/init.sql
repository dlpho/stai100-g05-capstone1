CREATE TABLE dim_locations (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_name TEXT NOT NULL,
    province_name TEXT NOT NULL UNIQUE
);

INSERT INTO dim_locations (region_name, province_name) VALUES 
('Region III (Central Luzon)', 'Aurora'),
('Region III (Central Luzon)', 'Bataan'),
('Region III (Central Luzon)', 'Bulacan'),
('Region III (Central Luzon)', 'Nueva Ecija'),
('Region III (Central Luzon)', 'Pampanga'),
('Region III (Central Luzon)', 'Tarlac'),
('Region III (Central Luzon)', 'Zambales');

CREATE TABLE fact_palay_production (
    production_id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER REFERENCES dim_locations(location_id),
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    volume_metric_tons REAL NOT NULL,
    area_harvested_hectares REAL NOT NULL,
    yield_mt_per_ha REAL GENERATED ALWAYS AS (volume_metric_tons / NULLIF(area_harvested_hectares, 0)) STORED,
    UNIQUE (location_id, year, month)
);

CREATE TABLE fact_farmgate_prices (
    price_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id         INTEGER REFERENCES dim_locations(location_id),
    year                INTEGER NOT NULL,
    month               INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    farmgate_price_php  REAL NOT NULL,
    UNIQUE (location_id, year, month)
);