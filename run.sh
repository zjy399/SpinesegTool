#!/bin/bash
# 桌面环境启动脚本 - 确保 Qt 界面能正常显示

# 切换到项目根目录
cd "$(dirname "$0")"

# 设置显示环境变量（Ubuntu 桌面）
if [ -z "$DISPLAY" ]; then
    # 尝试常见的显示方式
    if [ -n "$WAYLAND_DISPLAY" ]; then
        export DISPLAY=:0
    elif [ -e /tmp/.X11-unix/X0 ]; then
        export DISPLAY=:0
    else
        # 尝试从正在运行的会话获取
        export DISPLAY=:0
    fi
fi

# 设置 X11 认证（如果需要）
if [ -z "$XAUTHORITY" ] && [ -f "$HOME/.Xauthority" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
fi

# 激活虚拟环境并运行
source .venv/bin/activate

echo "========================================="
echo "启动标注工具..."
echo "DISPLAY=$DISPLAY"
echo "========================================="

# 运行应用
python -m segtool "$@"
