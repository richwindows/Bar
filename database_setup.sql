-- ====================================
-- 条码扫描数据库表结构 (PostgreSQL/Supabase)
-- ====================================

-- 创建条码扫描记录表
CREATE TABLE IF NOT EXISTS barcode_scans (
    id BIGSERIAL PRIMARY KEY,
    barcode_data VARCHAR(500) NOT NULL,
    device_port VARCHAR(50),
    scan_time TIMESTAMPTZ DEFAULT NOW()
);

-- 创建条码扫描记录表索引
CREATE INDEX IF NOT EXISTS idx_barcode_scans_scan_time ON barcode_scans(scan_time);
CREATE INDEX IF NOT EXISTS idx_barcode_scans_barcode_data ON barcode_scans(barcode_data);
CREATE INDEX IF NOT EXISTS idx_barcode_scans_device_port ON barcode_scans(device_port);




-- ===================
-- 示例查询
-- ===================

-- 查询最近的扫描记录
SELECT 
    id,
    barcode_data,
    scan_time,
    device_port
FROM barcode_scans
ORDER BY scan_time DESC 
LIMIT 50;

-- 按日期统计扫描次数
SELECT 
    DATE(scan_time) as scan_date,
    COUNT(*) as total_scans,
    COUNT(DISTINCT barcode_data) as unique_barcodes
FROM barcode_scans 
GROUP BY DATE(scan_time)
ORDER BY scan_date DESC;

-- 查询最活跃的扫描时间段
SELECT 
    EXTRACT(HOUR FROM scan_time) as hour_of_day,
    COUNT(*) as scan_count
FROM barcode_scans
WHERE scan_time >= NOW() - INTERVAL '7 days'
GROUP BY EXTRACT(HOUR FROM scan_time)
ORDER BY scan_count DESC;

-- 查询特定设备的扫描记录
SELECT 
    device_port,
    COUNT(*) as total_scans,
    MIN(scan_time) as first_scan,
    MAX(scan_time) as last_scan
FROM barcode_scans
GROUP BY device_port
ORDER BY total_scans DESC;