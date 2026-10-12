# 06 · 安全、运维、备份与故障排查

## 当前安全边界

服务默认绑定 127.0.0.1；内置网页通过请求头传递 CYCLING_TOKEN。**当前没有可信 HTTPS、细粒度权限、连接速率限制、会话撤销或多用户访问控制**。因此只能作为单机模拟服务使用。

- 不直接使用 --host 0.0.0.0 开放控制接口；不要路由器端口转发至公网。
- 不在浏览器地址栏、GitHub、issue、PR、日志或截图中暴露 token。
- 在其他开发电脑访问时使用 SSH 本机转发，具体见 [03](03-macos-deployment.md)。
- 如果令牌可能泄漏，停止服务，更换 runtime.env 内的 CYCLING_TOKEN 并重启所有服务。
- 项目仓库为公开仓库。数据库、导出 FIT、设备 UUID、未经脱敏的心率/固件日志都不应提交。

## 进程与健康检查

~~~bash
launchctl print "gui/$(id -u)/dev.indoorcycling.simulator"
tail -n 100 "$HOME/Library/Logs/IndoorCycling/stderr.log"
curl -i http://127.0.0.1:8765/api/status
~~~

最后一个命令在未带 token 时返回 401，表示 HTTP 进程响应了请求，**不代表设备在线**。骑行台仍为 simulator mode；BLE 心率状态由 /api/devices 返回。

## 备份数据库（SQLite 在线备份）

先确定你正在使用的 CYCLING_DB；如未配置，则使用默认路径。为了避免数据库正在写入时直接 cp，推荐使用 SQLite backup API：

~~~bash
python3 - <<'PY'
from pathlib import Path
import datetime, os, sqlite3
src = Path(os.environ.get("CYCLING_DB", str(Path.home() / ".local/share/indoor-cycling/sessions.sqlite3")))
dst_dir = Path.home() / "IndoorCyclingBackups"
dst_dir.mkdir(parents=True, exist_ok=True)
dst = dst_dir / ("sessions-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".sqlite3")
if not src.is_file():
    raise SystemExit(f"Database not found: {src}")
with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as source:
    with sqlite3.connect(dst) as target:
        source.backup(target)
dst.chmod(0o600)
print("Backup created:", dst)
PY
~~~

恢复流程：先停止模拟服务及 LaunchAgent、确认当前 schema 与备份兼容、备份当前数据库，再使用 sqlite3 backup 或文件复制将备份恢复到正确的 CYCLING_DB 位置，检查权限与 SQLite 完整性，最后重启。对于未来 schema 变更，恢复前需要对应版本的迁移策略，不能简单覆盖。

项目**没有自动备份**。建议将备份位置置于加密磁盘并由使用者自行配置周期备份。不要将个人训练数据库推送至 GitHub。

## 常见故障定位

| 现象 | 检查项 |
| --- | --- |
| command not found | 检查 .venv 是否激活、是否执行 pip install -e |
| 端口无法访问 | 服务是否运行，是否监听 127.0.0.1，端口是否被占用 |
| HTTP 401 | CYCLING_TOKEN 未设置或与网页输入不一致 |
| HTTP 422 | JSON 请求字段/模拟功率范围错误 |
| 启动时报 CYCLING_TOKEN | 终端环境变量或 runtime.env 丢失 |
| LaunchAgent 无法启动 | 文件路径、Python 虚拟环境、登录会话、权限、stderr.log |
| 页面无法从手机打开 | 当前默认本机监听；手机 PWA HTTPS 部署尚未实现 |
| 扫描不到设备 | macOS 蓝牙授权、设备广播模式、其他 App 占用 |
| 运动数据不符合现实 | 未连接设备时使用模拟指标；连接后心率实测，功率仍为模拟 |

## 安全运行与变更要求

即使未来完成 FTMS，软件断线不意味着阻力一定会自动降为零；硬件控制之前必须有实测安全退出途径、命令回执、约束值、心率失联处理和人工停止方案。事故风险高于软件功能完成度，未通过硬件验收不能升级为真实控制模式。

对于项目的 CI 与人工验收范围，见 [07](07-status-and-acceptance.md)。

## BLE 心率与设备管理更新

设备接口全部要求控制令牌。设备标识、名称及真实心率仅保存在本地数据库，不提交。令牌改为当前标签页 sessionStorage 保留以支持跨子页面导航；同源脚本可读取，使用完关闭标签页。BLE 错误接口不返回设备原始诊断日志。
