# StudyFlow Debian ARM64 部署说明

目标：Orange Pi Zero 3（4GB RAM）、Armbian Debian ARM64、Python 3、SQLite、Wi-Fi；使用 Gunicorn + systemd，仅监听 `127.0.0.1:5000`。暂不安装或启动 FRP/ChmlFrp，不开放公网。

## 1. 系统依赖

以具有 sudo 权限的管理员执行：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip sqlite3 curl ca-certificates
# Pillow 在 ARM64 上通常有预编译 wheel；若 pip 需要本地编译，再安装：
# sudo apt install -y build-essential libjpeg62-turbo-dev zlib1g-dev
```

不安装 Docker、Kubernetes 或其他编排系统。业务依赖均为纯 Python 或 ARM64 可用 wheel；Gunicorn、Flask、requests、Pillow 不依赖 x86 专用二进制。

## 2. 创建运行用户和目录

```bash
sudo useradd --system --create-home --home-dir /home/studyflow --shell /usr/sbin/nologin studyflow
sudo mkdir -p /opt/studyflow /opt/studyflow/data/uploads /opt/studyflow/logs
sudo chown -R studyflow:studyflow /opt/studyflow
sudo chmod 750 /opt/studyflow
sudo chmod 700 /opt/studyflow/data /opt/studyflow/data/uploads
sudo chmod 750 /opt/studyflow/logs
```

把项目文件放到 `/opt/studyflow`。不要复制 `.env` 到可被 Web 静态目录访问的位置；项目根目录本身不会作为静态目录暴露，Flask 只服务 `frontend/`。

## 3. Python 虚拟环境与依赖

```bash
cd /opt/studyflow
sudo -u studyflow python3 -m venv .venv
sudo -u studyflow .venv/bin/python -m pip install --upgrade pip
sudo -u studyflow .venv/bin/pip install -r requirements.txt
```

确认架构：

```bash
uname -m          # 应为 aarch64
.venv/bin/python -c "import platform; print(platform.machine())"
.venv/bin/python -c "import PIL, flask, gunicorn; print(PIL.__version__, flask.__version__, gunicorn.__version__)"
```

## 4. 生成安全配置

### SECRET_KEY

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 管理员密码哈希

```bash
cd /opt/studyflow
sudo -u studyflow .venv/bin/python scripts/hash_password.py
```

脚本使用 `getpass`，不显示、不记录明文密码；输出只有 Werkzeug `scrypt` 哈希。

### `.env`

```bash
sudo -u studyflow cp /opt/studyflow/.env.example /opt/studyflow/.env
sudo -u studyflow nano /opt/studyflow/.env
sudo chmod 600 /opt/studyflow/.env
sudo chown studyflow:studyflow /opt/studyflow/.env
```

至少填写：

```dotenv
FLASK_ENV=production
HOST=127.0.0.1
PORT=5000
SECRET_KEY=<安全随机值>
STUDYFLOW_PASSWORD_HASH=<hash_password.py 的输出>
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_SECURE=false
SESSION_LIFETIME_HOURS=12
LOGIN_MAX_ATTEMPTS=5
LOGIN_WINDOW_SECONDS=900
TRUST_PROXY=false
SEED_DEMO=false
```

同时按实际部署填写已有 AI Provider、Key、Base URL、模型和时区；不要更换或清空现有 AI 配置。

- **应用启动时会强制校验** `SECRET_KEY` 和 `STUDYFLOW_PASSWORD_HASH`。缺失、占位或过短会直接报错，不会以弱默认值启动。
- 不要把真实密码、哈希、SECRET_KEY、AI Key 写入 Git。
- `.env` 已被 `.gitignore` 忽略；权限保持 `600`。

### HTTPS 与反向代理

当前先保持 `SESSION_COOKIE_SECURE=false`，避免纯 HTTP 本地登录时浏览器丢弃 Session Cookie。

待 HTTPS 反向代理/ChmlFrp 正式启用、并且确认外部访问为 HTTPS 后，再：

```dotenv
SESSION_COOKIE_SECURE=true
TRUST_PROXY=true
```

`TRUST_PROXY=true` 只应在一层可信反向代理后面使用；它启用 `ProxyFix`，信任一层 `X-Forwarded-For/Proto/Host`。如果 Flask 直接被访问，保持 `false`。

**本任务不安装、不启动 FRP，不修改 ChmlFrp 配置。**

## 5. 初始化数据库（仅首次）

现有生产数据请按第 11 节迁移；全新实例才执行：

```bash
cd /opt/studyflow
sudo -u studyflow .venv/bin/python scripts/init_db.py --no-seed
```

`SEED_DEMO=false`，不会自动写入演示数据。初始化前必须已经配置好 `.env` 中的安全参数。

## 6. Gunicorn 启动

生产命令：

```bash
cd /opt/studyflow
sudo -u studyflow .venv/bin/gunicorn --config deploy/gunicorn.conf.py wsgi:app
```

`deploy/gunicorn.conf.py` 固定：

- `bind = "127.0.0.1:5000"`
- `worker_class = "gthread"`
- 默认 2 workers × 2 threads
- 120 秒超时
- 日志写入 `/opt/studyflow/logs/access.log`、`error.log`

不要使用 `python run.py` 对公网提供服务。开发服务器只用于本机开发。

本机验证：

```bash
curl -I http://127.0.0.1:5000/login
```

应返回 `200`。直接访问 `/` 会重定向到 `/login`；未登录访问 `/api/meta` 返回 JSON `401`，不是 HTML 登录页。

## 7. systemd 服务

```bash
sudo cp /opt/studyflow/deploy/studyflow.service /etc/systemd/system/studyflow.service
sudo systemd-analyze verify /etc/systemd/system/studyflow.service
sudo systemctl daemon-reload
sudo systemctl enable --now studyflow
sudo systemctl status studyflow --no-pager
```

服务文件中的 `User/Group`、`WorkingDirectory`、`EnvironmentFile`、`ReadWritePaths` 按 `/opt/studyflow` 编写；如果实际目录不同，必须同步修改。

常用命令：

```bash
sudo systemctl restart studyflow
sudo systemctl stop studyflow
sudo journalctl -u studyflow -f
sudo tail -f /opt/studyflow/logs/error.log
```

服务设置了：

- `Restart=on-failure`、`RestartSec=5`
- `ProtectSystem=strict`
- 仅 `data/`、`logs/` 可写
- `NoNewPrivileges=true`、`PrivateTmp=true`
- `UMask=0077`

## 8. 防火墙/网络

Gunicorn 只绑定回环地址：

```bash
ss -ltnp | grep 5000
# 应看到 127.0.0.1:5000，而不是 0.0.0.0:5000
```

本阶段不开放公网端口，不启动 FRP。后续只允许 ChmlFrp 或可信反向代理连接本机回环端口。

## 9. 登录与会话安全

- 单管理员密码，无注册、无多用户。
- `POST /api/auth/login` 成功后才建立 Session。
- 所有页面、`/api/*`、`/uploads/*` 默认需要登录；登录/登出是明确例外。
- 未登录 API 返回 JSON `401 AUTH_REQUIRED`，不会返回登录页 HTML。
- Session Cookie：`HttpOnly`、`SameSite=Lax`、可配置 `Secure`。
- Session 默认 12 小时过期；登录会清空旧 Session（防会话固定）。
- 登录失败按 IP 限制：默认 5 次/15 分钟；只记录失败次数，不记录密码。
- 写请求带同源 `Origin/Referer` 校验，结合 SameSite 做基本 CSRF 防护。
- 登出按钮位于侧栏底部。

**限制**：登录限流是进程内固定窗口。当前配置是 2 个 Gunicorn worker，因此每个 worker 各自计数；对单管理员场景足够，但不等同于分布式账户锁定。需要严格跨 worker 限流时，应接入受保护的集中式限流存储，本次没有引入。

## 10. 数据库与上传文件权限/备份

生产数据：

```text
/opt/studyflow/data/studyflow.db
/opt/studyflow/data/uploads/
```

权限建议：

```bash
sudo chown -R studyflow:studyflow /opt/studyflow/data
sudo chmod 700 /opt/studyflow/data /opt/studyflow/data/uploads
sudo chmod 600 /opt/studyflow/data/studyflow.db
```

在线备份（SQLite backup API，不直接复制正在写入的 DB）：

```bash
sudo bash /opt/studyflow/scripts/backup_db.sh
```

或手动：

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
sudo mkdir -p /var/backups/studyflow
sudo sqlite3 /opt/studyflow/data/studyflow.db ".backup '/var/backups/studyflow/studyflow-$STAMP.sqlite'"
sudo chmod 600 /var/backups/studyflow/studyflow-$STAMP.sqlite
sudo tar -C /opt/studyflow/data -czf /var/backups/studyflow/uploads-$STAMP.tar.gz uploads
sudo chmod 600 /var/backups/studyflow/uploads-$STAMP.tar.gz
sudo sha256sum /var/backups/studyflow/studyflow-$STAMP.sqlite
```

将备份文件复制到另一台设备/离线介质；不要只留在 Orange Pi 上。备份包含私人学习数据，权限必须为 `600`，不得进入 Git。

## 11. 迁移现有数据库/上传文件

如果已有本地 `data/studyflow.db` 和 `data/uploads/`：

1. 先备份现有数据。
2. 停止旧服务（如有）。
3. 将 DB 和 uploads 放到 `/opt/studyflow/data/`。
4. 执行第 10 节权限设置。
5. 启动 Gunicorn/systemd 后登录验证。
6. 不要用 `seed_demo`、清空数据或重建数据表来“初始化”已有生产库。

数据库 Schema 和业务表不会被部署脚本修改；应用启动只执行幂等的 `init_schema`。

## 12. 保持账户安全

- 管理员密码至少 12 位，建议使用密码管理器生成的长随机密码。
- 修改密码时重新运行 `scripts/hash_password.py`，替换 `.env` 中 `STUDYFLOW_PASSWORD_HASH`，再重启 `studyflow.service`。
- 每 3 个月轮换 `SECRET_KEY` 会使现有 Session 全部失效（用户需重新登录），这是预期行为。
- `.env`、备份、数据库、上传文件都不要提交 Git。
- HTTPS 未完成前不要将 5000 端口直接暴露到公网。

## 13. 部署验收清单

- [ ] `ss -ltnp` 只显示 `127.0.0.1:5000`
- [ ] `systemctl status studyflow` 为 active
- [ ] `curl -I http://127.0.0.1:5000/login` 为 200
- [ ] 未登录 `/api/meta` 返回 JSON 401
- [ ] 正确密码可登录，错误密码有明确提示
- [ ] 侧栏“退出登录”可用
- [ ] 十个页面加载正常
- [ ] 现有 DB、上传文件、AI 配置未丢失
- [ ] `backup_db.sh` 可生成 600 权限备份
- [ ] 未启动 FRP
