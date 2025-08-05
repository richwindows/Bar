"""
测试状态解析功能
"""

def parse_barcode_status(barcode_data: str) -> tuple:
    """解析条码数据中的状态信息"""
    if barcode_data.startswith('1@'):
        return barcode_data[2:], '已切割'
    elif barcode_data.startswith('2@'):
        return barcode_data[2:], '已清角'
    elif barcode_data.startswith('3@'):
        return barcode_data[2:], '已入库'
    else:
        return barcode_data, None

def test_status_parsing():
    """测试状态解析功能"""
    print("🧪 测试状态解析功能...")
    
    test_cases = [
        "1@Rich-07212025-03",
        "2@Rich-07212025-04", 
        "3@Rich-07212025-05",
        "Rich-07212025-10",
        "123456789012",
        "2@Rich-052125-16-19",
        "3@Rich-052125-16-17"
    ]
    
    for barcode in test_cases:
        clean_barcode, status = parse_barcode_status(barcode)
        print(f"原始: {barcode}")
        print(f"  -> 条码: {clean_barcode}")
        print(f"  -> 状态: {status or '无状态'}")
        print()

if __name__ == "__main__":
    test_status_parsing()