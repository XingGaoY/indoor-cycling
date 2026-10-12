# 03 · Mac mini / macOS 部署手册

**部署状态：模拟器可部署；真实骑行台 ERG、手机 HTTPS/PWA 以及 COROS 上传尚未交付。** 本文只覆盖当前代码真实具备的本机服务能力。长期运行采用**用户登录会话中的 LaunchAgent**，不是系统 LaunchDaemon；避免假设无登录会话即可使用 CoreBluetooth。

## A. 新 Mac mini 首次部署

1. 在目标用户会话中安装 Git、Python 3.11+，完成 [01](01-quick-start.md) 的 clone、venv、pip、pytest。
2. 先在 Terminal 启动模拟器，并验证 http://127.0.0.1:8765。
3. 按下述方式创建**仓库外**的运行令牌文件；这一步会要求使用者在自己的终端执行，不得将 token 存入 Git。
4. 运行 LaunchAgent 安装脚本；在本机确认服务可访问并查看日志。
5. 如要进行 BLE 诊断，请先在当前用户 Terminal 交互运行 scan/inspect 并处理 macOS 蓝牙授权；这与后台服务是否有权限是两件事。

## B. 创建持久化配置（只需一次）

~~~bash
mkdir -p "$HOME/.config/indoor-cycling"
chmod 700 "$HOME/.config/indoor-cycling"
python3 - <<'PY'
import pathlib, secrets
p = pathlib.Path.home() / ".config/indoor-cycling/runtime.env"
with p.open("x", encoding="utf-8") as f:
    f.write("CYCLING_TOKEN=" + secrets.token_urlsafe(32) + "\n")
p.chmod(0o600)
print("Created", p)
PY
~~~

已有 runtime.env 时脚本会拒绝覆盖，避免重置正在使用的控制令牌。可手动在文件中增加 CYCLING_DB=/absolute/path/record.sqlite3 或 CYCLING_PORT=8765；该文件由 shell 加载，仅使用可信内容，不要从他人处直接执行配置。

如需要读取 token 用于本机网页，使用终端查看配置文件；不要通过工单、截图或 GitHub issue 分享。删除配置文件会使后续启动失败，但不会清除数据库。

## C. LaunchAgent 安装（当前仅模拟器）

在已克隆仓库根目录，且 .venv 已创建并安装好依赖时运行：

~~~bash
bash scripts/macos/install-launch-agent.sh
launchctl print "gui/$(id -u)/dev.indoorcycling.simulator"
curl -i http://127.0.0.1:8765/api/status
# 缺少 token 应返回 HTTP 401
~~~

安装脚本生成 ~/Library/LaunchAgents/dev.indoorcycling.simulator.plist，并将日志写入 ~/Library/Logs/IndoorCycling/。使用 127.0.0.1 绑定；即使配置了 CYCLING_PORT 也不应直接使用公网代理或开放端口。

检查日志：

~~~bash
tail -n 100 "$HOME/Library/Logs/IndoorCycling/stderr.log"
tail -n 100 "$HOME/Library/Logs/IndoorCycling/stdout.log"
~~~

LaunchAgent 在用户登录会话启动，受用户登出、系统休眠、权限弹窗和 macOS 更新等因素影响；Mac mini 实机常驻可靠性尚待验证。确认 macOS 能源设置适合长时间运行；对真实设备控制必须另外做断连与唤醒测试。

卸载服务：

~~~bash
bash scripts/macos/uninstall-launch-agent.sh
~~~

这只停用并移除 LaunchAgent，不会删除源代码、数据库或 runtime.env。想在另一台设备部署，重复 A–C 并为该设备生成**独立 token**。

## D. 从另一台电脑进行安全的远程开发

当前服务仅监听 Mac mini 本机。开发者在另一台电脑可通过 SSH 端口转发访问本机开发服务（须先正确设置 SSH 账号权限）：

~~~bash
ssh -N -L 8765:127.0.0.1:8765 youruser@your-macmini-host
~~~

然后在**开发电脑**打开 http://127.0.0.1:8765。此方法将流量放进 SSH 隧道；它不是手机 PWA 的正式部署方案。不要直接将服务监听改成 0.0.0.0，也不要把现有简单 token 认证当作可公开部署的安全边界。

## E. 更新、回滚与备份

更新前，在 Mac mini 上记下当前 commit，并备份数据库（具体见 [06](06-security-and-operations.md)），然后停止服务：

~~~bash
git rev-parse HEAD
bash scripts/macos/uninstall-launch-agent.sh
git switch main
git pull --ff-only
source .venv/bin/activate
python -m pip install -e ".[test]"
python -m pytest -q
bash scripts/macos/install-launch-agent.sh
~~~

如需回滚，在确认已保存旧提交号和数据库备份后，停止服务，然后 git switch --detach <known-good-sha>，重装依赖并启动；恢复数据库必须检查版本与 schema 兼容性，不能盲目用旧程序打开升级过的数据库。恢复 stable 分支前，应重新检视版本状态。

## F. 当前未支持的部署模式

- 手机跨设备访问需要可信 HTTPS、细化的权限模型与更完善的 PWA，尚未实现。
- 目前不支持云服务器直连家庭 BLE 硬件。
- 不把 Docker 作为 macOS BLE 原生控制进程的默认部署方式。
- 真实 ERG 控制需经过独立硬件测试与安全验收，不能因为模拟服务启动成功就视作通过。

运行问题与备份说明见 [06](06-security-and-operations.md)。
