#!/bin/bash
# =============================================
# Shuttle MCP SSH 安装脚本
# 用于 Claude Code 连接远端云服务器
# =============================================
set -e

SHUTTLE_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin/shuttle-mcp"
MCP_FILE="/Users/jacklee/myProject/daily_stock_analysis/.mcp.json"

echo "=== Step 1: 检查 Shuttle 安装 ==="
if [ -x "$SHUTTLE_BIN" ]; then
    echo "✅ Shuttle 已安装: $SHUTTLE_BIN"
    $SHUTTLE_BIN --help 2>&1 | head -3
else
    echo "❌ Shuttle 未找到，请先执行: pip3 install shuttle-mcp"
    exit 1
fi

echo ""
echo "=== Step 2: 创建 .mcp.json ==="
cat > "$MCP_FILE" << 'MCPEOF'
{
  "mcpServers": {
    "shuttle": {
      "command": "/Library/Frameworks/Python.framework/Versions/3.12/bin/shuttle-mcp"
    }
  }
}
MCPEOF
echo "✅ 已创建: $MCP_FILE"
cat "$MCP_FILE"

echo ""
echo "============================================"
echo "✅ Shuttle MCP 配置完成！"
echo ""
echo "下一步："
echo "  1. 重启 Claude Code 以加载新 MCP 服务器"
echo "  2. 在对话中输入添加服务器:"
echo "     shuttle add <服务器名> --host <IP> --user root"
echo "============================================"
