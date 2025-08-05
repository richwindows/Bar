#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多设备扫码枪管理器 - Windows打包脚本
使用PyInstaller将Python应用程序打包成Windows可执行文件
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_pyinstaller():
    """检查PyInstaller是否已安装"""
    try:
        import PyInstaller
        print("✅ PyInstaller已安装")
        return True
    except ImportError:
        print("❌ PyInstaller未安装")
        return False

def install_pyinstaller():
    """安装PyInstaller"""
    print("📦 正在安装PyInstaller...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ PyInstaller安装失败: {e}")
        return False

def clean_build_dirs():
    """清理之前的构建目录"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"🧹 清理目录: {dir_name}")
            shutil.rmtree(dir_name)
    
    # 清理.spec文件
    spec_files = list(Path('.').glob('*.spec'))
    for spec_file in spec_files:
        print(f"🧹 清理文件: {spec_file}")
        spec_file.unlink()

def create_version_info():
    """创建版本信息文件"""
    version_info = '''
# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
# filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
# Set not needed items to zero 0.
filevers=(1,0,0,0),
prodvers=(1,0,0,0),
# Contains a bitmask that specifies the valid bits 'flags'r
mask=0x3f,
# Contains a bitmask that specifies the Boolean attributes of the file.
flags=0x0,
# The operating system for which this file was designed.
# 0x4 - NT and there is no need to change it.
OS=0x4,
# The general type of file.
# 0x1 - the file is an application.
fileType=0x1,
# The function of the file.
# 0x0 - the function is not defined for this fileType
subtype=0x0,
# Creation date and time stamp.
date=(0, 0)
),
  kids=[
StringFileInfo(
  [
  StringTable(
    u'080404B0',
    [StringStruct(u'CompanyName', u'多设备扫码枪管理器'),
    StringStruct(u'FileDescription', u'多设备扫码枪管理器'),
    StringStruct(u'FileVersion', u'1.0.0.0'),
    StringStruct(u'InternalName', u'MultiScannerApp'),
    StringStruct(u'LegalCopyright', u'Copyright © 2025'),
    StringStruct(u'OriginalFilename', u'MultiScannerApp.exe'),
    StringStruct(u'ProductName', u'多设备扫码枪管理器'),
    StringStruct(u'ProductVersion', u'1.0.0.0')])
  ]), 
VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
'''
    
    with open('version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_info)
    print("📝 版本信息文件已创建")

def build_executable():
    """构建可执行文件"""
    print("🔨 开始构建可执行文件...")
    
    # PyInstaller命令参数
    cmd = [
        'pyinstaller',
        '--onefile',                    # 打包成单个文件
        '--windowed',                   # 不显示控制台窗口
        '--name=MultiScannerApp',       # 可执行文件名称
        '--icon=scanner.ico',           # 图标文件（如果存在）
        '--version-file=version_info.txt',  # 版本信息
        '--add-data=.env;.',            # 包含环境配置文件
        '--hidden-import=serial',       # 确保serial模块被包含
        '--hidden-import=serial.tools.list_ports',
        '--hidden-import=winsound',
        '--hidden-import=winreg',
        '--clean',                      # 清理临时文件
        'multi_scanner.py'              # 主程序文件
    ]
    
    # 如果图标文件不存在，移除图标参数
    if not os.path.exists('scanner.ico'):
        cmd = [arg for arg in cmd if not arg.startswith('--icon')]
        print("⚠️ 未找到图标文件scanner.ico，将使用默认图标")
    
    try:
        # 执行PyInstaller命令
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ 构建成功！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False

def copy_additional_files():
    """复制额外的文件到dist目录"""
    dist_dir = Path('dist')
    if not dist_dir.exists():
        print("❌ dist目录不存在")
        return
    
    # 需要复制的文件
    files_to_copy = [
        '.env',
        'requirements.txt',
        'database_setup.sql'
    ]
    
    for file_name in files_to_copy:
        if os.path.exists(file_name):
            shutil.copy2(file_name, dist_dir)
            print(f"📋 已复制: {file_name}")
    
    # 创建README文件
    readme_content = '''
多设备扫码枪管理器 v1.0
========================

使用说明：
1. 双击 MultiScannerApp.exe 启动程序
2. 首次运行时，请确保.env文件中的数据库配置正确
3. 程序会自动检测可用的串口设备
4. 支持多设备同时扫描和数据管理

文件说明：
- MultiScannerApp.exe: 主程序
- .env: 数据库配置文件
- requirements.txt: Python依赖列表
- database_setup.sql: 数据库初始化脚本

技术支持：
如有问题，请检查程序日志或联系技术支持。
'''
    
    with open(dist_dir / 'README.txt', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print("📋 已创建README.txt")

def main():
    """主函数"""
    print("🚀 多设备扫码枪管理器 - Windows打包工具")
    print("=" * 50)
    
    # 检查PyInstaller
    if not check_pyinstaller():
        if not install_pyinstaller():
            print("❌ 无法安装PyInstaller，请手动安装")
            return False
    
    # 清理之前的构建
    clean_build_dirs()
    
    # 创建版本信息
    create_version_info()
    
    # 构建可执行文件
    if not build_executable():
        return False
    
    # 复制额外文件
    copy_additional_files()
    
    print("\n" + "=" * 50)
    print("✅ 打包完成！")
    print(f"📁 可执行文件位置: {os.path.abspath('dist')}")
    print("🎉 您可以在dist目录中找到MultiScannerApp.exe")
    
    return True

if __name__ == '__main__':
    try:
        success = main()
        if success:
            input("\n按Enter键退出...")
        else:
            input("\n打包失败，按Enter键退出...")
    except KeyboardInterrupt:
        print("\n❌ 用户取消操作")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        input("按Enter键退出...")