"""
更新现有数据的状态字段
根据条码数据前缀自动设置状态
"""
import os
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def parse_barcode_status(barcode_data: str) -> str:
    """解析条码数据中的状态信息"""
    if barcode_data.startswith('1@'):
        return '已切割'
    elif barcode_data.startswith('2@'):
        return '已清角'
    elif barcode_data.startswith('3@'):
        return '已入库'
    else:
        return None

def update_existing_records():
    """更新现有记录的状态字段"""
    print("🔄 开始更新现有记录的状态字段...")
    
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
        # 1. 获取所有状态为NULL的记录
        print("📋 获取需要更新的记录...")
        response = requests.get(
            f"{api_url}/barcode_scans?status=is.null&order=id.asc",
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ 获取记录失败: HTTP {response.status_code}")
            return False
        
        records = response.json()
        print(f"📊 找到 {len(records)} 条需要更新的记录")
        
        if not records:
            print("✅ 没有需要更新的记录")
            return True
        
        # 2. 逐条更新记录
        updated_count = 0
        for record in records:
            record_id = record['id']
            barcode_data = record['barcode_data']
            
            # 解析状态
            status = parse_barcode_status(barcode_data)
            
            if status:
                # 更新记录
                update_data = {'status': status}
                
                update_response = requests.patch(
                    f"{api_url}/barcode_scans?id=eq.{record_id}",
                    headers=headers,
                    json=update_data,
                    timeout=10
                )
                
                if update_response.status_code in [200, 204]:
                    print(f"✅ 更新记录 {record_id}: {barcode_data} -> {status}")
                    updated_count += 1
                else:
                    print(f"❌ 更新记录 {record_id} 失败: HTTP {update_response.status_code}")
            else:
                print(f"⚠️ 记录 {record_id} 无法解析状态: {barcode_data}")
        
        print(f"\n🎉 更新完成！成功更新了 {updated_count} 条记录")
        return True
        
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        return False

if __name__ == "__main__":
    update_existing_records()