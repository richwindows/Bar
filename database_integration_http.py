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
    
    def _parse_barcode_status(self, barcode_data: str) -> tuple:
        """
        解析条码数据中的状态信息
        
        Args:
            barcode_data: 原始条码数据
            
        Returns:
            (clean_barcode_data, status): 清理后的条码数据和状态
        """
        if barcode_data.startswith('0@'):
            return barcode_data[2:], '已排产'
        elif barcode_data.startswith('1@'):
            return barcode_data[2:], '已切割'
        elif barcode_data.startswith('2@'):
            return barcode_data[2:], '已清角'
        elif barcode_data.startswith('3@'):
            return barcode_data[2:], '已入库'
        elif barcode_data.startswith('4@'):
            return barcode_data[2:], '部分出库'
        elif barcode_data.startswith('5@'):
            return barcode_data[2:], '已出库'
        else:
            return barcode_data, None

    def upload_scan_data(self, barcode_data: str, device_port: str) -> bool:
        """
        上传扫描数据 - 使用现有barcode_scans表
        
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
            # 解析条码数据中的状态信息
            clean_barcode_data, status = self._parse_barcode_status(barcode_data)
            
            if not status:
                self.logger.warning(f"无法识别状态的条码: {barcode_data}")
                return False
            
            # 首先检查记录是否存在
            existing_record = self._get_existing_record(clean_barcode_data)
            
            if existing_record:
                # 更新现有记录
                return self._update_existing_record(existing_record, status, device_port)
            else:
                # 创建新记录
                return self._create_new_record(clean_barcode_data, status, device_port)
                
        except Exception as e:
            self.logger.error(f"扫描数据上传失败: {e}")
            # 上传失败时保存到本地
            if self.config['local_backup_enabled']:
                return self._save_to_local(barcode_data, device_port)
            return False

    def _get_existing_record(self, barcode_data: str) -> dict:
        """获取现有记录"""
        try:
            response = requests.get(
                f"{self.api_url}/barcode_scans?barcode_data=eq.{barcode_data}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                records = response.json()
                return records[0] if records else None
            else:
                self.logger.error(f"查询现有记录失败: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"查询现有记录失败: {e}")
            return None

    def _create_new_record(self, barcode_data: str, status: str, device_port: str) -> bool:
        """创建新记录 - 兼容现有表结构"""
        try:
            current_time = datetime.now().isoformat()
            
            # 构建新记录数据 - 只使用存在的字段
            scan_data = {
                'barcode_data': barcode_data,
                'device_port': device_port
            }
            
            # 根据状态添加对应的状态字段
            if status:
                status_mapping = {
                    '已排产': ('status_1_scheduled', 'status_1_time'),
                    '已切割': ('status_2_cut', 'status_2_time'),
                    '已清角': ('status_3_cleaned', 'status_3_time'),
                    '已入库': ('status_4_stored', 'status_4_time'),
                    '部分出库': ('status_5_partial_out', 'status_5_time'),
                    '已出库': ('status_6_shipped', 'status_6_time')
                }
                
                if status in status_mapping:
                    status_field, time_field = status_mapping[status]
                    scan_data[status_field] = True
                    scan_data[time_field] = current_time
            
            self.logger.debug(f"尝试创建记录，数据: {scan_data}")
            
            # 执行插入
            response = requests.post(
                f"{self.api_url}/barcode_scans",
                headers=self.headers,
                json=scan_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                self.logger.info(f"新条码记录创建成功: {barcode_data} (状态: {status})")
                # 同时保存到本地备份（如果启用）
                if self.config['local_backup_enabled']:
                    self._save_to_local(f"{self._get_status_prefix(status)}@{barcode_data}", device_port)
                return True
            else:
                # 记录详细的错误信息
                error_text = response.text if hasattr(response, 'text') else 'Unknown error'
                self.logger.error(f"新条码记录创建失败: HTTP {response.status_code}, 响应: {error_text}")
                self.logger.error(f"发送的数据: {scan_data}")
                
                # 如果是400错误，可能是字段不存在，尝试只用基本字段重试
                if response.status_code == 400:
                    return self._create_basic_record(barcode_data, status, device_port)
                
                return False
                
        except Exception as e:
            self.logger.error(f"创建新记录失败: {e}")
            return False

    def _create_basic_record(self, barcode_data: str, status: str, device_port: str) -> bool:
        """创建基本记录 - 只使用最基本字段"""
        try:
            # 只使用最基本的字段
            scan_data = {
                'barcode_data': barcode_data,
                'device_port': device_port
            }
            
            self.logger.debug(f"尝试创建基本记录，数据: {scan_data}")
            
            # 执行插入
            response = requests.post(
                f"{self.api_url}/barcode_scans",
                headers=self.headers,
                json=scan_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                self.logger.info(f"基本条码记录创建成功: {barcode_data}")
                # 同时保存到本地备份（如果启用）
                if self.config['local_backup_enabled']:
                    self._save_to_local(f"{self._get_status_prefix(status)}@{barcode_data}", device_port)
                return True
            else:
                error_text = response.text if hasattr(response, 'text') else 'Unknown error'
                self.logger.error(f"基本条码记录创建失败: HTTP {response.status_code}, 响应: {error_text}")
                return False
                
        except Exception as e:
            self.logger.error(f"创建基本记录失败: {e}")
            return False

    def _update_existing_record(self, existing_record: dict, status: str, device_port: str) -> bool:
        """更新现有记录的状态 - 兼容现有表结构"""
        try:
            current_time = datetime.now().isoformat()
            
            # 构建更新数据 - 只使用存在的字段
            update_data = {
                'device_port': device_port
            }
            
            # 根据状态添加对应的状态字段
            if status:
                status_mapping = {
                    '已排产': ('status_1_scheduled', 'status_1_time'),
                    '已切割': ('status_2_cut', 'status_2_time'),
                    '已清角': ('status_3_cleaned', 'status_3_time'),
                    '已入库': ('status_4_stored', 'status_4_time'),
                    '部分出库': ('status_5_partial_out', 'status_5_time'),
                    '已出库': ('status_6_shipped', 'status_6_time')
                }
                
                if status in status_mapping:
                    status_field, time_field = status_mapping[status]
                    update_data[status_field] = True
                    update_data[time_field] = current_time
            
            self.logger.debug(f"尝试更新记录，数据: {update_data}")
            
            # 执行更新
            response = requests.patch(
                f"{self.api_url}/barcode_scans?id=eq.{existing_record['id']}",
                headers=self.headers,
                json=update_data,
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                self.logger.info(f"条码状态更新成功: {existing_record['barcode_data']} -> {status}")
                # 同时保存到本地备份（如果启用）
                if self.config['local_backup_enabled']:
                    self._save_to_local(f"{self._get_status_prefix(status)}@{existing_record['barcode_data']}", device_port)
                return True
            else:
                error_text = response.text if hasattr(response, 'text') else 'Unknown error'
                self.logger.error(f"条码状态更新失败: HTTP {response.status_code}, 响应: {error_text}")
                self.logger.error(f"发送的数据: {update_data}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新现有记录失败: {e}")
            return False

    def _get_status_prefix(self, status: str) -> str:
        """根据状态获取前缀"""
        prefix_mapping = {
            '已排产': '0',
            '已切割': '1',
            '已清角': '2',
            '已入库': '3',
            '部分出库': '4',
            '已出库': '5'
        }
        return prefix_mapping.get(status, '')

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
            
            if response.status_code == 200:
                self.logger.info("数据库连接测试成功")
                return True
            else:
                self.logger.error(f"数据库连接测试失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"数据库连接测试失败: {e}")
            return False

    def get_scan_statistics(self) -> Dict[str, Any]:
        """获取扫描统计信息 - 使用视图查询"""
        if not self.api_url:
            return self._get_local_statistics()
        
        try:
            # 使用视图查询统计数据
            response = requests.get(
                f"{self.api_url}/barcode_scans_with_status?select=current_status",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                records = response.json()
                
                # 统计各状态数量
                status_counts = {}
                for record in records:
                    status = record.get('current_status', '未知状态')
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                stats = {
                    '已排产': status_counts.get('已排产', 0),
                    '已切割': status_counts.get('已切割', 0),
                    '已清角': status_counts.get('已清角', 0),
                    '已入库': status_counts.get('已入库', 0),
                    '部分出库': status_counts.get('部分出库', 0),
                    '已出库': status_counts.get('已出库', 0),
                    'total': len(records)
                }
                
                return stats
            else:
                self.logger.error(f"获取统计信息失败: HTTP {response.status_code}")
                return self._get_local_statistics()
                
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return self._get_local_statistics()

    def _save_to_local(self, barcode_data: str, device_port: str) -> bool:
        """保存数据到本地文件（备份/离线模式）"""
        if not self.config['local_backup_enabled']:
            return False
        
        try:
            # 解析条码数据中的状态信息
            clean_barcode_data, status = self._parse_barcode_status(barcode_data)
            
            local_data = {
                'barcode_data': clean_barcode_data,
                'scan_time': datetime.now().isoformat(),
                'device_port': device_port,
                'status': status,
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
            
            self.logger.info(f"扫描数据保存到本地: {clean_barcode_data} (状态: {status or '无'})")
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
                            'scan_time': record.get('scan_time', datetime.now().isoformat()),
                            'status': record.get('status')
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
                            self.logger.debug(f"同步成功: {record['barcode_data']} (状态: {record.get('status', '无')})")
                    
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


# 在文件末尾添加全局函数，保持与主程序的兼容性

# 创建全局数据库管理器实例
_db_manager = DatabaseManagerHTTP()

def upload_scan_data(barcode_data: str, device_port: str) -> bool:
    """
    全局函数：上传扫描数据
    直接调用版本
    
    Args:
        barcode_data: 条码数据
        device_port: 设备端口
        
    Returns:
        上传是否成功
    """
    return _db_manager.upload_scan_data(barcode_data, device_port)

def upload_barcode_scan(barcode_data: str, device_port: str) -> bool:
    """
    全局函数：上传条码扫描数据
    保持与主程序的兼容性
    
    Args:
        barcode_data: 条码数据
        device_port: 设备端口
        
    Returns:
        上传是否成功
    """
    return _db_manager.upload_scan_data(barcode_data, device_port)

def sync_local_data() -> int:
    """
    全局函数：同步本地数据到数据库
    保持与主程序的兼容性
    
    Returns:
        同步的记录数量
    """
    return _db_manager.sync_local_data()

def get_scan_statistics() -> dict:
    """
    全局函数：获取扫描统计信息
    保持与主程序的兼容性
    
    Returns:
        统计信息字典
    """
    return _db_manager.get_scan_statistics()

def test_database_connection() -> bool:
    """测试数据库连接"""
    return _db_manager.test_connection()