"""
条码扫描数据库集成模块 - HTTP版本
使用HTTP请求直接与Supabase API通信，避免库兼容性问题
"""

import json
import os
import requests
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

class DatabaseManagerHTTP:
    """基于HTTP请求的数据库管理器"""
    
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
        
        # 构建API端点
        if self.supabase_url:
            self.api_url = f"{self.supabase_url}/rest/v1"
            self.headers = {
                'apikey': self.supabase_key,
                'Authorization': f'Bearer {self.supabase_key}',
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal'
            }
        else:
            self.api_url = None
            self.headers = None
        
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
        if self.supabase_url and self.supabase_key:
            self.logger.info("HTTP数据库连接配置成功")
        else:
            self.logger.warning("未找到数据库配置，将使用离线模式")
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        if not self.api_url or not self.headers:
            return False
        
        try:
            response = requests.get(
                f"{self.api_url}/barcode_scans?limit=1",
                headers=self.headers,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"数据库连接测试失败: {e}")
            return False
    
    def upload_scan_data(self, barcode_data: str, device_port: str) -> bool:
        """
        上传扫描数据
        
        Args:
            barcode_data: 条码数据
            device_port: 设备端口
            
        Returns:
            上传是否成功
        """
        if not self.api_url or not self.config['database_enabled']:
            if self.config['local_backup_enabled']:
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
            
            response = requests.post(
                f"{self.api_url}/barcode_scans",
                headers=self.headers,
                json=scan_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                self.logger.info(f"扫描数据上传成功: {barcode_data}")
                # 同时保存到本地备份（如果启用）
                if self.config['local_backup_enabled']:
                    self._save_to_local(barcode_data, device_port)
                return True
            else:
                self.logger.error(f"扫描数据上传失败: HTTP {response.status_code}")
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
    
    def sync_local_data(self) -> int:
        """
        同步本地数据到数据库
        
        Returns:
            成功上传的记录数
        """
        if not self.api_url or not self.config['database_enabled']:
            self.logger.warning("数据库不可用，无法上传本地备份")
            return 0
        
        if not self.config['auto_sync_enabled']:
            self.logger.info("自动同步已禁用")
            return 0
        
        uploaded_count = 0
        
        # 同步JSONL格式的本地数据
        try:
            for filename in os.listdir(self.local_data_dir):
                if filename.startswith('scans_') and filename.endswith('.jsonl'):
                    filepath = os.path.join(self.local_data_dir, filename)
                    uploaded_count += self._sync_jsonl_file(filepath)
        except FileNotFoundError:
            self.logger.info("没有找到本地数据目录")
        
        return uploaded_count
    
    def _sync_jsonl_file(self, filepath: str) -> int:
        """同步单个JSONL文件"""
        uploaded_count = 0
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            unsynced_lines = []
            
            for line in lines:
                try:
                    record = json.loads(line.strip())
                    if not record.get('synced', False):
                        # 尝试上传
                        scan_data = {
                            'barcode_data': record['barcode_data'],
                            'device_port': record['device_port'],
                            'scan_time': record.get('scan_time', datetime.now().isoformat())
                        }
                        
                        response = requests.post(
                            f"{self.api_url}/barcode_scans",
                            headers=self.headers,
                            json=scan_data,
                            timeout=10
                        )
                        
                        if response.status_code in [200, 201]:
                            record['synced'] = True
                            uploaded_count += 1
                            self.logger.debug(f"同步成功: {record['barcode_data']}")
                    
                    unsynced_lines.append(json.dumps(record, ensure_ascii=False) + '\n')
                    
                except Exception as e:
                    self.logger.error(f"同步记录失败: {e}")
                    unsynced_lines.append(line)
            
            # 更新文件
            if uploaded_count > 0:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.writelines(unsynced_lines)
                
        except Exception as e:
            self.logger.error(f"同步文件失败 {filepath}: {e}")
        
        return uploaded_count


# 全局数据库管理器实例
db_manager = DatabaseManagerHTTP()

def upload_barcode_scan(barcode_data: str, device_port: str) -> bool:
    """上传条码扫描数据"""
    return db_manager.upload_scan_data(barcode_data, device_port)

def sync_local_data() -> int:
    """同步本地数据到数据库"""
    return db_manager.sync_local_data()

def test_database_connection() -> bool:
    """测试数据库连接"""
    return db_manager.test_connection()