"""
条码扫描数据库集成模块
用于将扫描数据上传到 Supabase 数据库
"""

import json
import uuid
import os
from datetime import datetime
from typing import Optional, Dict, List, Any
import logging

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("提示: python-dotenv 库未安装，将直接使用系统环境变量。运行: pip install python-dotenv")

# 尝试导入supabase，如果失败则使用离线模式
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except Exception as e:
    SUPABASE_AVAILABLE = False
    print(f"警告: supabase 库导入失败: {e}")
    print("程序将以离线模式运行")
    # 创建一个虚拟的Client类型提示
    Client = None

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        """
        初始化数据库管理器
        
        Args:
            supabase_url: Supabase 项目 URL (可选，优先从环境变量读取)
            supabase_key: Supabase 匿名密钥 (可选，优先从环境变量读取)
        """
        # 优先从环境变量读取配置
        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL')
        self.supabase_key = supabase_key or os.getenv('SUPABASE_KEY')
        self.client = None
        
        # 从环境变量读取配置选项
        self.config = {
            'database_enabled': os.getenv('DATABASE_ENABLED', 'true').lower() == 'true',
            'local_backup_enabled': os.getenv('LOCAL_BACKUP_ENABLED', 'true').lower() == 'true',
            'local_backup_filename': os.getenv('LOCAL_BACKUP_FILENAME', 'local_scan_backup.json'),
            'auto_sync_enabled': os.getenv('AUTO_SYNC_ENABLED', 'true').lower() == 'true',
            'log_level': os.getenv('LOG_LEVEL', 'INFO').upper()
        }
        
        # 设置本地数据目录
        self.local_data_dir = os.getenv('LOCAL_DATA_DIR', 'local_data')
        
        # 设置日志
        log_level = getattr(logging, self.config['log_level'], logging.INFO)
        logging.basicConfig(level=log_level)
        self.logger = logging.getLogger(__name__)
        
        # 显示配置信息
        if not SUPABASE_AVAILABLE:
            self.logger.warning("Supabase库不可用，将使用离线模式")
        elif self.supabase_url and self.supabase_key:
            self.logger.info("从环境变量加载数据库配置成功")
        else:
            self.logger.warning("未找到数据库配置，将使用离线模式")
        
        if SUPABASE_AVAILABLE and self.supabase_url and self.supabase_key and self.config['database_enabled']:
            self._initialize_client()
    
    def _initialize_client(self):
        """初始化 Supabase 客户端"""
        if not SUPABASE_AVAILABLE:
            self.logger.warning("Supabase库不可用，无法初始化客户端")
            return
            
        try:
            self.client = create_client(self.supabase_url, self.supabase_key)
            self.logger.info("Supabase 客户端初始化成功")
        except Exception as e:
            self.logger.error(f"Supabase 客户端初始化失败: {e}")
            self.client = None
    
    def configure_database(self, supabase_url: str, supabase_key: str):
        """配置数据库连接"""
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        if SUPABASE_AVAILABLE:
            self._initialize_client()
        else:
            self.logger.warning("Supabase库不可用，无法配置数据库连接")
    
    def upload_scan_data(self, barcode_data: str, device_port: str) -> bool:
        """
        上传扫描数据
        
        Args:
            barcode_data: 条码数据
            device_port: 设备端口
            
        Returns:
            上传是否成功
        """
        # 如果数据库不可用或未启用，直接保存到本地
        if not SUPABASE_AVAILABLE or not self.client or not self.config['database_enabled']:
            if self.config['local_backup_enabled']:
                if not SUPABASE_AVAILABLE:
                    self.logger.warning("数据库库不可用，数据将保存到本地")
                else:
                    self.logger.warning("数据库不可用，数据将保存到本地")
                return self._save_to_local(barcode_data, device_port)
            else:
                self.logger.warning("数据库不可用且本地备份已禁用，数据将丢失")
                return False
        
        try:
            scan_data = {
                'barcode_data': barcode_data,
                'device_port': device_port,
                'scan_time': datetime.now().isoformat()
            }
            
            self.logger.debug(f"尝试上传扫描数据: {scan_data}")
            response = self.client.table('barcode_scans').insert(scan_data).execute()
            
            if response.data:
                self.logger.info(f"扫描数据上传成功: {barcode_data}")
                # 同时保存到本地备份（如果启用）
                if self.config['local_backup_enabled']:
                    self._save_to_local(barcode_data, device_port)
                return True
            else:
                self.logger.error("扫描数据上传失败: 无响应数据")
                # 上传失败时保存到本地
                if self.config['local_backup_enabled']:
                    return self._save_to_local(barcode_data, device_port)
                return False
                
        except Exception as e:
            self.logger.error(f"扫描数据上传失败: {e}")
            # 上传失败时保存到本地
            if self.config['local_backup_enabled']:
                return self._save_to_local(barcode_data, device_port)
            return False

    def _save_to_local(self, barcode_data: str, device_port: str) -> bool:
        """保存数据到本地文件（备份/离线模式）"""
        if not self.config['local_backup_enabled']:
            return False
        
        try:
            local_data = {
                'barcode_data': barcode_data,
                'scan_time': datetime.now().isoformat(),
                'device_port': device_port,
                'synced': False
            }
            
            # 确保本地数据目录存在
            os.makedirs(self.local_data_dir, exist_ok=True)
            
            # 生成文件名（按日期分组）
            date_str = datetime.now().strftime('%Y-%m-%d')
            filename = f"scans_{date_str}.jsonl"
            filepath = os.path.join(self.local_data_dir, filename)
            
            # 追加写入文件
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(json.dumps(local_data, ensure_ascii=False) + '\n')
            
            self.logger.info(f"扫描数据保存到本地: {barcode_data}")
            return True
            
        except Exception as e:
            self.logger.error(f"本地保存失败: {e}")
            return False
    
    def upload_local_backup(self) -> int:
        """
        上传本地备份数据到数据库
        
        Returns:
            成功上传的记录数
        """
        if not self.client or not self.config['database_enabled']:
            self.logger.warning("数据库不可用，无法上传本地备份")
            return 0
        
        if not self.config['auto_sync_enabled']:
            self.logger.info("自动同步已禁用")
            return 0
        
        backup_filename = self.config['local_backup_filename']
        
        try:
            with open(backup_filename, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.logger.info("没有找到本地备份数据")
            return 0
        
        uploaded_count = 0
        failed_data = []
        
        for record in backup_data:
            try:
                scan_data = {
                    'barcode_data': record['barcode_data'],
                    'device_port': record['device_port'],
                    'scan_time': record.get('scan_time', datetime.now().isoformat())
                }
                
                response = self.client.table('barcode_scans').insert(scan_data).execute()
                
                if response.data:
                    uploaded_count += 1
                else:
                    failed_data.append(record)
                    
            except Exception as e:
                self.logger.error(f"上传备份记录失败: {e}")
                failed_data.append(record)
        
        # 更新本地备份文件（只保留失败的记录）
        if failed_data:
            with open(backup_filename, 'w', encoding='utf-8') as f:
                json.dump(failed_data, f, ensure_ascii=False, indent=2)
        else:
            # 所有数据上传成功，删除备份文件
            try:
                os.remove(backup_filename)
            except:
                pass
        
        self.logger.info(f"本地备份上传完成: {uploaded_count} 条记录成功")
        return uploaded_count
    

    
    def get_recent_scans(self, limit: int = 50) -> List[Dict]:
        """获取最近的扫描记录"""
        if not self.client:
            return self._get_local_scans(limit)
        
        try:
            response = self.client.table('barcode_scans')\
                .select('*')\
                .order('scan_time', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            self.logger.error(f"获取扫描记录失败: {e}")
            return []
    
    def _get_local_scans(self, limit: int = 50) -> List[Dict]:
        """从本地备份获取扫描记录"""
        backup_filename = self.config['local_backup_filename']
        
        try:
            with open(backup_filename, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # 按时间倒序排列并限制数量
            backup_data.sort(key=lambda x: x.get('scan_time', ''), reverse=True)
            return backup_data[:limit]
            
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def get_scan_statistics(self) -> Dict[str, Any]:
        """获取扫描统计信息"""
        if not self.client:
            return self._get_local_statistics()
        
        try:
            # 总扫描次数
            total_response = self.client.table('barcode_scans')\
                .select('*', count='exact')\
                .execute()
            
            # 今日扫描次数
            today = datetime.now().date().isoformat()
            today_response = self.client.table('barcode_scans')\
                .select('*', count='exact')\
                .gte('scan_time', today)\
                .execute()
            
            # 不重复条码数
            unique_response = self.client.table('barcode_scans')\
                .select('barcode_data')\
                .execute()
            
            unique_barcodes = len(set(item['barcode_data'] for item in unique_response.data)) if unique_response.data else 0
            
            return {
                'total_scans': total_response.count or 0,
                'today_scans': today_response.count or 0,
                'unique_barcodes': unique_barcodes,
                'last_scan_time': None  # 可以进一步查询
            }
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {'total_scans': 0, 'today_scans': 0, 'unique_barcodes': 0}
    
    def _get_local_statistics(self) -> Dict[str, Any]:
        """从本地备份获取统计信息"""
        backup_filename = self.config['local_backup_filename']
        
        try:
            with open(backup_filename, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            today = datetime.now().date().isoformat()
            today_scans = sum(1 for item in backup_data if item.get('scan_time', '').startswith(today))
            unique_barcodes = len(set(item['barcode_data'] for item in backup_data))

            return {
                'total_scans': len(backup_data),
                'today_scans': today_scans,
                'unique_barcodes': unique_barcodes,
                'last_scan_time': backup_data[0].get('scan_time') if backup_data else None
            }
            
        except (FileNotFoundError, json.JSONDecodeError):
            return {'total_scans': 0, 'today_scans': 0, 'unique_barcodes': 0}


# 全局数据库管理器实例（自动从环境变量初始化）
db_manager = DatabaseManager()

def configure_database_connection(supabase_url: str = None, supabase_key: str = None):
    """
    配置数据库连接
    
    Args:
        supabase_url: Supabase URL（可选，优先从环境变量读取）
        supabase_key: Supabase 密钥（可选，优先从环境变量读取）
    """
    global db_manager
    if supabase_url or supabase_key:
        db_manager.configure_database(supabase_url, supabase_key)
    else:
        # 重新初始化以读取最新的环境变量
        db_manager = DatabaseManager()

def upload_barcode_scan(barcode_data: str, device_port: str) -> bool:
    """上传条码扫描数据"""
    return db_manager.upload_scan_data(barcode_data, device_port)

def upload_scan_data(barcode_data: str, device_port: str) -> bool:
    """上传扫描数据（兼容性函数）"""
    return db_manager.upload_scan_data(barcode_data, device_port)



def get_scan_history(limit: int = 50) -> List[Dict]:
    """获取扫描历史"""
    return db_manager.get_recent_scans(limit)

def get_statistics() -> Dict[str, Any]:
    """获取扫描统计"""
    return db_manager.get_scan_statistics()

def sync_local_data() -> int:
    """同步本地数据到数据库"""
    return db_manager.upload_local_backup()


def check_configuration():
    """检查环境变量配置是否正确"""
    print("=== 数据库配置检查 ===")
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url:
        print("❌ SUPABASE_URL 未设置")
        return False
    elif supabase_url == "https://your-project-id.supabase.co":
        print("❌ SUPABASE_URL 为默认值，请设置实际的项目URL")
        return False
    else:
        print(f"✅ SUPABASE_URL: {supabase_url}")
    
    if not supabase_key:
        print("❌ SUPABASE_KEY 未设置")
        return False
    elif supabase_key.startswith("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."):
        print("❌ SUPABASE_KEY 为默认值，请设置实际的密钥")
        return False
    else:
        print(f"✅ SUPABASE_KEY: {supabase_key[:20]}...")
    
    # 检查 Supabase 库
    if not SUPABASE_AVAILABLE:
        print("❌ supabase 库未安装")
        return False
    else:
        print("✅ supabase 库已安装")
    
    # 测试连接和表结构
    try:
        client = create_client(supabase_url, supabase_key)
        print("✅ 数据库连接成功")
        
        # 检查必要的表是否存在
        try:
            # 测试 barcode_scans 表
            client.table('barcode_scans').select('*').limit(1).execute()
            print("✅ barcode_scans 表可访问")
        except Exception as e:
            print(f"⚠️ barcode_scans 表访问失败: {e}")
            print("   扫描数据将保存到本地备份")
        

        
        print(f"✅ 数据库上传: {'启用' if os.getenv('DATABASE_ENABLED', 'true').lower() == 'true' else '禁用'}")
        print(f"✅ 本地备份: {'启用' if os.getenv('LOCAL_BACKUP_ENABLED', 'true').lower() == 'true' else '禁用'}")
        print(f"✅ 自动同步: {'启用' if os.getenv('AUTO_SYNC_ENABLED', 'true').lower() == 'true' else '禁用'}")
        print(f"✅ 日志级别: {os.getenv('LOG_LEVEL', 'INFO')}")
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

if __name__ == "__main__":
    print("数据库集成模块测试")
    print("=" * 50)
    
    # 检查配置
    if not check_configuration():
        print("\n请创建 .env 文件并配置正确的值")
        print("参考 env_template.txt 文件中的配置示例")
        exit(1)
    
    print("\n=== 功能测试 ===")
    
    # 注意：数据库管理器已自动从环境变量初始化
    # 不需要手动调用 configure_database_connection()
    

    
    # 上传测试数据
    print("上传测试数据...")
    success = upload_barcode_scan(
        "1234567890123",
        "COM3"
    )
    
    print(f"测试数据上传: {'成功' if success else '失败'}")
    
    # 获取统计信息
    print("获取统计信息...")
    stats = get_statistics()
    print(f"扫描统计: {stats}")
    
    # 测试本地数据同步
    if os.getenv('AUTO_SYNC_ENABLED', 'true').lower() == 'true':
        print("测试本地数据同步...")
        synced = sync_local_data()
        print(f"同步了 {synced} 条记录")
    

    
    print("\n✅ 测试完成！")