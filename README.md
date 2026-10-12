# Indoor Cycling / 室内骑行训练系统

[![Tests](https://github.com/XingGaoY/indoor-cycling/actions/workflows/tests.yml/badge.svg)](https://github.com/XingGaoY/indoor-cycling/actions/workflows/tests.yml)

一个本地优先、可自主部署的室内骑行与有氧交叉训练项目。目标运行环境是 **macOS / Mac mini**：由主机连接骑行台和心率传感器，手机端通过 Web/PWA 查看训练状态并控制训练。训练数据优先留在本地，并为导出与 COROS 集成保留发展空间。

> **当前版本：v0.1 simulator MVP。** 现有 Web 控制仅驱动模拟训练状态；没有真实蓝牙阻力控制。不能把当前版本当作已验证的骑行台控制器使用。

## 当前状态

| 能力 | 当前实现 |
| --- | --- |
| 命令行 BLE 扫描、GATT 只读检查 | 已实现，需 macOS 实机验证 |
| 心率特征值 / FTMS Indoor Bike Data 解析 | 已实现部分标准字段与单元测试 |
| FastAPI 服务、基础网页仪表盘 | 已实现，默认仅监听本机 |
| 模拟开始 / 暂停 / 结束 / 40–150 W 目标功率 | 已实现，仅模拟 |
| SQLite 会话与模拟时序记录 | 已实现，尚无数据迁移机制 |
| 真实心率与功率持续采样 | 未实现 |
| 实际 T300 FTMS/ERG 写入 | 未实现，不得在未验证前启用 |
| 手机上通过可信 HTTPS/PWA 控制 | 未完成（当前网页不构成完整可安装 PWA） |
| FIT 导出、COROS 自动上传 | 未实现；上传权限/集成方式待核实 |

模拟数据不代表真实训练记录，也不应被导出作为真实运动。

## 5 分钟本机启动

前提：Git、**Python 3.11+**、macOS（仅 BLE 诊断需 macOS；模拟服务和测试可以在其他桌面系统运行）。

~~~bash
git clone https://github.com/XingGaoY/indoor-cycling.git
cd indoor-cycling
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
python -m pytest -q
export CYCLING_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
indoor-cycling serve
~~~

浏览器在**运行服务的同一台电脑**上访问 http://127.0.0.1:8765 ，并输入刚生成的令牌。若尚未保存令牌，可在原终端另外输出环境变量（勿上传或截图公开令牌）。服务关闭后此临时环境变量不会自动持久化。

注意：默认地址为 127.0.0.1。**不要为了手机访问直接将服务绑定 0.0.0.0 或端口映射到公网**。当前认证与传输层尚未达到公开网络或共享局域网使用要求。

## 只读蓝牙检查

~~~bash
indoor-cycling scan --seconds 10
indoor-cycling inspect '<扫描结果中的 identifier>'
~~~

首次调用可能需要在 macOS 的隐私与安全性设置中给 Terminal / Python 授予蓝牙权限。inspect 只读取允许读取的 GATT 值，不会写入 ERG 控制点。设备不可用、被其他 App 占用或 Bluetooth 未授权都可能造成连接失败。

## 目录导览

- **src/indoor_cycling/**：Python CLI、BLE 诊断、协议解析、模拟 API/页面
- **tests/**：pytest
- **scripts/macos/**：仅本机监听的 macOS LaunchAgent 安装、运行和卸载脚本
- **doc/**：以序号固定入口的开发与部署文档
- **.github/workflows/**：CI

## 文档阅读顺序

| 文档 | 用途 |
| --- | --- |
| [01 - 从零安装](doc/01-quick-start.md) | 新电脑 clone、Python 环境、运行和验证 |
| [02 - 开发流程](doc/02-development.md) | 分支、测试、代码修改与交付标准 |
| [03 - macOS / Mac mini 部署](doc/03-macos-deployment.md) | 手动运行、LaunchAgent、更新、回滚 |
| [04 - BLE 设备诊断](doc/04-ble-diagnostics.md) | T300 与 COROS 检查、日志脱敏 |
| [05 - API 与数据](doc/05-api-and-data.md) | API、SQLite、状态和数据迁移 |
| [06 - 安全与运维](doc/06-security-and-operations.md) | 网络隔离、备份、故障排查 |
| [07 - 能力状态与验收](doc/07-status-and-acceptance.md) | 已实现/待验证边界 |
| [08 - 项目指令模板](doc/08-project-instructions.md) | ChatGPT Project instruction 的稳定版本 |

## 贡献和协作

开发以 GitHub 为唯一代码事实来源：从 main 建功能分支，经 PR、CI 和文档审查后合并。变更命令、配置、数据格式或部署方式时，同一 PR 必须更新相关文档。保持模拟器可测试；硬件测试必须明确区分和记录。请参阅 [02 - 开发流程](doc/02-development.md)。

**数据与隐私：** 令牌、蓝牙设备标识、未经脱敏的诊断日志、个人健康/训练数据、SQLite 数据库及 FIT 文件不得提交到公开仓库。当前仓库为 Public。

**许可证：** 尚未选择许可证。公开可查看源码并不自动授予任意使用、修改或再分发权利。
