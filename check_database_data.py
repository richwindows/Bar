"""
检查数据库中的实际数据
"""
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

# 加载环境变量
load_dotenv()

def check_database_data():
    """检查数据库中的数据"""
    print("🔍 检查数据库中的实际数据...")
    
    # 获取配置
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ 数据库配置不完整")
        return False
    
    # 构建API端点
    api_url = f"{supabase_url}/rest/v1"
    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        # 1. 检查表是否存在
        print("\n📋 检查 barcode_scans 表...")
        response = requests.get(
            f"{api_url}/barcode_scans?limit=5&order=scan_time.desc",
            headers=headers,
            timeout=10
        )
        
        print(f"📊 HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 表存在，找到 {len(data)} 条记录")
            
            if data:
                print("\n📝 最新的5条记录:")
                for i, record in enumerate(data, 1):
                    print(f"  {i}. ID: {record.get('id')}")
                    print(f"     条码: {record.get('barcode_data')}")
                    print(f"     设备: {record.get('device_port')}")
                    print(f"     时间: {record.get('scan_time')}")
                    print()
            else:
                print("⚠️ 表存在但没有数据")
                
        elif response.status_code == 404:
            print("❌ barcode_scans 表不存在")
            
        else:
            print(f"❌ 查询失败: HTTP {response.status_code}")
            print(f"响应内容: {response.text}")
            
        # 2. 检查总记录数
        print("\n📊 检查总记录数...")
        count_response = requests.get(
            f"{api_url}/barcode_scans?select=count",
            headers={**headers, 'Prefer': 'count=exact'},
            timeout=10
        )
        
        if count_response.status_code == 200:
            count_header = count_response.headers.get('Content-Range', '')
            if count_header:
                total_count = count_header.split('/')[-1]
                print(f"📈 数据库中总共有 {total_count} 条记录")
            else:
                print("📈 无法获取总记录数")
        
        # 3. 检查今天的记录
        print("\n📅 检查今天的记录...")
        today = datetime.now().strftime('%Y-%m-%d')
        today_response = requests.get(
            f"{api_url}/barcode_scans?scan_time=gte.{today}T00:00:00&order=scan_time.desc",
            headers=headers,
            timeout=10
        )
        
        if today_response.status_code == 200:
            today_data = today_response.json()
            print(f"📅 今天有 {len(today_data)} 条扫描记录")
            
            if today_data:
                print("最新的3条今日记录:")
                for i, record in enumerate(today_data[:3], 1):
                    print(f"  {i}. {record.get('barcode_data')} - {record.get('scan_time')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False

if __name__ == "__main__":
    check_database_data()