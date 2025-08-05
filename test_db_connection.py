"""
测试数据库连接脚本
"""
import os
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_database_connection():
    """测试数据库连接"""
    print("🔍 开始测试数据库连接...")
    
    # 获取配置
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    print(f"📍 SUPABASE_URL: {supabase_url}")
    print(f"🔑 SUPABASE_KEY: {supabase_key[:20]}..." if supabase_key else "🔑 SUPABASE_KEY: 未设置")
    
    if not supabase_url or not supabase_key:
        print("❌ 数据库配置不完整")
        return False
    
    # 构建API端点
    api_url = f"{supabase_url}/rest/v1"
    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
    }
    
    try:
        print(f"🌐 测试连接到: {api_url}/barcode_scans")
        response = requests.get(
            f"{api_url}/barcode_scans?limit=1",
            headers=headers,
            timeout=10
        )
        
        print(f"📊 HTTP状态码: {response.status_code}")
        print(f"📝 响应内容: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("✅ 数据库连接成功！")
            return True
        else:
            print(f"❌ 数据库连接失败: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        return False

if __name__ == "__main__":
    test_database_connection()