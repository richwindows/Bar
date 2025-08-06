-- ====================================
-- 改进的条码扫描数据库表结构 (PostgreSQL/Supabase)
-- current_status 根据最新状态时间自动计算
-- ====================================

-- 创建新的条码扫描记录表
CREATE TABLE IF NOT EXISTS barcode_scans_new (
    id BIGSERIAL PRIMARY KEY,
    barcode_data VARCHAR(500) NOT NULL UNIQUE,
    device_port VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- 状态1：已排产
    status_1_scheduled BOOLEAN DEFAULT FALSE,
    status_1_time TIMESTAMPTZ,
    
    -- 状态2：已切割
    status_2_cut BOOLEAN DEFAULT FALSE,
    status_2_time TIMESTAMPTZ,
    
    -- 状态3：已清角
    status_3_cleaned BOOLEAN DEFAULT FALSE,
    status_3_time TIMESTAMPTZ,
    
    -- 状态4：已入库
    status_4_stored BOOLEAN DEFAULT FALSE,
    status_4_time TIMESTAMPTZ,
    
    -- 状态5：部分出库
    status_5_partial_out BOOLEAN DEFAULT FALSE,
    status_5_time TIMESTAMPTZ,
    
    -- 状态6：已出库
    status_6_shipped BOOLEAN DEFAULT FALSE,
    status_6_time TIMESTAMPTZ,
    
    -- 当前状态（自动计算，不需要手动设置）
    current_status VARCHAR(50) GENERATED ALWAYS AS (
        CASE 
            WHEN status_6_time IS NOT NULL AND (
                status_6_time >= COALESCE(status_5_time, '1900-01-01'::timestamptz) AND
                status_6_time >= COALESCE(status_4_time, '1900-01-01'::timestamptz) AND
                status_6_time >= COALESCE(status_3_time, '1900-01-01'::timestamptz) AND
                status_6_time >= COALESCE(status_2_time, '1900-01-01'::timestamptz) AND
                status_6_time >= COALESCE(status_1_time, '1900-01-01'::timestamptz)
            ) THEN '已出库'
            WHEN status_5_time IS NOT NULL AND (
                status_5_time >= COALESCE(status_4_time, '1900-01-01'::timestamptz) AND
                status_5_time >= COALESCE(status_3_time, '1900-01-01'::timestamptz) AND
                status_5_time >= COALESCE(status_2_time, '1900-01-01'::timestamptz) AND
                status_5_time >= COALESCE(status_1_time, '1900-01-01'::timestamptz)
            ) THEN '部分出库'
            WHEN status_4_time IS NOT NULL AND (
                status_4_time >= COALESCE(status_3_time, '1900-01-01'::timestamptz) AND
                status_4_time >= COALESCE(status_2_time, '1900-01-01'::timestamptz) AND
                status_4_time >= COALESCE(status_1_time, '1900-01-01'::timestamptz)
            ) THEN '已入库'
            WHEN status_3_time IS NOT NULL AND (
                status_3_time >= COALESCE(status_2_time, '1900-01-01'::timestamptz) AND
                status_3_time >= COALESCE(status_1_time, '1900-01-01'::timestamptz)
            ) THEN '已清角'
            WHEN status_2_time IS NOT NULL AND (
                status_2_time >= COALESCE(status_1_time, '1900-01-01'::timestamptz)
            ) THEN '已切割'
            WHEN status_1_time IS NOT NULL THEN '已排产'
            ELSE '未知状态'
        END
    ) STORED,
    
    -- 最后扫描时间（自动计算）
    last_scan_time TIMESTAMPTZ GENERATED ALWAYS AS (
        GREATEST(
            COALESCE(status_1_time, '1900-01-01'::timestamptz),
            COALESCE(status_2_time, '1900-01-01'::timestamptz),
            COALESCE(status_3_time, '1900-01-01'::timestamptz),
            COALESCE(status_4_time, '1900-01-01'::timestamptz),
            COALESCE(status_5_time, '1900-01-01'::timestamptz),
            COALESCE(status_6_time, '1900-01-01'::timestamptz)
        )
    ) STORED
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_barcode_scans_new_barcode_data ON barcode_scans_new(barcode_data);
CREATE INDEX IF NOT EXISTS idx_barcode_scans_new_current_status ON barcode_scans_new(current_status);
CREATE INDEX IF NOT EXISTS idx_barcode_scans_new_last_scan_time ON barcode_scans_new(last_scan_time);
CREATE INDEX IF NOT EXISTS idx_barcode_scans_new_device_port ON barcode_scans_new(device_port);

-- 创建更新时间的触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_barcode_scans_updated_at 
    BEFORE UPDATE ON barcode_scans_new 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ===================
-- 示例查询
-- ===================

-- 查询所有条码及其自动计算的状态
SELECT 
    barcode_data,
    current_status,
    last_scan_time,
    status_1_time as 排产时间,
    status_2_time as 切割时间,
    status_3_time as 清角时间,
    status_4_time as 入库时间,
    status_5_time as 部分出库时间,
    status_6_time as 出库时间
FROM barcode_scans_new
ORDER BY last_scan_time DESC;

-- 统计各状态数量（基于自动计算的current_status）
SELECT 
    current_status,
    COUNT(*) as 数量
FROM barcode_scans_new
GROUP BY current_status
ORDER BY 数量 DESC;