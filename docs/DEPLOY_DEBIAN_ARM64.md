# StudyFlow Debian ARM64 部署说明

目标：Orange Pi Zero 3（4GB RAM）、Armbian Debian ARM64、Python 3、SQLite、Wi-Fi；使用 Gunicorn + systemd，仅监听 `127.0.0.1:5000`。本文包含启用公网前的 HTTPS/反向代理检查项；当前阶段不安装或启动 FRP/ChmlFrp，不开放公网。

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

### 启动兼容密码哈希

```bash
cd /opt/studyflow
sudo -u studyflow .venv/bin/python scripts/hash_password.py
```

脚本使用 `getpass`，不显示、不记录明文密码；输出只有 Werkzeug `scrypt` 哈希。

该哈希仍用于启动校验，并在数据库还没有任何邮箱账户时提供旧库过渡登录。它不是新用户的正常登录方式：正式用户应通过 `/login?mode=register` 用邮箱注册并完成验证。创建邮箱账户后，旧密码入口自动失效。

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
# 本机纯 HTTP 开发为 false；完成 HTTPS 反向代理后改为 true
SESSION_COOKIE_SECURE=false
SESSION_LIFETIME_HOURS=12
LOGIN_MAX_ATTEMPTS=5
LOGIN_WINDOW_SECONDS=900
# 只有在一层可信反向代理后才改为 true
TRUST_PROXY=false
SEED_DEMO=false

# Email verification (production)
MAIL_BACKEND=smtp
MAIL_FROM=StudyFlow <no-reply@example.com>
# 本机开发可先保留 http://127.0.0.1:5000；公网/HTTPS 必须改成外部地址
PUBLIC_BASE_URL=https://studyflow.example.com
EMAIL_VERIFICATION_HOURS=24
PASSWORD_MIN_LENGTH=12
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=<smtp-user>
SMTP_PASSWORD=<smtp-password>
SMTP_USE_TLS=true
SMTP_USE_SSL=false

