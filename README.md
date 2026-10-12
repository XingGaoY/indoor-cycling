# Indoor Cycling / 室内骑行训练系统

[![Tests](https://github.com/XingGaoY/indoor-cycling/actions/workflows/tests.yml/badge.svg)](https://github.com/XingGaoY/indoor-cycling/actions/workflows/tests.yml)

一个本地优先、可自主部署的室内骑行与有氧交叉训练项目。目标运行环境是 **macOS / Mac mini**：由主机连接骑行台和心率传感器，手机端通过 Web/PWA 查看训练状态并控制训练。训练数据优先留在本地，并为导出与 COROS 集成保留发展空间。

> **当前版本：v0.1 模拟骑行台 + 可选真实 BLE 心率。** 现有 Web 控制仅驱动模拟训练状态；没有真实蓝牙阻力控制。不能把当前版本当作已验证的骑行台控制器使用。

## 当前状态

| 能力 | 当前实现 |
| --- | --- |
| 命令行 BLE 扫描、GATT 只读检查 | 已实现，需 macOS 实机验证 |
| 心率特征值 / FTMS Indoor Bike Data 解析 | 已实现部分标准字段与单元测试 |
| FastAPI 服务、基础网页仪表盘 | 已实现，默认仅监听本机 |
| 模拟开始 / 暂停 / 结束 / 40–150 W 目标功率 | 已实现，仅模拟 |
| SQLite 会话与模拟时序记录 | 已实现，尚无数据迁移机制 |
| 真实心率与功率持续采样 | 心率 BLE 通知已实现；真实功率未实现 |
| 本地课程计划库与四页导航 | 已实现（计划不自动执行） |
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
| [09 - 页面与训练功能设计](doc/09-training-product-design.md) | 手机分页、课程编排、执行微调与分阶段交付设计 |
| [10 - 可视化课程编辑器](doc/10-visual-workout-editor-design.md) | 双视图时间轴、区间定义、预设及交互/数据规范 |

## 贡献和协作

开发以 GitHub 为唯一代码事实来源：从 main 建功能分支，经 PR、CI 和文档审查后合并。变更命令、配置、数据格式或部署方式时，同一 PR 必须更新相关文档。保持模拟器可测试；硬件测试必须明确区分和记录。请参阅 [02 - 开发流程](doc/02-development.md)。

**数据与隐私：** 令牌、蓝牙设备标识、未经脱敏的诊断日志、个人健康/训练数据、SQLite 数据库及 FIT 文件不得提交到公开仓库。当前仓库为 Public。

**许可证：** 尚未选择许可证。公开可查看源码并不自动授予任意使用、修改或再分发权利。

## 心率与设备管理

打开 `/devices`，输入控制令牌，开启 COROS 心率推送后扫描。扫描结果可连接、命名保存；已保存设备可手动重连或移除。设备存在本机 SQLite，重启不自动连接。主页标注真实/模拟心率，连接后超过 5 秒未更新显示空值，不回退到模拟心率。骑行台功率和踏频仍为模拟。

当前标签页的令牌使用 sessionStorage 在两个页面间保留，关页结束；不要在共享电脑留下已登录标签页。没有新增骑行台控制写入。APEX 4 曾完成命令行通知验证；网页接入须单独实测。

本机验收：APEX 4 已通过 Web API 扫描、保存、连接，设备页面与仪表盘真实心率显示通过；长期连接、系统休眠恢复仍待验证。

## 手机多页面布局

底部导航提供训练（/）、计划（/plans）、设备（/devices）和记录（/history）四页，共享标签页访问凭证。触控控件至少 48px，兼容手机安全区。记录通过认证 GET /api/history 读取最近 50 条本机会话，并标注模拟训练和 BLE 心率来源。切换页面不停止后台训练或设备连接。当前服务仍监听本机；手机实机访问需要后续可信 HTTPS 与访问方案，当前未完成离线 PWA 安装能力。

## 课程规划（首批实现）

访问 `/plans`，输入与训练主页相同的控制令牌，可以创建、编辑、复制、选择与删除结构化课程。包含恒定功率阶段、线性变化阶段与一层重复间歇组。课程保存在本机 SQLite 的 `workout_plans` 表，选中课程保存在 `workout_settings` 表，重启后仍存在；API 和结构见 [05](doc/05-api-and-data.md)。

**当前仅完成计划库与编辑器，没有训练执行引擎。** 选中计划不会改变主页按钮的含义，也不会控制真实设备；主页的“开始”仍运行自由模拟训练。课程规划允许 40–500 W，但现有模拟训练 API 仍限制 40–150 W。阶段与功率范围是计划数据校验，不是实际硬件能力声明。移动端正式 HTTPS/PWA 尚待开发。

COROS 自动上传不作为近期开发阻塞项；优先完整手机交互、课程执行与训练历史。FIT/上传仍待后续评估。

## 时间轴编辑器与预设课程

`/plans` 现在提供共享时间轴的 **功率 Z1–Z6 / 心率 Z1–Z6 双视图**，点击/拖入区间块、上下拖动修改目标、拖右端把手调整时长，并使用下方表单精确编辑恒定、斜坡、单层重复阶段。内置四个可复制预设：恢复 30 分钟、Z2 45 分钟、节奏 40 分钟、阈值间歇 43 分钟；模板不会自动添加进用户的个人库。配置 FTP/HRmax 默认为空，不猜测真实功率或心率。

此编辑器**仅保存计划，不负责执行**。未来开始训练必须根据当次个人基准和设备能力二次校验。详见 [10 - 可视化编辑器设计](doc/10-visual-workout-editor-design.md)。移动端触摸操作尚需 Safari/实机验证。
