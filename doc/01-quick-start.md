# 01 · 从零安装与首次运行

适用于新 Mac、Mac mini，或临时在另一台电脑继续开发。下列命令以 macOS 的 zsh/bash 为例；服务模拟部分可在 Linux 开发，BLE 诊断则需要本机可用的蓝牙适配器及系统权限。

## 1. 准备依赖

- macOS、Git、Python **3.11 或更新版本**；确保 python3 指向合适版本：运行 python3 --version。
- 推荐使用官方 Python 安装程序或 Homebrew 安装 Python；请不要修改系统自带 Python。
- 当前仓库没有 npm/Node 前端构建步骤：Web 页面嵌入 Python 服务。
- 不需要购买 ANT+ 适配器就能验证模拟模式。

~~~bash
git --version
python3 --version
git clone https://github.com/XingGaoY/indoor-cycling.git
cd indoor-cycling
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
~~~

若安装失败，检查 python --version 和 python -m pip --version 是否都来自 .venv；Apple Silicon 和 Intel Mac 使用相同操作步骤，但应选与机器架构匹配的 Python。

## 2. 运行测试并启动模拟器

~~~bash
python -m pytest -q
export CYCLING_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf '仅在本机查看 token: %s\n' "$CYCLING_TOKEN"
indoor-cycling serve
~~~

打开 http://127.0.0.1:8765；把 token 填入网页。开始/暂停/结束和调整功率仅改变**模拟状态**。未连接心率设备时所有指标为模拟；连接后心率来自 BLE，踏频和功率仍为模拟。Ctrl+C 停止服务。

在同一台机器另一终端中可以验证 API：

~~~bash
curl -i http://127.0.0.1:8765/api/status
# 未携带令牌时应为 HTTP 401
curl -H "X-Cycling-Token: $CYCLING_TOKEN" http://127.0.0.1:8765/api/status
~~~

第二个命令必须在拥有相同 CYCLING_TOKEN 环境变量的 shell 中运行；如果换了 shell，需重新安全设置相同 token。请勿把 token 写进仓库或公开的终端记录。

## 3. 设备诊断（可选）

~~~bash
indoor-cycling scan --seconds 10
indoor-cycling inspect '<identifier>'
~~~

T300 接通电源、COROS 手表开启 BLE 心率广播、并允许终端访问蓝牙。详情参考 [04 - BLE 设备诊断](04-ble-diagnostics.md)。

## 4. 环境与文件位置

| 项目 | 默认路径/来源 |
| --- | --- |
| 虚拟环境 | 仓库下 .venv/（不纳入 Git） |
| 会话数据库 | ~/.local/share/indoor-cycling/sessions.sqlite3 |
| 指定数据库路径 | 启动前设置 CYCLING_DB 环境变量 |
| 控制令牌 | 启动前设置 CYCLING_TOKEN 环境变量 |
| 服务地址 | 127.0.0.1:8765 |
| 启动命令 | indoor-cycling serve |

**重要：** 数据库路径与令牌在服务模块加载时从环境变量读取。更改变量后应停止并重新启动服务。并发运行多个进程操纵同一个模拟数据库不是受支持的部署方式。

## 5. 新地点开发的最小检查

1. git status 无意外修改、git pull 更新 main。
2. Python 和依赖能安装、pytest 通过。
3. 使用强 token 在本机启动。
4. 页面可以显示 SIMULATOR 并执行模拟指令。
5. 只有在确需硬件诊断时启用蓝牙，并确保诊断过程不写入控制点。

持续部署方法见 [03](03-macos-deployment.md)，开发规范见 [02](02-development.md)。

## BLE 心率与设备管理更新

打开 /devices 输入令牌，扫描开启心率推送的手表，然后保存并连接。主页可显示真实 BLE 心率，功率与踏频仍模拟。令牌在当前标签页 sessionStorage 保留。

## 手机多页面布局

底部导航提供训练（/）、设备（/devices）和记录（/history）三页，共享标签页访问凭证。触控控件至少 48px，兼容手机安全区。记录通过认证 GET /api/history 读取最近 50 条本机会话，并标注模拟训练和 BLE 心率来源。切换页面不停止后台训练或设备连接。当前服务仍监听本机；手机实机访问需要后续可信 HTTPS 与访问方案，当前未完成离线 PWA 安装能力。
