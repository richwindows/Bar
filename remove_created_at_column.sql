-- ====================================
-- 删除重复的 created_at 列脚本
-- ====================================
-- 此脚本用于简化 barcode_scans 表结构，移除重复的时间字段

-- 步骤1: 确保 scan_time 列存在并包含数据
ALTER TABLE barcode_scans 
ADD COLUMN IF NOT EXISTS scan_time TIMESTAMPTZ DEFAULT NOW();

-- 步骤2: 为没有 scan_time 的记录填充数据（使用 created_at 的值）
UPDATE barcode_scans 
SET scan_time = created_at 
WHERE scan_time IS NULL AND created_at IS NOT NULL;

-- 步骤3: 为 scan_time 列创建索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_barcode_scans_scan_time ON barcode_scans(scan_time);

-- 步骤4: 删除 created_at 相关的索引
DROP INDEX IF EXISTS idx_barcode_scans_created_at;

-- 步骤5: 删除重复的 created_at 列
ALTER TABLE barcode_scans DROP COLUMN IF EXISTS created_at;

-- 验证表结构
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'barcode_scans' 
ORDER BY ordinal_position;

-- 查看最新的扫描记录以确认数据完整性
SELECT id, barcode_data, device_port, scan_time
FROM barcode_scans 
ORDER BY scan_time DESC 
LIMIT 5;