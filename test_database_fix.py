"""
测试数据库连接和修复
"""
import os
import requests
from dotenv import load_dotenv
import time
from datetime import datetime

# 加载环境变量
load_dotenv()

def check_table_structure():
    """检查数据库表结构"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ 数据库配置不完整")
        return False
    
    api_url = f"{supabase_url}/rest/v1"
    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        print("🔍 检查表结构...")
        
        # 尝试获取表的一条记录来了解字段结构
        response = requests.get(
            f"{api_url}/barcode_scans?limit=1",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data:
                print("📋 当前表字段:")
                for key in data[0].keys():
                    print(f"  - {key}")
            else:
                print("📋 表为空，无法获取字段信息")
            return True
        else:
            print(f"❌ 无法获取表结构: HTTP {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 检查表结构失败: {e}")
        return False

def test_status_insert():
    """测试状态插入功能"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    api_url = f"{supabase_url}/rest/v1"
    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        print("🔄 测试状态插入...")
        
        current_time = datetime.now().isoformat()
        
        # 测试插入带状态的记录
        test_data = {
            'barcode_data': 'STATUS-TEST-' + str(int(time.time())),
            'device_port': 'TEST',
            'status_1_scheduled': True,
            'status_1_time': current_time
        }
        
        insert_response = requests.post(
            f"{api_url}/barcode_scans",
            headers=headers,
            json=test_data,
            timeout=10
        )
        
        if insert_response.status_code in [200, 201]:
            print("✅ 状态记录插入成功")
            return True
        else:
            print(f"❌ 状态记录插入失败: HTTP {insert_response.status_code}")
            print(f"响应内容: {insert_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 状态插入测试失败: {e}")
        return False

def test_basic_insert():
    """测试基本插入功能"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    api_url = f"{supabase_url}/rest/v1"
    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        print("🔄 测试基本插入...")
        
        # 只使用最基本的字段（不包含scan_time）
        test_data = {
            'barcode_data': 'BASIC-TEST-' + str(int(time.time())),
            'device_port': 'TEST'
        }
        
        insert_response = requests.post(
            f"{api_url}/barcode_scans",
            headers=headers,
            json=test_data,
            timeout=10
        )
        
        if insert_response.status_code in [200, 201]:
            print("✅ 基本记录插入成功")
            return True
        else:
            print(f"❌ 记录插入失败: HTTP {insert_response.status_code}")
            print(f"响应内容: {insert_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 插入测试失败: {e}")
        return False

def test_database_connection():
    """测试数据库连接"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ 数据库配置不完整")
        return False
    
    api_url = f"{supabase_url}/rest/v1"
    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        # 测试连接
        print("🔄 测试数据库连接...")
        response = requests.get(
            f"{api_url}/barcode_scans?limit=1",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ 数据库连接成功")
            return True
        else:
            print(f"❌ 数据库连接失败: HTTP {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 数据库测试失败: {e}")
        return False

if __name__ == "__main__":
    print("🧪 开始数据库诊断...")
    
    # 1. 测试连接
    if test_database_connection():
        # 2. 检查表结构
        if check_table_structure():
            # 3. 测试基本插入
            if test_basic_insert():
                # 4. 测试状态插入
                test_status_insert()
    
    print("\n📊 诊断完成")