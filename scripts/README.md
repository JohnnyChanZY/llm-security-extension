# 开发调试启动脚本

本项目提供便捷的开发环境启动脚本。

## 快速启动

### Windows

双击运行 `dev-start.bat` 即可启动所有服务：

- **Backend FastAPI** - http://127.0.0.1:8000
- **Admin 管理面板** - http://localhost:3000
- **Extension 开发服务** - http://localhost:5173

### 停止服务

双击运行 `dev-stop.bat` 可停止所有服务。

或者手动关闭各个终端窗口。

## 首次运行

脚本会自动检测并安装缺失的依赖：

1. Backend 虚拟环境不存在时自动创建并安装依赖
2. Admin 的 `node_modules` 不存在时自动安装
3. Extension 的 `node_modules` 不存在时自动安装

## 注意事项

- 确保 Python 3.10+ 和 Node.js 18+ 已安装
- 确保 MySQL 数据库已启动并配置正确
- 确保 `.env` 文件已正确配置（参考 `.env.example`）

## 手动启动

如需单独启动某个服务，请参考 [CLAUDE.md](./CLAUDE.md) 中的命令说明。
