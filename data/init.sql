CREATE TABLE IF NOT EXISTS dim_province (
    province_id INTEGER PRIMARY KEY AUTOINCREMENT,
    province_name TEXT UNIQUE NOT NULL,
    region_name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_city_municipality (
    city_municipality_id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_municipality_name TEXT NOT NULL,
    province_id INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    FOREIGN KEY (province_id) REFERENCES dim_province(province_id) ON DELETE CASCADE,
    UNIQUE (city_municipality_name, province_id)
);

CREATE TABLE IF NOT EXISTS dim_barangay (
    barangay_id INTEGER PRIMARY KEY AUTOINCREMENT,
    barangay_name TEXT NOT NULL,
    city_municipality_id INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    FOREIGN KEY (city_municipality_id) REFERENCES dim_city_municipality(city_municipality_id) ON DELETE CASCADE,
    UNIQUE (barangay_name, city_municipality_id)
);

INSERT OR IGNORE INTO dim_province (region_name, province_name, latitude, longitude) VALUES
('Region III (Central Luzon)', 'Aurora', 15.922812842207223, 121.69931394152403),
('Region III (Central Luzon)', 'Bataan', 14.660422834689955, 120.4544259554945),
('Region III (Central Luzon)', 'Bulacan', 14.97861601658849, 121.05847123279369),
('Region III (Central Luzon)', 'Nueva Ecija', 15.619597664873712, 121.02167261035025),
('Region III (Central Luzon)', 'Pampanga', 15.058489921748, 120.64719833089151),
('Region III (Central Luzon)', 'Tarlac', 15.47829450787392, 120.47615743319972),
('Region III (Central Luzon)', 'Zambales', 15.286127431578489, 120.14405413196098)
ON CONFLICT(province_name) DO NOTHING;

CREATE TABLE IF NOT EXISTS fact_palay_production (
    production_id INTEGER PRIMARY KEY AUTOINCREMENT,
    province_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    volume_metric_tons REAL NOT NULL,
    area_harvested_hectares REAL NOT NULL,
    yield_mt_per_ha REAL GENERATED ALWAYS AS (volume_metric_tons / NULLIF(area_harvested_hectares, 0)) STORED,
    FOREIGN KEY (province_id) REFERENCES dim_province(province_id),
    UNIQUE (province_id, year, month)
);

CREATE TABLE IF NOT EXISTS fact_retail_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    province_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    retail_price_php REAL NOT NULL,
    FOREIGN KEY (province_id) REFERENCES dim_province(province_id),
    UNIQUE (province_id, year, month)
);

CREATE TABLE fact_weather_monthly (
    province_id INTEGER,
    year INTEGER,
    month INTEGER,
    precipitation_sum REAL,
    et0_fao_evapotranspiration REAL,
    shortwave_radiation_sum REAL,
    temperature_2m_mean REAL,
    temperature_2m_max REAL,
    temperature_2m_min REAL,
    wind_gusts_10m_max REAL,
    surface_pressure_mean REAL,
    soil_moisture_0_to_100cm_mean REAL,
    relative_humidity_2m_mean REAL,
    extreme_rain_days INTEGER,
    extreme_heat_days INTEGER,
    PRIMARY KEY (province_id, year, month),
    FOREIGN KEY (province_id) REFERENCES dim_province(province_id)
);

CREATE INDEX IF NOT EXISTS idx_city_prov_id ON dim_city_municipality (province_id);
CREATE INDEX IF NOT EXISTS idx_brgy_city_id ON dim_barangay (city_municipality_id);

CREATE VIEW v_monthly_market_summary AS
SELECT
    l.province_id,
    l.region_name,
    l.province_name,
    l.latitude,
    l.longitude,
    p.year,
    p.month,
    p.volume_metric_tons,
    p.area_harvested_hectares,
    p.yield_mt_per_ha,
    pr.retail_price_php
FROM fact_palay_production p
JOIN dim_province l ON p.province_id = l.province_id
LEFT JOIN fact_retail_prices pr
       ON p.province_id = pr.province_id
      AND p.year = pr.year
      AND p.month = pr.month;

CREATE VIEW v_ml_market_features AS
SELECT
    curr.province_id,
    curr.province_name,
    curr.latitude,
    curr.longitude,
    curr.year,
    curr.month,
    curr.retail_price_php,
    curr.yield_mt_per_ha,
    curr.volume_metric_tons,
    LAG(curr.retail_price_php, 1) OVER w AS price_lag1,
    LAG(curr.retail_price_php, 12) OVER w AS price_lag12,
    LAG(curr.yield_mt_per_ha, 1) OVER w AS yield_lag1,
    LAG(curr.yield_mt_per_ha, 12) OVER w AS hist_yield,
    LAG(curr.volume_metric_tons, 1) OVER w AS production_lag1,
    LAG(curr.retail_price_php, 12) OVER w AS hist_price
FROM v_monthly_market_summary curr
WINDOW w AS (PARTITION BY curr.province_name ORDER BY curr.year, curr.month);

CREATE VIEW v_ml_full_dataset AS
SELECT
    p.province_name,
    p.latitude,
    p.longitude,
    w.year AS current_year,
    w.month,
    m.yield_mt_per_ha AS target_yield,
    m.retail_price_php AS target_price,
    m.volume_metric_tons AS target_production,
    m.price_lag1,
    m.price_lag12,
    m.yield_lag1,
    m.hist_yield,
    m.production_lag1,
    m.hist_price,
    w.precipitation_sum, 
    w.et0_fao_evapotranspiration, 
    w.shortwave_radiation_sum,
    w.temperature_2m_mean, 
    w.temperature_2m_max, 
    w.temperature_2m_min,
    w.wind_gusts_10m_max, 
    w.surface_pressure_mean, 
    w.soil_moisture_0_to_100cm_mean,
    w.relative_humidity_2m_mean, 
    w.extreme_rain_days, 
    w.extreme_heat_days
FROM fact_weather_monthly w
JOIN dim_province p ON w.province_id = p.province_id
LEFT JOIN v_ml_market_features m 
    ON w.province_id = m.province_id 
   AND w.year = m.year 
   AND w.month = m.month;