# 可选：注册/重发验证邮件的共享 SQLite 限流（默认值如下）
ACCOUNT_RATE_WINDOW_SECONDS=3600
REGISTER_IP_LIMIT=20
REGISTER_EMAIL_LIMIT=3
REGISTER_GLOBAL_LIMIT=100
RESEND_IP_LIMIT=20
RESEND_EMAIL_LIMIT=5
RESEND_GLOBAL_LIMIT=200
```

`SESSION_COOKIE_SECURE=false` 只适用于本机纯 HTTP 开发；通过 HTTPS 反向代理提供服务时必须改为 `true`。

`TRUST_PROXY=true` 只应在一层可信反向代理后面使用；它启用 `ProxyFix`，只信任一层 `X-Forwarded-For/Proto/Host`。如果 Flask 被直接访问，必须保持 `false`。

**SMTP**：

- 本地开发可先使用 `MAIL_BACKEND=console`：不会真实发送，只把验证 URL 记录在内存 outbox 供测试/调试；不再把 token 或完整 URL 写入应用日志。
- 生产必须使用 `smtp`，并让 `MAIL_FROM` 的域与 SMTP 服务商授权一致；上线前实际收一封验证邮件确认链路。
- `SMTP_USE_SSL=true` 使用 465/SMTPS，此时应把 `SMTP_USE_TLS=false`；使用 STARTTLS（如 587）时保持 `SMTP_USE_TLS=true`、`SMTP_USE_SSL=false`。
- `PUBLIC_BASE_URL` 必须是用户能访问的外部地址；验证链接为 `${PUBLIC_BASE_URL}/verify-email?token=...`。
- SMTP 失败会返回 `503 EMAIL_DELIVERY_FAILED`，账户保持未验证，用户可稍后重试“重发验证邮件”。

### HTTPS 与反向代理

Gunicorn 只监听回环地址，HTTPS 应在反向代理（例如 Nginx）终止。下面的域名、证书路径均为占位示例，必须替换为实际值：

```nginx
server {
    listen 80;
    server_name studyflow.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name studyflow.example.com;

    ssl_certificate     /etc/letsencrypt/live/studyflow.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/studyflow.example.com/privkey.pem;

    client_max_body_size 12m;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Host $host;
        proxy_read_timeout 120s;
    }
}
```

启用后：

```dotenv
SESSION_COOKIE_SECURE=true
TRUST_PROXY=true
PUBLIC_BASE_URL=https://studyflow.example.com
```

`PUBLIC_BASE_URL` 在 `FLASK_ENV=production` 且非测试模式下会于启动阶段校验：必须是外部 HTTPS 地址，不能是 localhost、私网/保留 IP、明文 HTTP、带凭据或带 query/fragment；hostname 会做 DNS 解析，所有 A/AAAA 结果必须是公网地址，DNS 失败会 fail-closed。DNS 校验只代表启动时的解析结果，不能保证未来解析不变。配置错误时应用直接拒绝启动，而不是等发送邮件时失败。

- 不要让公网直接访问 `127.0.0.1:5000`；防火墙只允许反向代理所在主机访问。
- 反向代理必须保留 `Host`、`X-Forwarded-Proto` 和客户端 IP 头；不要信任来自任意客户端的转发头。
- 本仓库不安装 Nginx、TLS 证书或 FRP/ChmlFrp；相关操作需由运维人员单独完成，不在本次文档变更中自动执行。
- ChmlFrp/FRP 不是 HTTPS 的替代品；若使用，仍需确认端到端 TLS 和可信代理解析。

### 访问日志脱敏

v1.1.1 的 Gunicorn 配置已改为只记录请求方法、路径和协议（`%(m)s %(U)s %(H)s`），不再使用包含 query string 的原始请求行。

反向代理仍需单独处理，否则 `/verify-email?token=...` 的 token 可能进入代理日志：

- **Nginx**：默认 `$request`/`$request_uri` 包含 query。应使用自定义 `log_format`，采用 `$request_method $uri $server_protocol`一类的字段，并确保 `access_log` 使用该格式；不要记录 `$args`。
- **Caddy**：默认 JSON access log 的 `request.uri` 包含 query。建议在 Caddy 的日志 filter/format 中对 `request.uri` 删除 `?` 及其后的 query，或对该路由关闭 access log；不同 Caddy 版本的 filter 语法不同，修改后先执行 `caddy validate`。不要只依赖 Gunicorn 配置。
- 仓库不包含 Nginx 站点配置或 Caddyfile；这些必须在实际部署主机上由运维人员核对。不要为了脱敏而删除状态码、路径、耗时等正常诊断字段。

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
- 登录失败计数存于 SQLite 的 `login_rate_limits` 表，两个 worker 共享同一窗口，不再按进程各算一份

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

## 9. 邮箱账户、访客模式与会话安全

- 正式账户以邮箱为登录标识；用户通过 `/login?mode=register` 注册，必须完成邮件验证后才能登录。
- 登录使用邮箱和密码；密码只保存 `scrypt` 哈希。
- `STUDYFLOW_PASSWORD_HASH` 是启动校验和旧库过渡入口，不是新用户登录方式；一旦存在邮箱账户，旧入口失效。
- 所有业务页面、`/api/*`、`/uploads/*` 默认需要 Session；`/api/auth/*`、`/login`、`/guest`、`/verify-email` 是明确公开入口。
- `/api/health` 和 `/api/health/db` 也需要登录，不能作为匿名健康检查使用。
- 未登录 API 返回 JSON `401 AUTH_REQUIRED`，不会返回登录页 HTML。
- Session Cookie：`HttpOnly`、`SameSite=Lax`（可配置）、HTTPS 下应配置 `Secure`。
- Session 默认 12 小时过期；登录会清空旧 Session（防会话固定）。
- 登录失败按来源 IP + 邮箱限制：默认 5 次/15 分钟；计数表由 SQLite 共享，Gunicorn 多 worker 使用同一份计数。
- 写请求带同源 `Origin/Referer` 校验，结合 SameSite 做基本 CSRF 防护。
- 每个账户只能读写自己的业务记录和上传文件；没有管理员越权查看全部用户数据的 API。
- 访客模式先经过 `/guest` 确认页并清除正式 Session；数据只保存在浏览器 IndexedDB。AI 在访客模式下不可用。登录后导入访客数据必须由用户在前端明确确认；服务端按当前 Session 用户导入并保持幂等。
- 登出按钮位于侧栏底部；`POST /api/auth/logout` 立即清除 Session。

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

### 备份能力现状

**手动执行，不是自动任务。** 仓库没有安装 cron、systemd timer 或自动备份服务；操作员必须自己运行下面的脚本，并自行把结果复制到离线介质。

| 方式 | 产物 | 完整性验证 | 恢复能力 |
| --- | --- | --- | --- |
| `scripts/backup_db.sh` | SQLite `.sqlite` + `uploads` `.tar.gz` | 脚本输出文件路径和 SHA-256；不自动做恢复验证 | 数据库可单独恢复；uploads 需手动解压 |
| `scripts/backup_snapshot.py` | 一个有 manifest 的目录：DB、uploads 副本、`manifest.json` | `PRAGMA integrity_check`、源/备份表计数比较、上传文件 SHA-256、临时目录恢复检查 | DB 可用 `restore_snapshot.py`；uploads 目前需手动复制 |

手动在线备份（服务继续运行；SQLite 使用 backup API）：

```bash
sudo bash /opt/studyflow/scripts/backup_db.sh
```

更完整的快照（建议在变更或升级前运行）：

```bash
cd /opt/studyflow
sudo -u studyflow .venv/bin/python scripts/backup_snapshot.py \
  --database /opt/studyflow/data/studyflow.db \
  --uploads /opt/studyflow/data/uploads \
  --backup-root /opt/studyflow/data/backups \
  --label manual
```

脚本会拒绝不完整/不一致的快照，并在临时目录中验证数据库和每个上传文件的哈希；它不会自动删除旧备份。

**验证已有备份**：

- `backup_snapshot.py` 的 `manifest.json` 应包含 `integrity_check: "ok"`、`restore.restore_verified: true`、表计数和每个 upload 的 `sha256`。
- 可用 `sha256sum` 对备份文件复核；不要只根据文件存在判断成功。
- 定期做恢复演练，但必须在临时目标上进行，不能直接覆盖生产库。

**数据库恢复（显式、会先创建安全快照）**：

```bash
cd /opt/studyflow
sudo systemctl stop studyflow
sudo -u studyflow .venv/bin/python scripts/restore_snapshot.py \
  --backup-db /opt/studyflow/data/backups/manual-YYYYmmddTHHMMSSZ/studyflow.db \
  --database /opt/studyflow/data/studyflow.db \
  --uploads /opt/studyflow/data/uploads \
  --backup-root /opt/studyflow/data/backups
sudo systemctl start studyflow
```

`restore_snapshot.py` **只替换数据库文件**，并先对当前目标创建 `pre-manual-restore` 快照；`--uploads` 仅用于创建这个安全快照。它不会自动恢复 uploads。

**上传文件恢复（手动）**：

1. 先停止服务并确认已有一份可用的当前 uploads 快照。
2. 对 `backup_db.sh` 的 tar 包，先检查内容再解压：
   ```bash
   tar -tzf /var/backups/studyflow/studyflow-uploads-YYYYmmddTHHMMSSZ.tar.gz | head
   ```
   然后按实际路径解压到 `/opt/studyflow/data/`，确认得到 `uploads/` 目录。
3. 对 `backup_snapshot.py` 的快照，把 `manual-.../uploads/` 内容同步到 `/opt/studyflow/data/uploads/`；建议先移动到临时目录，核对 manifest 中哈希后再替换。
4. 恢复后重新设置所有者和 `700/600` 权限，启动服务，检查 `/api/health/db`、登录、上传文件访问和关键数据。

不要把数据库和上传文件恢复到不一致的时间点；如果两者来自不同备份，要明确说明。备份含私人学习数据、登录邮箱和上传内容，权限保持 `600`，不得提交 Git，也不得发送到公共位置。

## 11. 旧实例迁移（不是新用户流程）

本节只适用于已有旧版 StudyFlow 数据库/上传文件的运维迁移，不是当前邮箱用户的正常注册流程。全新实例请跳过本节，直接注册邮箱账户。

如果已有本地 `data/studyflow.db` 和 `data/uploads/`：

1. 先按第 10 节做并验证备份。
2. 停止旧服务（如有）。
3. 将 DB 和 uploads 放到 `/opt/studyflow/data/`。
4. 执行第 10 节权限设置。
5. 若要把旧业务数据归属到邮箱账户，在完成并验证第 10 节备份后显式运行迁移脚本（示例邮箱必须替换）：
   ```bash
   cd /opt/studyflow
   sudo -u studyflow .venv/bin/python scripts/migrate_iteration1.py \
     --admin-email admin@example.invalid \
     --database /opt/studyflow/data/studyflow.db \
     --uploads /opt/studyflow/data/uploads \
     --backup-root /opt/studyflow/data/backups
   ```
   该脚本会先创建并验证快照，再把旧默认用户链接到指定的已验证账户；它不是新用户注册流程。
6. 启动 Gunicorn/systemd，检查旧数据是否可读，再创建/验证其他邮箱账户。
7. 不要用 `seed_demo`、清空数据或重建数据表来“初始化”已有生产库。

应用启动只执行幂等的 `init_schema`，不会自动执行 `migrate_iteration1.py`，也不会把旧数据自动归属到新邮箱账户。此次变更新增的 `login_rate_limits` 辅助表会自动创建，不修改现有用户/业务表数据。旧密码入口只在尚无邮箱账户时存在，是兼容桥，不是推荐使用方式。

## 12. 保持账户安全

- 邮箱账户密码至少 12 位，建议使用密码管理器生成的长随机密码。
- 旧库兼容哈希只用于过渡；修改它时重新运行 `scripts/hash_password.py`，替换 `.env` 中 `STUDYFLOW_PASSWORD_HASH`，再重启 `studyflow.service`。不要把它当作所有用户的共享密码。
- 当前没有密码找回、邮箱变更/重新验证、2FA 或账户冻结流程；上线前应在产品层明确这些限制，不要向用户承诺未实现的能力。
- 轮换 `SECRET_KEY` 会使现有 Session 全部失效（用户需重新登录），这是预期行为。
- `.env`、备份、数据库、上传文件都不要提交 Git。
- HTTPS 未完成前不要将 5000 端口直接暴露到公网。

## 13. 部署验收清单

- [ ] `ss -ltnp` 只显示 `127.0.0.1:5000`
- [ ] `systemctl status studyflow` 为 active
- [ ] `curl -I http://127.0.0.1:5000/login` 为 200
- [ ] 未登录 `/api/meta` 返回 JSON 401
- [ ] `/login?mode=register` 能创建账户
- [ ] 生产 SMTP 能实际收到验证邮件，验证链接使用 `PUBLIC_BASE_URL`
- [ ] 未验证账户不能登录；验证后可以登录
- [ ] 两个不同账户的数据、upload URL 相互隔离
- [ ] 错误密码/未验证邮箱有明确提示；多 worker 下限流仍生效
- [ ] 侧栏“退出登录”可用
- [ ] `/guest` 确认页可用；访客 AI 被拒绝；登录后导入必须二次确认
- [ ] 十个页面加载正常
- [ ] 现有 DB、上传文件、AI 配置未丢失
- [ ] HTTPS 反向代理生效，`SESSION_COOKIE_SECURE=true`、`TRUST_PROXY=true`（仅一层代理）
- [ ] `backup_db.sh` 或 `backup_snapshot.py` 可生成并验证备份（权限 600）
- [ ] 已做过一次临时目标恢复演练；确认 uploads 恢复步骤
- [ ] 未安装自动备份任务时，没有把“自动备份”写成已完成
- [ ] 未启动 FRP；未直接暴露 5000 端口
