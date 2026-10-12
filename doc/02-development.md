# 02 · 开发模式与协作规范

## 单一事实来源

GitHub 仓库是代码、文档、测试与开发历史的事实来源。不要把 ChatGPT 对话、某台 Mac mini 本地目录或 ZIP 包当成最新版本。Project instruction 只承载稳定产品目标与协作方式，具体方案维护在 README、doc/ 和代码中。

## 分支与 PR

- main 保持可复现、测试通过、可以安全启动模拟器。
- 一项独立修改使用一个短期分支：feat/、fix/、docs/ 或 chore/ 前缀。
- PR 描述至少包含目标、改动范围、测试证据、风险与未验证项、文档变更。
- 合并前运行 pytest；涉及 shell 脚本时执行 bash -n；涉及硬件时单独记录 macOS/固件版本与实测结果。
- 默认由 PR 合并进入 main；生产/常驻部署应使用经过检查的确定提交而非漂移的开发分支。

## 本地开发循环

~~~bash
git switch main
git pull --ff-only
git switch -c feat/your-change
source .venv/bin/activate
python -m pip install -e ".[test]"
python -m pytest -q
bash -n scripts/macos/*.sh
git status
~~~

代码在 src/indoor_cycling；CLI 入口位于 cli.py；只读 BLE 诊断在 ble.py；协议解析在 protocol.py；目前模拟器/API/HTML 在 server.py。测试位于 tests/。尚未抽出的模块不要在文档中写成已经存在。

## 必须维持的架构边界

1. **模拟器与真实硬件不能混淆。** 当前 serve 为 SIMULATOR；加入硬件支持时必须有显式模式选择、能力检查和安全退出，不得悄悄让现有命令开始发送阻力控制指令。
2. **浏览器不是硬件控制器。** Web 只提交命令、展示后端权威状态。断线或刷新不应在未来改变服务端对训练的真实判断。
3. **读取与写入分离。** 扫描和 GATT 探测不得写入控制点；硬件控制需要可测试的 FTMS 状态机、功率限制、指令应答和异常恢复。
4. **数据先本地、再同步。** 外部同步失败不能抹掉原始数据。模拟数据永远不能被标识为实测。
5. **通信与安全变更必须有测试。** 协议解析用已知字节 fixture，HTTP 用 TestClient，硬件验证作为独立人工验收步骤。

## 文档同步规则

以下变化必须更新对应文档：启动参数与环境变量（01/03）、开发流程（02）、蓝牙能力或实测结果（04/07）、API 及 SQLite 格式（05）、安全与备份（06）、产品稳定边界（08）。README 汇总并链接详细文档。

新增文档使用两位数字加短英文主题：例如 09-new-topic.md；不随意更换既有编号。引入重大设计决定时可加独立技术文档，但**不要把阶段性方案写进 Project instruction**。

## 发布与回滚

发布/部署前记下 commit SHA；主机工作副本必须清楚显示正在运行哪个版本。更新数据库结构前先备份。合并并不意味着已经在真实 T300、COROS 和 macOS 蓝牙上通过验证；CI 的 Linux 测试不能代替硬件测试。

## 仓库信息保护

这是公开仓库。任何配置 token、用户数据库、训练记录、FIT 文件、实际设备 UUID 和完整诊断日志先脱敏，必要时只用私有渠道传递。不要把聊天中粘贴的凭据直接写入 PR。
