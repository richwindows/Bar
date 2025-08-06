#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多设备扫码枪同时扫描程序
支持同时连接多台扫码枪进行并发扫描
"""

import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import json
import os
from datetime import datetime
import uuid
import winsound  # Windows系统声音播放
from tkinter import font

# 导入数据库集成模块
try:
    # 优先尝试HTTP版本
    import database_integration_http as db
    DATABASE_AVAILABLE = True
    print("✅ 数据库模块加载成功 (HTTP版本)")
except Exception as e:
    try:
        # 备用原版本
        import database_integration as db
        DATABASE_AVAILABLE = True
        print("✅ 数据库模块加载成功")
    except Exception as e2:
        DATABASE_AVAILABLE = False
        print(f"⚠️ 数据库模块加载失败: {e2}")
        print("程序将以离线模式运行，数据将保存到本地文件")


class ScannerDevice:
    """单个扫码设备类"""
    
    def __init__(self, device_id, port, baudrate=9600, databits=8, parity='N', stopbits=1.0, timeout=1.0):
        self.device_id = device_id
        self.port = port
        self.baudrate = baudrate
        self.databits = databits
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        
        self.serial_connection = None
        self.is_connected = False
        self.is_scanning = False
        self.scan_thread = None
        self.scan_count = 0
        self.last_scan_time = None
        self.device_name = f"设备{device_id}({port})"
        

        
        # 重连相关
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.last_error_time = None
        
        # 重复扫描检测
        self.recent_scans = {}  # {data: timestamp}
        self.duplicate_window = 5.0  # 5秒内的重复扫描将被过滤
    
    def get_serial_params(self):
        """获取串口参数"""
        parity_map = {
            'N': serial.PARITY_NONE,
            'E': serial.PARITY_EVEN,
            'O': serial.PARITY_ODD,
            'M': serial.PARITY_MARK,
            'S': serial.PARITY_SPACE
        }
        
        stopbits_map = {
            1.0: serial.STOPBITS_ONE,
            1.5: serial.STOPBITS_ONE_POINT_FIVE,
            2.0: serial.STOPBITS_TWO
        }
        
        return {
            'baudrate': self.baudrate,
            'bytesize': self.databits,
            'parity': parity_map.get(self.parity, serial.PARITY_NONE),
            'stopbits': stopbits_map.get(self.stopbits, serial.STOPBITS_ONE),
            'timeout': self.timeout
        }
    
    def get_device_settings_dict(self):
        """获取设备设置字典"""
        return {
            'baudrate': self.baudrate,
            'databits': self.databits,
            'parity': self.parity,
            'stopbits': self.stopbits,
            'timeout': self.timeout,
            'device_id': self.device_id
        }

    def is_duplicate_scan(self, data):
        """检查是否为重复扫描"""
        current_time = time.time()
        
        # 清理过期的扫描记录
        expired_keys = []
        for scan_data, timestamp in self.recent_scans.items():
            if current_time - timestamp > self.duplicate_window:
                expired_keys.append(scan_data)
        
        for key in expired_keys:
            del self.recent_scans[key]
        
        # 检查当前扫描是否重复
        if data in self.recent_scans:
            return True
        
        # 记录新的扫描
        self.recent_scans[data] = current_time
        return False


class MultiScannerApp:
    """多设备扫码程序主类"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("多设备扫码枪管理器")
        self.root.geometry("1100x700")
        self.root.minsize(950, 600)
        
        # 在初始化时清理可能的孤立串口连接
        self.cleanup_orphaned_serial_connections()
        
        # 设置现代化主题
        self.setup_theme()
        
        # 设备管理
        self.devices = {}  # device_id -> ScannerDevice
        self.next_device_id = 1
        self.total_scan_count = 0
        
        # 数据回调
        self.data_callbacks = []
        
        # 当天扫描数据缓存（用于去重）
        self.today_scanned_data = set()
        self.today_cache_file = f"today_scans_{datetime.now().strftime('%Y%m%d')}.json"
        
        # 声音提示设置
        self.sound_enabled = tk.BooleanVar(value=True)
        
        # 自动连接设置
        self.auto_connect_enabled = tk.BooleanVar(value=False)
        
        # 开机启动设置
        self.startup_enabled = tk.BooleanVar(value=False)
        
        # 初始化工具提示
        self.tooltips = []
        
        # 创建界面
        self.create_widgets()
        
        # 数据库状态检查
        if DATABASE_AVAILABLE:
            self.check_database_status()
        
        # 刷新可用端口
        self.refresh_ports()
        
        # 加载保存的设备配置
        self.load_saved_devices()
        
        # 加载当天已扫描的数据
        self.load_today_scanned_data()
        
        # 清理过期缓存文件
        self.cleanup_expired_cache_files()
        
        # 加载设置
        self.load_settings()
        
        # 启动时自动连接设备（如果启用）
        self.auto_connect_devices_on_startup()
    
    def setup_theme(self):
        """设置现代化主题"""
        try:
            # 设置ttk主题
            style = ttk.Style()
            
            # 尝试使用现代主题
            available_themes = style.theme_names()
            if 'vista' in available_themes:
                style.theme_use('vista')
            elif 'clam' in available_themes:
                style.theme_use('clam')
            elif 'alt' in available_themes:
                style.theme_use('alt')
            
            # 自定义样式
            style.configure('Title.TLabel', font=('Segoe UI', 18, 'bold'), foreground='#2c3e50')
            style.configure('Heading.TLabel', font=('Segoe UI', 12, 'bold'), foreground='#34495e')
            style.configure('Status.TLabel', font=('Segoe UI', 9), foreground='#7f8c8d')
             
             # 按钮样式
            style.configure('Action.TButton', 
                           font=('Segoe UI', 9, 'bold'),
                           padding=(10, 5))
             
            style.configure('Success.TButton', 
                           font=('Segoe UI', 9, 'bold'),
                           padding=(10, 5))
             
            style.configure('Warning.TButton', 
                           font=('Segoe UI', 9, 'bold'),
                           padding=(10, 5))
             
             # Treeview样式
            style.configure('Treeview', 
                           font=('Segoe UI', 9),
                           rowheight=25)
            style.configure('Treeview.Heading', 
                           font=('Segoe UI', 9, 'bold'),
                           padding=(5, 5))
             
             # LabelFrame样式
            style.configure('TLabelframe', 
                           borderwidth=2,
                           relief='groove')
            style.configure('TLabelframe.Label', 
                           font=('Segoe UI', 10, 'bold'),
                           foreground='#2c3e50')
             
             # Separator样式
            style.configure('TSeparator', background='#bdc3c7')
            
        except Exception as e:
            print(f"主题设置失败: {e}")
    
    def create_widgets(self):
        """创建界面元素"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=2)  # 左侧控制区域权重
        main_frame.columnconfigure(1, weight=3)  # 右侧数据区域权重更大
        main_frame.rowconfigure(1, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="多设备扫码枪管理器", style='Title.TLabel')
        title_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 15))
        
        # 左侧控制区域
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 15))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=3)
        left_frame.rowconfigure(1, weight=1)
        
        # 设备管理区域
        self.create_device_management(left_frame)
        
        # 全局控制按钮
        self.create_global_controls(left_frame)
        
        # 右侧数据显示区域
        self.create_data_display(main_frame)
        
        # 状态栏
        self.create_status_bar(main_frame)
    
    def create_device_management(self, parent):
        """创建设备管理区域"""
        device_frame = ttk.LabelFrame(parent, text="🔧 设备管理", padding="12")
        device_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 12))
        device_frame.columnconfigure(1, weight=1)
        device_frame.rowconfigure(1, weight=1)  # 设备列表行权重
        
        # 端口选择区域
        port_frame = ttk.Frame(device_frame)
        port_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        port_frame.columnconfigure(1, weight=1)
        
        ttk.Label(port_frame, text="选择端口:", style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        self.port_combo = ttk.Combobox(port_frame, width=20, state="readonly", font=('Segoe UI', 9))
        self.port_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 15))
        
        # 按钮区域
        btn_frame = ttk.Frame(port_frame)
        btn_frame.grid(row=0, column=2, sticky=tk.E)
        
        self.refresh_ports_btn = ttk.Button(btn_frame, text="🔄 刷新端口", command=self.refresh_ports, style='Action.TButton')
        self.refresh_ports_btn.grid(row=0, column=0, padx=(0, 8))
        
        self.add_device_btn = ttk.Button(btn_frame, text="➕ 添加设备", command=self.add_device, style='Success.TButton')
        self.add_device_btn.grid(row=0, column=1)
        
        # 添加工具提示
        self.create_tooltip(self.refresh_ports_btn, "刷新可用的串口列表")
        self.create_tooltip(self.add_device_btn, "将选中的端口添加为扫码设备")
        self.create_tooltip(self.port_combo, "选择要添加的串口设备")
        
        # 设备列表
        self.create_device_list(device_frame)
    
    def create_device_list(self, parent):
        """创建设备列表"""
        list_frame = ttk.LabelFrame(parent, text="📱 设备列表", padding="12")
        list_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(12, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # 设备列表容器
        tree_container = ttk.Frame(list_frame)
        tree_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 12))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        
        # 设备列表
        columns = ('device_id', 'port', 'status', 'scan_count', 'last_scan')
        self.device_tree = ttk.Treeview(tree_container, columns=columns, show='headings', height=7)
        
        # 设置列标题和宽度
        self.device_tree.heading('device_id', text='🆔 设备ID')
        self.device_tree.heading('port', text='🔌 端口')
        self.device_tree.heading('status', text='📊 状态')
        self.device_tree.heading('scan_count', text='📈 扫描次数')
        self.device_tree.heading('last_scan', text='⏰ 最后扫描')
        
        self.device_tree.column('device_id', width=120, anchor='center')
        self.device_tree.column('port', width=120, anchor='center')
        self.device_tree.column('status', width=120, anchor='center')
        self.device_tree.column('scan_count', width=120, anchor='center')
        self.device_tree.column('last_scan', width=180, anchor='center')
        
        self.device_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 滚动条
        tree_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.device_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.device_tree.configure(yscrollcommand=tree_scroll.set)
        
        # 设备操作按钮区域
        device_btn_frame = ttk.Frame(list_frame)
        device_btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # 左侧按钮组
        left_btn_frame = ttk.Frame(device_btn_frame)
        left_btn_frame.grid(row=0, column=0, sticky=tk.W)
        
        self.connect_selected_btn = ttk.Button(left_btn_frame, text="🔗 连接选中", command=self.connect_selected_device, style='Success.TButton')
        self.connect_selected_btn.grid(row=0, column=0, padx=(0, 8))
        self.create_tooltip(self.connect_selected_btn, "连接当前选中的设备")
        
        self.disconnect_selected_btn = ttk.Button(left_btn_frame, text="🔌 断开选中", command=self.disconnect_selected_device, style='Warning.TButton')
        self.disconnect_selected_btn.grid(row=0, column=1, padx=(0, 8))
        self.create_tooltip(self.disconnect_selected_btn, "断开当前选中的设备连接")
        
        self.remove_selected_btn = ttk.Button(left_btn_frame, text="🗑️ 移除选中", command=self.remove_selected_device, style='Warning.TButton')
        self.remove_selected_btn.grid(row=0, column=2)
        self.create_tooltip(self.remove_selected_btn, "从设备列表中移除选中的设备")
    
    def create_global_controls(self, parent):
        """创建全局控制按钮区域"""
        control_frame = ttk.LabelFrame(parent, text="🎮 全局控制", padding="12")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 0))
        control_frame.columnconfigure(0, weight=1)
        
        # 主要操作按钮区域
        main_btn_frame = ttk.Frame(control_frame)
        main_btn_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 左侧设备控制按钮
        device_ctrl_frame = ttk.Frame(main_btn_frame)
        device_ctrl_frame.grid(row=0, column=0, sticky=tk.W)
        
        self.connect_all_btn = ttk.Button(device_ctrl_frame, text="🔗 连接所有设备", command=self.connect_all_devices, style='Success.TButton')
        self.connect_all_btn.grid(row=0, column=0, padx=(0, 8))
        self.create_tooltip(self.connect_all_btn, "一键连接所有已添加的设备")
        
        self.disconnect_all_btn = ttk.Button(device_ctrl_frame, text="🔌 断开所有设备", command=self.disconnect_all_devices, style='Warning.TButton')
        self.disconnect_all_btn.grid(row=0, column=1, padx=(0, 8))
        self.create_tooltip(self.disconnect_all_btn, "一键断开所有已连接的设备")
        
        # 数据操作按钮
        data_ctrl_frame = ttk.Frame(main_btn_frame)
        data_ctrl_frame.grid(row=0, column=1, sticky=tk.W, padx=(20, 0))
        
        self.clear_data_btn = ttk.Button(data_ctrl_frame, text="🗑️ 清空数据", command=self.clear_data, style='Warning.TButton')
        self.clear_data_btn.grid(row=0, column=0, padx=(0, 8))
        self.create_tooltip(self.clear_data_btn, "清空所有扫描数据显示")
        
        if DATABASE_AVAILABLE:
            self.sync_data_btn = ttk.Button(data_ctrl_frame, text="☁️ 同步数据", command=self.sync_data, style='Action.TButton')
            self.sync_data_btn.grid(row=0, column=1)
            self.create_tooltip(self.sync_data_btn, "将扫描数据同步到数据库")
        
        # 设置区域
        settings_frame = ttk.Frame(control_frame)
        settings_frame.grid(row=1, column=0, sticky=tk.W)
        
        # 声音设置
        sound_frame = ttk.Frame(settings_frame)
        sound_frame.grid(row=0, column=0, sticky=tk.W)
        
        ttk.Label(sound_frame, text="🔊", font=('Segoe UI', 12)).grid(row=0, column=0, padx=(0, 5))
        self.sound_checkbox = ttk.Checkbutton(sound_frame, text="启用声音提示", variable=self.sound_enabled)
        self.sound_checkbox.grid(row=0, column=1)
        self.create_tooltip(self.sound_checkbox, "开启或关闭扫描成功、重复、错误时的声音提示")
        
        # 自动连接设置
        auto_connect_frame = ttk.Frame(settings_frame)
        auto_connect_frame.grid(row=0, column=1, sticky=tk.W, padx=(20, 0))
        
        ttk.Label(auto_connect_frame, text="🔗", font=('Segoe UI', 12)).grid(row=0, column=0, padx=(0, 5))
        self.auto_connect_checkbox = ttk.Checkbutton(auto_connect_frame, text="启动时自动连接设备", variable=self.auto_connect_enabled, command=self.on_auto_connect_changed)
        self.auto_connect_checkbox.grid(row=0, column=1)
        self.create_tooltip(self.auto_connect_checkbox, "程序启动时自动连接所有已保存的设备")
        
        # 开机启动设置
        startup_frame = ttk.Frame(settings_frame)
        startup_frame.grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        
        ttk.Label(startup_frame, text="🚀", font=('Segoe UI', 12)).grid(row=0, column=0, padx=(0, 5))
        self.startup_checkbox = ttk.Checkbutton(startup_frame, text="开机自动启动", variable=self.startup_enabled, command=self.on_startup_changed)
        self.startup_checkbox.grid(row=0, column=1)
        self.create_tooltip(self.startup_checkbox, "系统启动时自动运行此程序")
    
    def create_data_display(self, parent):
        """创建数据显示区域"""
        data_frame = ttk.LabelFrame(parent, text="📊 扫描数据预览", padding="15")
        data_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 0), pady=(0, 0))
        data_frame.columnconfigure(0, weight=1)
        data_frame.rowconfigure(1, weight=1)
        
        # 数据统计信息
        stats_frame = ttk.Frame(data_frame)
        stats_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 12))
        stats_frame.columnconfigure(2, weight=1)
        
        # 统计标签
        self.scan_stats_var = tk.StringVar(value="📈 今日扫描: 0 | 📋 总计: 0 | 🔄 重复: 0")
        stats_label = ttk.Label(stats_frame, textvariable=self.scan_stats_var, style='Status.TLabel')
        stats_label.grid(row=0, column=0, sticky=tk.W)
        
        # 数据显示文本框
        text_container = ttk.Frame(data_frame)
        text_container.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_container.columnconfigure(0, weight=1)
        text_container.rowconfigure(0, weight=1)
        
        self.data_text = scrolledtext.ScrolledText(
            text_container, 
            height=16, 
            font=("Consolas", 9),
            wrap=tk.WORD,
            relief='solid',
            borderwidth=1
        )
        self.data_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=2, pady=2)
        
        # 配置文本框颜色
        self.data_text.configure(
            bg='#f8f9fa',
            fg='#2c3e50',
            selectbackground='#3498db',
            selectforeground='white',
            insertbackground='#2c3e50'
        )
    
    def create_status_bar(self, parent):
        """创建状态栏"""
        status_frame = ttk.Frame(parent, relief='sunken', borderwidth=1)
        status_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(15, 0))
        status_frame.columnconfigure(4, weight=1)
        
        # 状态栏内容容器
        status_content = ttk.Frame(status_frame)
        status_content.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=5)
        status_content.columnconfigure(4, weight=1)
        
        # 系统状态
        self.status_var = tk.StringVar(value="✅ 系统就绪")
        status_label = ttk.Label(status_content, textvariable=self.status_var, style='Status.TLabel')
        status_label.grid(row=0, column=0, sticky=tk.W)
        
        # 分隔符
        ttk.Separator(status_content, orient='vertical').grid(row=0, column=1, sticky=(tk.N, tk.S), padx=15)
        
        # 设备统计
        self.device_count_var = tk.StringVar(value="📱 设备: 0")
        device_label = ttk.Label(status_content, textvariable=self.device_count_var, style='Status.TLabel')
        device_label.grid(row=0, column=2, sticky=tk.W)
        
        # 分隔符
        ttk.Separator(status_content, orient='vertical').grid(row=0, column=3, sticky=(tk.N, tk.S), padx=15)
        
        # 扫描统计
        self.total_count_var = tk.StringVar(value="📊 总扫描: 0")
        scan_label = ttk.Label(status_content, textvariable=self.total_count_var, style='Status.TLabel')
        scan_label.grid(row=0, column=4, sticky=tk.W)
        
        if DATABASE_AVAILABLE:
            # 分隔符
            ttk.Separator(status_content, orient='vertical').grid(row=0, column=5, sticky=(tk.N, tk.S), padx=15)
            
            # 数据库状态
            self.db_status_var = tk.StringVar(value="🔄 数据库: 检查中...")
            db_label = ttk.Label(status_content, textvariable=self.db_status_var, style='Status.TLabel')
            db_label.grid(row=0, column=6, sticky=tk.W)
        
        # 时间显示
        ttk.Separator(status_content, orient='vertical').grid(row=0, column=7, sticky=(tk.N, tk.S), padx=15)
        
        self.time_var = tk.StringVar(value="🕐 " + datetime.now().strftime("%H:%M:%S"))
        time_label = ttk.Label(status_content, textvariable=self.time_var, style='Status.TLabel')
        time_label.grid(row=0, column=8, sticky=tk.E)
    
    def check_database_status(self):
        """检查数据库状态"""
        try:
            import os
            url = os.getenv('SUPABASE_URL')
            key = os.getenv('SUPABASE_KEY')
            
            if url and key and url != "https://your-project-id.supabase.co":
                # 测试实际的数据库连接
                if DATABASE_AVAILABLE and hasattr(db, 'test_database_connection'):
                    try:
                        if db.test_database_connection():
                            self.add_log("✅ 数据库连接测试成功，扫描数据将自动上传到云端")
                            if hasattr(self, 'db_status_var'):
                                self.db_status_var.set("数据库: ✅ 已连接")
                        else:
                            self.add_log("⚠️ 数据库连接测试失败，数据将保存到本地并稍后同步")
                            if hasattr(self, 'db_status_var'):
                                self.db_status_var.set("数据库: ⚠️ 离线模式")
                    except Exception as test_e:
                        self.add_log(f"⚠️ 数据库连接测试异常: {test_e}")
                        if hasattr(self, 'db_status_var'):
                            self.db_status_var.set("数据库: ⚠️ 离线模式")
                else:
                    self.add_log("✅ 数据库配置已加载，扫描数据将自动上传到云端")
                    if hasattr(self, 'db_status_var'):
                        self.db_status_var.set("数据库: ✅ 已连接")
            else:
                self.add_log("⚠️ 数据库配置不完整，数据将只保存在本地")
                if hasattr(self, 'db_status_var'):
                    self.db_status_var.set("数据库: ⚠️ 离线模式")
        except Exception as e:
            self.add_log(f"⚠️ 数据库状态检查失败: {e}")
            if hasattr(self, 'db_status_var'):
                self.db_status_var.set("数据库: ❌ 错误")
    
    def refresh_ports(self):
        """刷新可用端口"""
        ports = serial.tools.list_ports.comports()
        port_list = []
        
        for port in ports:
            port_info = f"{port.device} - {port.description}"
            port_list.append(port_info)
        
        self.port_combo['values'] = port_list
        if port_list and not self.port_combo.get():
            self.port_combo.current(0)
        
        self.add_log(f"发现 {len(port_list)} 个可用端口")
    
    def add_device(self):
        """添加新设备"""
        selection = self.port_combo.get()
        if not selection:
            messagebox.showerror("错误", "请选择一个COM端口")
            return
        
        port = selection.split(" - ")[0]
        
        # 检查端口是否已被使用
        for device in self.devices.values():
            if device.port == port:
                messagebox.showerror("错误", f"端口 {port} 已被设备 {device.device_id} 使用")
                return
        
        # 创建新设备
        device_id = self.next_device_id
        self.next_device_id += 1
        
        device = ScannerDevice(device_id, port)
        self.devices[device_id] = device
        
        # 更新设备列表
        self.update_device_list()
        self.update_status()
        
        # 立即保存设备配置
        self.save_devices()
        
        self.add_log(f"添加设备: {device.device_name}")
    
    def remove_selected_device(self):
        """移除选中的设备"""
        selected = self.device_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请选择要移除的设备")
            return
        
        item = selected[0]
        device_id = int(self.device_tree.item(item)['values'][0])
        device = self.devices[device_id]
        
        # 先断开连接
        if device.is_connected:
            self.disconnect_device(device)
        
        # 移除设备
        del self.devices[device_id]
        
        # 更新界面
        self.update_device_list()
        self.update_status()
        
        # 立即保存设备配置
        self.save_devices()
        
        self.add_log(f"移除设备: {device.device_name}")
    
    def connect_selected_device(self):
        """连接选中的设备"""
        selected = self.device_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请选择要连接的设备")
            return
        
        item = selected[0]
        device_id = int(self.device_tree.item(item)['values'][0])
        device = self.devices[device_id]
        
        self.connect_device(device)
    
    def disconnect_selected_device(self):
        """断开选中的设备"""
        selected = self.device_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请选择要断开的设备")
            return
        
        item = selected[0]
        device_id = int(self.device_tree.item(item)['values'][0])
        device = self.devices[device_id]
        
        self.disconnect_device(device)
    
    def connect_all_devices(self):
        """连接所有设备"""
        for device in self.devices.values():
            if not device.is_connected:
                self.connect_device(device)
    
    def stop_all_scanning(self):
        """停止所有设备扫描"""
        for device in self.devices.values():
            if device.is_scanning:
                self.stop_device_scanning(device)
    
    def disconnect_all_devices(self):
        """断开所有设备"""
        for device in self.devices.values():
            if device.is_connected:
                self.disconnect_device(device)
    
    def connect_device(self, device):
        """连接单个设备"""
        try:
            # 确保设备完全断开
            self.force_disconnect_device(device)
            
            # 等待一小段时间确保资源释放
            time.sleep(0.1)
            
            params = device.get_serial_params()
            device.serial_connection = serial.Serial(port=device.port, **params)
            device.is_connected = True
            device.reconnect_attempts = 0  # 重置重连计数
            

            
            self.add_log(f"✅ {device.device_name} 连接成功")
            self.start_device_scanning(device)
            self.update_device_list()
            
        except Exception as e:
            self.add_log(f"❌ {device.device_name} 连接失败: {e}")
            
            # 检查是否是连接相关的错误
            connection_errors = ['device attached to the system is not functioning', 
                               'permission', 'access', 'device not found', 
                               'could not open port', 'serial exception']
            
            error_str = str(e).lower()
            is_connection_error = any(err.lower() in error_str for err in connection_errors)
            
            if is_connection_error:
                self.add_log(f"🔌 {device.device_name} 检测到连接问题，尝试重试后启动自动重连...")
            
            # 尝试强制清理资源后重试一次
            try:
                self.force_disconnect_device(device)
                time.sleep(0.5)
                params = device.get_serial_params()
                device.serial_connection = serial.Serial(port=device.port, **params)
                device.is_connected = True
                device.reconnect_attempts = 0  # 重置重连计数
                

                
                self.add_log(f"✅ {device.device_name} 重试连接成功")
                self.start_device_scanning(device)
                self.update_device_list()
                
            except Exception as retry_e:
                self.add_log(f"❌ {device.device_name} 重试连接也失败: {retry_e}")
                
                # 检查是否是连接相关的错误，如果是则启动自动重连
                connection_errors = ['device attached to the system is not functioning', 
                                   'permission', 'access', 'device not found', 
                                   'could not open port', 'serial exception']
                
                error_str = str(retry_e).lower()
                is_connection_error = any(err.lower() in error_str for err in connection_errors)
                
                if is_connection_error:
                    self.add_log(f"🔌 {device.device_name} 检测到连接问题，启动自动重连...")
                    # 启动自动重连
                    threading.Thread(target=self.auto_reconnect_device, args=(device,), daemon=True).start()
                else:
                    # 非连接错误，显示错误对话框
                    messagebox.showerror("连接失败", f"{device.device_name} 连接失败:\n原始错误: {e}\n重试错误: {retry_e}\n\n建议:\n1. 检查设备是否正常工作\n2. 尝试重新插拔设备\n3. 检查其他程序是否占用该端口")
    
    def disconnect_device(self, device):
        """断开单个设备"""
        try:
            # 停止扫描
            if device.is_scanning:
                self.stop_device_scanning(device)
            

            
            # 强制断开连接
            self.force_disconnect_device(device)
            
            self.add_log(f"🔌 {device.device_name} 已断开")
            self.update_device_list()
            
        except Exception as e:
            self.add_log(f"❌ 断开 {device.device_name} 失败: {e}")
            # 即使出错也要尝试强制清理
            self.force_disconnect_device(device)
    
    def force_disconnect_device(self, device):
        """强制断开设备连接，确保资源完全释放"""
        try:
            # 停止扫描线程
            device.is_scanning = False
            
            # 等待扫描线程结束
            if hasattr(device, 'scan_thread') and device.scan_thread and device.scan_thread.is_alive():
                device.scan_thread.join(timeout=2.0)  # 增加等待时间
                
                # 如果线程仍然活跃，强制结束
                if device.scan_thread.is_alive():
                    self.add_log(f"⚠️ {device.device_name} 扫描线程未能正常结束")
            
            # 强制关闭串口连接
            if device.serial_connection:
                try:
                    if device.serial_connection.is_open:
                        # 取消所有待处理的读写操作
                        try:
                            device.serial_connection.cancel_read()
                        except AttributeError:
                            pass  # 某些版本的pyserial可能没有这个方法
                        try:
                            device.serial_connection.cancel_write()
                        except AttributeError:
                            pass  # 某些版本的pyserial可能没有这个方法
                        # 刷新缓冲区
                        try:
                            device.serial_connection.flush()
                            device.serial_connection.flushInput()
                            device.serial_connection.flushOutput()
                        except AttributeError:
                            # 新版本pyserial使用不同的方法名
                            try:
                                device.serial_connection.flush()
                                device.serial_connection.reset_input_buffer()
                                device.serial_connection.reset_output_buffer()
                            except:
                                pass
                        # 关闭连接
                        device.serial_connection.close()
                        
                    # 额外等待确保系统释放资源
                    time.sleep(0.2)
                    
                except Exception as close_error:
                    self.add_log(f"⚠️ {device.device_name} 关闭串口时出错: {close_error}")
                
                # 清空连接对象
                device.serial_connection = None
            
            # 重置设备状态
            device.is_connected = False
            device.last_scan_time = None
            device.reconnect_attempts = 0
            device.scan_thread = None
            
            self.add_log(f"✅ {device.device_name} 连接已强制断开")
            
        except Exception as e:
            # 即使强制断开失败也要重置状态
            device.is_connected = False
            device.serial_connection = None
            device.is_scanning = False
            device.reconnect_attempts = 0
            device.scan_thread = None
            self.add_log(f"⚠️ {device.device_name} 强制断开时出错: {e}")
    
    def start_device_scanning(self, device):
        """开始单个设备扫描"""
        if not device.is_connected:
            messagebox.showerror("错误", f"{device.device_name} 未连接")
            return
        
        if device.is_scanning:
            return
        
        device.is_scanning = True
        device.scan_thread = threading.Thread(target=self.scan_worker, args=(device,), daemon=True)
        device.scan_thread.start()
        
        self.add_log(f"🔍 {device.device_name} 开始扫描")
        self.update_device_list()
    
    def stop_device_scanning(self, device):
        """停止单个设备扫描"""
        device.is_scanning = False
        self.add_log(f"⏹️ {device.device_name} 停止扫描")
        self.update_device_list()
    
    def scan_worker(self, device):
        """扫描工作线程"""
        buffer = ""
        
        while device.is_scanning and device.serial_connection and device.serial_connection.is_open:
            try:
                if device.serial_connection.in_waiting > 0:
                    data = device.serial_connection.read(device.serial_connection.in_waiting)
                    
                    try:
                        decoded_data = data.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            decoded_data = data.decode('gbk')
                        except UnicodeDecodeError:
                            decoded_data = data.decode('ascii', errors='ignore')
                    
                    buffer += decoded_data
                    
                    # 处理完整的扫描数据
                    while '\n' in buffer or '\r' in buffer:
                        if '\r\n' in buffer:
                            line, buffer = buffer.split('\r\n', 1)
                        elif '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                        elif '\r' in buffer:
                            line, buffer = buffer.split('\r', 1)
                        
                        line = line.strip()
                        if line:
                            self.process_scanned_data(device, line)
                
                time.sleep(0.01)
                
            except Exception as e:
                self.root.after(0, lambda: self.handle_scan_error(device, str(e)))
                break
    
    def process_scanned_data(self, device, data):
        """处理扫描到的数据"""
        # 检查短时间内重复扫描
        if device.is_duplicate_scan(data):
            self.root.after(0, lambda: self.add_log(f"🔄 {device.device_name} 重复扫描已过滤: {data}"))
            # 播放重复扫描警告音
            self.play_duplicate_sound()
            return
        
        # 检查当天是否已经扫描过相同条码
        if data in self.today_scanned_data:
            self.root.after(0, lambda: self.add_log(f"📋 {device.device_name} 当天已扫描过，跳过上传: {data}"))
            # 播放重复扫描警告音
            self.play_duplicate_sound()
            # 仍然更新计数和显示，但不上传到数据库
            device.scan_count += 1
            device.last_scan_time = datetime.now().strftime('%H:%M:%S')
            self.total_scan_count += 1
            self.root.after(0, lambda: self.update_scan_display(device, data))
            return
        
        # 添加到当天扫描数据缓存并保存
        self.today_scanned_data.add(data)
        self.save_today_scanned_data()
        
        device.scan_count += 1
        device.last_scan_time = datetime.now().strftime('%H:%M:%S')
        self.total_scan_count += 1
        
        # 播放成功扫描提示音
        self.play_success_sound()
        
        # 上传到数据库 (异步)
        if DATABASE_AVAILABLE:
            self.upload_to_database(device, data)
        
        # 更新UI
        self.root.after(0, lambda: self.update_scan_display(device, data))
    
    def update_scan_display(self, device, data):
        """更新扫描显示"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {device.device_name} 第{device.scan_count}次: {data}"
        
        self.add_log(log_entry)
        self.update_device_list()
        self.update_status()
    
    def upload_to_database(self, device, data):
        """异步上传数据到数据库"""
        def upload_worker():
            try:
                success = db.upload_barcode_scan(
                    barcode_data=data,
                    device_port=device.port
                )
                if not success:
                    self.root.after(0, lambda: self.add_log(f"⚠️ {device.device_name} 数据上传失败: {data}"))
            except Exception as e:
                self.root.after(0, lambda: self.add_log(f"⚠️ {device.device_name} 数据库上传错误: {e}"))

        threading.Thread(target=upload_worker, daemon=True).start()
    

    
    def handle_scan_error(self, device, error_msg):
        """处理扫描错误"""
        self.add_log(f"❌ {device.device_name} 扫描错误: {error_msg}")
        # 播放错误提示音
        self.play_error_sound()
        device.is_scanning = False
        
        # 检查是否是连接相关的错误
        connection_errors = ['device attached to the system is not functioning', 
                           'permission', 'access', 'device not found', 
                           'could not open port', 'serial exception']
        
        is_connection_error = any(err.lower() in error_msg.lower() for err in connection_errors)
        
        if is_connection_error:
            # 标记设备为断开状态
            device.is_connected = False
            self.add_log(f"🔌 {device.device_name} 检测到连接问题，尝试自动重连...")
            
            # 启动自动重连
            threading.Thread(target=self.auto_reconnect_device, args=(device,), daemon=True).start()
        
        self.update_device_list()
    
    def auto_reconnect_device(self, device):
        """自动重连设备"""
        current_time = time.time()
        
        # 防止频繁重连
        if device.last_error_time and (current_time - device.last_error_time) < 5:
            return
        
        device.last_error_time = current_time
        device.reconnect_attempts += 1
        
        if device.reconnect_attempts > device.max_reconnect_attempts:
            self.root.after(0, lambda: self.add_log(f"❌ {device.device_name} 重连次数超限，请手动重连"))
            return
        
        self.root.after(0, lambda: self.add_log(f"🔄 {device.device_name} 第{device.reconnect_attempts}次重连尝试..."))
        
        # 等待一段时间再重连
        time.sleep(2 * device.reconnect_attempts)  # 递增等待时间
        
        try:
            # 强制断开
            self.force_disconnect_device(device)
            time.sleep(1)
            
            # 尝试重连
            params = device.get_serial_params()
            device.serial_connection = serial.Serial(port=device.port, **params)
            device.is_connected = True
            device.reconnect_attempts = 0  # 重置重连计数
            

            
            self.root.after(0, lambda: self.add_log(f"✅ {device.device_name} 自动重连成功"))
            self.root.after(0, lambda: self.start_device_scanning(device))
            self.root.after(0, lambda: self.update_device_list())
            
        except Exception as e:
            # 修复变量作用域问题：将异常信息保存到局部变量
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.add_log(f"❌ {device.device_name} 自动重连失败: {msg}"))
            # 如果还有重连机会，继续尝试
            if device.reconnect_attempts < device.max_reconnect_attempts:
                threading.Thread(target=self.auto_reconnect_device, args=(device,), daemon=True).start()
    
    def update_device_list(self):
        """更新设备列表显示"""
        # 清空现有项目
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        
        # 添加设备信息
        for device in self.devices.values():
            status = "扫描中" if device.is_scanning else ("已连接" if device.is_connected else "未连接")
            last_scan = device.last_scan_time or "--"
            
            self.device_tree.insert('', 'end', values=(
                device.device_id,
                device.port,
                status,
                device.scan_count,
                last_scan
            ))
    
    def update_status(self):
        """更新状态信息"""
        # 更新时间
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_var.set(f"🕐 {current_time}")
        
        connected_count = sum(1 for d in self.devices.values() if d.is_connected)
        scanning_count = sum(1 for d in self.devices.values() if d.is_scanning)
        
        # 更新设备状态
        if connected_count == 0:
            self.device_count_var.set(f"📱 设备: {len(self.devices)} (未连接)")
        elif scanning_count > 0:
            self.device_count_var.set(f"📱 设备: {connected_count}/{len(self.devices)} (🔍 {scanning_count}扫描中)")
        else:
            self.device_count_var.set(f"📱 设备: {connected_count}/{len(self.devices)} (已连接)")
        
        # 更新总扫描次数
        self.total_count_var.set(f"📊 总扫描: {self.total_scan_count}")
        
        # 更新统计信息
        today_count = len(self.today_scanned_data)
        self.scan_stats_var.set(f"📈 今日扫描: {today_count} | 📋 总计: {self.total_scan_count} | 🔄 重复: 0")
        
        # 更新系统状态
        if scanning_count > 0:
            self.status_var.set(f"🔍 扫描中 ({scanning_count}个设备)")
        elif connected_count > 0:
            self.status_var.set(f"✅ 就绪 ({connected_count}个设备已连接)")
        elif len(self.devices) > 0:
            self.status_var.set("⚠️ 设备未连接")
        else:
            self.status_var.set("📱 请添加设备")
    
    def add_log(self, message):
        """添加日志"""
        self.data_text.insert(tk.END, message + "\n")
        self.data_text.see(tk.END)
    
    def clear_data(self):
        """清空数据"""
        # 询问是否清空当天缓存
        result = messagebox.askyesnocancel(
            "清空数据", 
            "是否同时清空当天扫描数据缓存？\n\n选择'是'：清空所有数据和缓存\n选择'否'：只清空显示数据，保留缓存\n选择'取消'：不执行任何操作"
        )
        
        if result is None:  # 取消
            return
        
        self.data_text.delete(1.0, tk.END)
        self.total_scan_count = 0
        
        # 重置各设备的扫描计数
        for device in self.devices.values():
            device.scan_count = 0
            device.last_scan_time = None
        
        if result:  # 选择'是'，清空缓存
            self.today_scanned_data.clear()
            try:
                if os.path.exists(self.today_cache_file):
                    os.remove(self.today_cache_file)
                self.add_log("📝 扫描数据和当天缓存已清空")
            except Exception as e:
                self.add_log(f"清空缓存文件失败: {e}")
        else:  # 选择'否'，保留缓存
            self.add_log("📝 扫描数据已清空（保留当天缓存）")
        
        self.update_device_list()
        self.update_status()
    
    def sync_data(self):
        """同步数据到数据库"""
        if not DATABASE_AVAILABLE:
            return
        
        try:
            synced_count = db.sync_local_data()
            if synced_count > 0:
                self.add_log(f"📤 已同步 {synced_count} 条本地数据到数据库")
            else:
                self.add_log("📤 没有需要同步的本地数据")
        except Exception as e:
            self.add_log(f"⚠️ 数据同步失败: {e}")
    
    def load_saved_devices(self):
        """从配置文件加载保存的设备"""
        config_path = 'scanner_config.json'
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                saved_ports = config.get('ports', [])
                
                # 加载声音设置
                sound_enabled = config.get('sound_enabled', True)
                self.sound_enabled.set(sound_enabled)
                
                available_ports = [p.device for p in serial.tools.list_ports.comports()]
                
                for port in saved_ports:
                    if port in available_ports:
                        device_id = self.next_device_id
                        self.next_device_id += 1
                        device = ScannerDevice(device_id, port)
                        self.devices[device_id] = device
                        self.add_log(f"🔄 加载保存设备: {device.device_name}")
                    else:
                        self.add_log(f"⚠️ 保存端口 {port} 不可用，跳过")
                
                self.update_device_list()
                self.update_status()
            except Exception as e:
                self.add_log(f"⚠️ 加载配置失败: {e}")

    def save_devices(self):
        """保存当前设备配置"""
        config_path = 'scanner_config.json'
        ports = [device.port for device in self.devices.values()]
        config = {
            'ports': ports,
            'sound_enabled': self.sound_enabled.get()
        }
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            self.add_log(f"设备配置已保存到 {config_path}")
        except Exception as e:
            self.add_log(f"保存设备配置失败: {e}")
    
    def load_today_scanned_data(self):
        """加载当天已扫描的数据"""
        try:
            if os.path.exists(self.today_cache_file):
                with open(self.today_cache_file, 'r', encoding='utf-8') as f:
                    data_list = json.load(f)
                    self.today_scanned_data = set(data_list)
                    self.add_log(f"已加载当天扫描数据缓存: {len(self.today_scanned_data)} 条记录")
            else:
                self.today_scanned_data = set()
                self.add_log("创建新的当天扫描数据缓存")
        except Exception as e:
            self.add_log(f"加载当天扫描数据失败: {e}")
            self.today_scanned_data = set()
    
    def save_today_scanned_data(self):
        """保存当天扫描数据到本地文件"""
        try:
            with open(self.today_cache_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.today_scanned_data), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.add_log(f"保存当天扫描数据失败: {e}")
    
    def play_success_sound(self):
        """播放成功扫描提示音"""
        if not self.sound_enabled.get():
            return
        try:
            # 播放系统默认的成功提示音
            winsound.MessageBeep(winsound.MB_OK)
        except Exception as e:
            pass  # 忽略声音播放错误
    
    def play_duplicate_sound(self):
        """播放重复扫描警告音"""
        if not self.sound_enabled.get():
            return
        try:
            # 播放系统警告音
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception as e:
            pass  # 忽略声音播放错误
    
    def play_error_sound(self):
        """播放错误提示音"""
        if not self.sound_enabled.get():
            return
        try:
            # 播放系统错误音
            winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception as e:
            pass  # 忽略声音播放错误
    
    def cleanup_expired_cache_files(self):
        """清理过期的缓存文件"""
        try:
            current_date = datetime.now().strftime('%Y%m%d')
            cache_pattern = 'today_scans_*.json'
            
            import glob
            cache_files = glob.glob(cache_pattern)
            
            cleaned_count = 0
            for cache_file in cache_files:
                # 提取文件中的日期
                try:
                    file_date = cache_file.split('_')[-1].split('.')[0]
                    if file_date != current_date and len(file_date) == 8:
                        os.remove(cache_file)
                        cleaned_count += 1
                        self.add_log(f"已清理过期缓存文件: {cache_file}")
                except Exception as e:
                    self.add_log(f"清理缓存文件 {cache_file} 失败: {e}")
            
            if cleaned_count > 0:
                self.add_log(f"共清理了 {cleaned_count} 个过期缓存文件")
            else:
                self.add_log("没有发现过期的缓存文件")
                
        except Exception as e:
            self.add_log(f"清理过期缓存文件失败: {e}")
    
    def on_closing(self):
        """程序关闭处理"""
        try:
            self.add_log("🔄 正在关闭程序，请稍候...")
            
            # 保存当天扫描数据
            self.save_today_scanned_data()
            
            # 停止所有扫描
            self.stop_all_scanning()
            
            # 强制断开所有设备并等待资源释放
            self.force_disconnect_all_devices()
            
            # 保存设备配置
            self.save_devices()

            # 同步数据 (同步执行，确保完成)
            if DATABASE_AVAILABLE:
                try:
                    synced_count = db.sync_local_data()
                    if synced_count > 0:
                        self.add_log(f"📤 已同步 {synced_count} 条本地数据到数据库")
                    else:
                        self.add_log("📤 没有需要同步的本地数据")
                except Exception as e:
                    self.add_log(f"⚠️ 数据同步失败: {e}")
            
            self.add_log("✅ 程序关闭完成")
            
            # 等待一段时间确保所有资源释放
            time.sleep(1.0)
            
        except Exception as e:
            print(f"关闭程序时发生错误: {e}")
        finally:
            # 销毁窗口
            self.root.destroy()

    def force_disconnect_all_devices(self):
        """强制断开所有设备并等待资源释放"""
        self.add_log("🔌 正在断开所有设备连接...")
        
        # 停止所有扫描线程
        for device in self.devices.values():
            device.is_scanning = False
        
        # 等待扫描线程结束
        time.sleep(0.5)
        
        # 强制断开所有设备
        for device in self.devices.values():
            if device.is_connected or device.serial_connection:
                self.force_disconnect_device(device)
        
        # 额外等待时间确保Windows系统释放串口资源
        time.sleep(1.0)
        
        self.add_log("✅ 所有设备已断开连接")
    
    def on_auto_connect_changed(self):
        """自动连接设置变化时的回调"""
        self.save_settings()
        if self.auto_connect_enabled.get():
            self.add_log("✅ 已启用启动时自动连接设备")
        else:
            self.add_log("❌ 已禁用启动时自动连接设备")
    
    def on_startup_changed(self):
        """开机启动设置变化时的回调"""
        try:
            if self.startup_enabled.get():
                self.enable_startup()
                self.add_log("✅ 已启用开机自动启动")
            else:
                self.disable_startup()
                self.add_log("❌ 已禁用开机自动启动")
        except Exception as e:
            self.add_log(f"⚠️ 开机启动设置失败: {e}")
            # 如果设置失败，恢复复选框状态
            self.startup_enabled.set(not self.startup_enabled.get())
        self.save_settings()
    
    def enable_startup(self):
        """启用开机自动启动"""
        import winreg
        import sys
        
        # 获取当前程序的完整路径
        if getattr(sys, 'frozen', False):
            # 如果是打包后的exe文件
            app_path = sys.executable
        else:
            # 如果是Python脚本
            app_path = f'python "{os.path.abspath(__file__)}"'
        
        # 添加到注册表
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                            r"Software\Microsoft\Windows\CurrentVersion\Run", 
                            0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "MultiScannerApp", 0, winreg.REG_SZ, app_path)
        winreg.CloseKey(key)
    
    def disable_startup(self):
        """禁用开机自动启动"""
        import winreg
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                r"Software\Microsoft\Windows\CurrentVersion\Run", 
                                0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, "MultiScannerApp")
            winreg.CloseKey(key)
        except FileNotFoundError:
            # 如果注册表项不存在，忽略错误
            pass
    
    def check_startup_status(self):
        """检查开机启动状态"""
        import winreg
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                r"Software\Microsoft\Windows\CurrentVersion\Run", 
                                0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "MultiScannerApp")
            winreg.CloseKey(key)
            return True
        except (FileNotFoundError, OSError):
            return False
    
    def save_settings(self):
        """保存设置到文件"""
        settings = {
            'sound_enabled': self.sound_enabled.get(),
            'auto_connect_enabled': self.auto_connect_enabled.get(),
            'startup_enabled': self.startup_enabled.get()
        }
        
        try:
            with open('settings.json', 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ 保存设置失败: {e}")
    
    def load_settings(self):
        """从文件加载设置"""
        try:
            if os.path.exists('settings.json'):
                with open('settings.json', 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                self.sound_enabled.set(settings.get('sound_enabled', True))
                self.auto_connect_enabled.set(settings.get('auto_connect_enabled', False))
                
                # 检查实际的开机启动状态
                actual_startup_status = self.check_startup_status()
                saved_startup_status = settings.get('startup_enabled', False)
                
                # 如果保存的状态与实际状态不一致，以实际状态为准
                if actual_startup_status != saved_startup_status:
                    self.startup_enabled.set(actual_startup_status)
                    self.save_settings()  # 更新保存的设置
                else:
                    self.startup_enabled.set(saved_startup_status)
        except Exception as e:
            print(f"⚠️ 加载设置失败: {e}")
    
    def auto_connect_devices_on_startup(self):
        """启动时自动连接设备"""
        if self.auto_connect_enabled.get() and self.devices:
            self.add_log("🔗 正在自动连接所有设备...")
            # 延迟一秒后执行自动连接，确保界面完全加载
            self.root.after(1000, self.connect_all_devices)
    
    def create_tooltip(self, widget, text):
        """为控件创建工具提示"""
        tooltip = ToolTip(widget, text)
        self.tooltips.append(tooltip)
        return tooltip
    
    def cleanup_orphaned_serial_connections(self):
        """清理可能的孤立串口连接"""
        try:
            import psutil
            import serial.tools.list_ports
            
            # 获取所有可用串口
            available_ports = [port.device for port in serial.tools.list_ports.comports()]
            
            # 尝试短暂打开和关闭每个串口以清理可能的孤立连接
            for port in available_ports:
                try:
                    test_serial = serial.Serial(port, timeout=0.1)
                    test_serial.close()
                    time.sleep(0.1)
                except:
                    pass  # 忽略错误，继续处理下一个端口
                    
        except ImportError:
            # 如果没有psutil模块，跳过清理
            pass
        except Exception as e:
            if hasattr(self, 'add_log'):
                self.add_log(f"⚠️ 串口资源清理时出错: {e}")


class ToolTip:
    """工具提示类"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind('<Enter>', self.on_enter)
        self.widget.bind('<Leave>', self.on_leave)
        self.widget.bind('<Motion>', self.on_motion)
    
    def on_enter(self, event=None):
        """鼠标进入时显示提示"""
        self.show_tooltip()
    
    def on_leave(self, event=None):
        """鼠标离开时隐藏提示"""
        self.hide_tooltip()
    
    def on_motion(self, event=None):
        """鼠标移动时更新位置"""
        if self.tooltip_window:
            self.hide_tooltip()
            self.show_tooltip()
    
    def show_tooltip(self):
        """显示工具提示"""
        if self.tooltip_window or not self.text:
            return
        
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 25
        
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            background='#ffffe0',
            foreground='#000000',
            relief='solid',
            borderwidth=1,
            font=('Segoe UI', 9),
            padx=5,
            pady=3
        )
        label.pack()
    
    def hide_tooltip(self):
        """隐藏工具提示"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


def main():
    """主函数"""
    root = tk.Tk()
    app = MultiScannerApp(root)
    
    # 绑定关闭事件
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    try:
        # 运行程序
        root.mainloop()
    except Exception as e:
        print(f"主程序运行时发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 确保窗口被销毁
        try:
            if root.winfo_exists():
                root.destroy()
        except:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("程序被用户中断")
    except Exception as e:
        print(f"程序运行时发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 确保程序完全退出
        import sys
        sys.exit(0)