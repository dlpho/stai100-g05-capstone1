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

INSERT INTO dim_province (region_name, province_name, latitude, longitude) VALUES
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

CREATE INDEX IF NOT EXISTS idx_city_prov_id ON dim_city_municipality (province_id);
CREATE INDEX IF NOT EXISTS idx_brgy_city_id ON dim_barangay (city_municipality_id);

CREATE VIEW IF NOT EXISTS v_monthly_market_summary AS
SELECT
    l.province_id,
    l.region_name,
    l.province_name,
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
