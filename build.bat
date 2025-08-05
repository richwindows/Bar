@echo off
chcp 65001 >nul
echo.
echo ========================================
echo    多设备扫码枪管理器 - 打包工具
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python未安装或未添加到PATH环境变量
    echo 请先安装Python 3.8或更高版本
    pause
    exit /b 1
)

echo ✅ Python环境检查通过
echo.

:: 运行打包脚本
echo 🚀 开始打包...
python build_exe.py

echo.
echo 打包完成！
pause