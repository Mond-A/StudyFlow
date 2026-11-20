# StudyFlow v1.1.0 → v1.1.1 升级说明

## 1. 变更范围

v1.1.1 是邮箱验证安全与可靠性补丁，不重写认证系统，不引入 Redis、消息队列、2FA 或短信验证码，也不改变现有 SMTP 通用接口。

- 注册、重发验证邮件增加 SQLite 共享限流：IP、邮箱、全站发送量。
- 重发 SMTP 失败不再提前作废旧验证链接。
- Gunicorn 访问日志不记录 query string。
- console 邮件后端不再输出 token/完整 URL；生产环境误用 console 会失败关闭。
- 前端补齐验证失败、注册邮件失败、未验证登录的重发入口。
- 新增异常路径回归测试。

## 2. 数据库兼容性

**本版本有一个向后兼容的列迁移，不需要单独执行迁移脚本。**

- `init_schema` 会为 v1.1.0 的 `auth_accounts` 表补上 `active_verification_token_id INTEGER`；应用启动或 `scripts/init_db.py` 会幂等执行。
- 迁移在 `BEGIN IMMEDIATE` 写锁内串行执行 Schema、补列、active 回填和默认用户创建；多个 Gunicorn Worker 同时启动时不会重复迁移。
- 对未验证账户，回填最新的未使用、未过期 token；已验证账户清空 active；没有有效 token 的账户保持 `NULL`。
- 新列只记录当前有效验证 token 的自增 id，不删除用户、账户、验证记录或上传文件。
- 继续使用 v1.1.0 已有的 `login_rate_limits` 表保存登录、注册和重发计数；只增加带命名空间的键。
- 旧的 `email_verification_tokens` 记录保持有效；v1.1.1 改变重发 token 的激活和旧 token 失效时机。
- 验证接口同时检查 `used_at`、`expires_at` 和 active 指针；迁移后只有 active token 可通过验证。
- 限流行按 24 小时保留期机会性清理；不清理业务数据。
- 重复执行初始化不会破坏现有数据；升级流程不需要重新运行 `init_db`，启动时会补列和回填。

## 3. 升级前备份

先停止写入并生成可验证快照。以下命令以现有部署路径为例，实际路径以 `/opt/studyflow/.env` 为准：

```bash
cd /opt/studyflow
sudo systemctl stop studyflow
sudo -u studyflow .venv/bin/python scripts/backup_snapshot.py \
  --database /opt/studyflow/data/studyflow.db \
  --uploads /opt/studyflow/data/uploads \
  --backup-root /opt/studyflow/data/backups \
  --label pre-v1.1.1
```

确认输出目录中的 `manifest.json` 至少包含：

- `integrity_check: "ok"`
- `restore.restore_verified: true`
- 数据库表计数和每个上传文件的 SHA-256

将快照复制到离线介质，并记录快照路径。不要只根据文件存在判断备份成功。

## 4. 升级步骤

1. 保持服务停止，替换代码到 v1.1.1。
2. 不修改生产 `.env` 中的密钥、数据库路径或上传路径。
3. 如使用生产 SMTP，确认：
   - `FLASK_ENV=production`
   - `MAIL_BACKEND=smtp`
   - `SMTP_HOST` 和认证信息完整
   - `PUBLIC_BASE_URL` 是外部可访问的 HTTPS 地址
   - `TRUST_PROXY` 和 `SESSION_COOKIE_SECURE` 与反向代理一致

   v1.1.1 会在启动阶段校验 `PUBLIC_BASE_URL`；HTTP、localhost、私网/保留 IP、异常端口、凭据或 query/fragment 会导致启动失败。hostname 会做 DNS 解析，所有 A/AAAA 必须为公网地址，DNS 失败为 fail-closed；DNS 结果只代表检查时状态，不能保证未来不变。

4. 可选地按部署规模调整注册/重发限流；不设置时使用默认值：

   ```dotenv
   ACCOUNT_RATE_WINDOW_SECONDS=3600
   REGISTER_IP_LIMIT=20
   REGISTER_EMAIL_LIMIT=3
   REGISTER_GLOBAL_LIMIT=100
   RESEND_IP_LIMIT=20
   RESEND_EMAIL_LIMIT=5
   RESEND_GLOBAL_LIMIT=200
   ```

   共享公网 IP 的部署可保留较宽的 IP 配额，不要为了单用户方便把全局限制关掉。

5. 本版本没有新增 Python 依赖；如现有虚拟环境完整，不需要重新安装依赖。若使用标准流程，可按现有部署文档执行 `pip install -r requirements.txt`。
6. 启动服务：

   ```bash
   sudo systemctl start studyflow
   sudo systemctl status studyflow --no-pager
   ```

7. 验收：
   - `/api/health/db` 返回正常。
   - 注册一个非生产测试邮箱，确认验证邮件到达。
   - 点击验证链接后能登录。
   - 在 SMTP 临时失败场景确认返回 `503 EMAIL_DELIVERY_FAILED`，账户仍未验证；恢复 SMTP 后重发成功。
   - 确认 Gunicorn/反向代理日志中没有 `token=` 或完整验证 URL。

## 5. 失败回滚

v1.1.1 只新增了一个可空列；回滚 v1.1.0 代码时旧代码会忽略该列，通常只需回滚代码：

1. 停止服务。
2. 恢复 v1.1.0 代码。
3. 启动服务并检查健康接口、登录和已有数据。
4. 仅在数据库确实损坏或升级过程中发生异常写入时，使用升级前快照恢复数据库；上传文件按部署文档手动恢复并核对 manifest 哈希。
5. 回滚后重新检查 `MAIL_BACKEND`、`PUBLIC_BASE_URL` 和日志配置。

不要使用未经验证的备份覆盖生产库；恢复脚本会先创建当前目标的安全快照。

## 6. 日志配置检查

- Gunicorn：v1.1.1 的 `deploy/gunicorn.conf.py` 不再使用 `%(r)s` 或 `%(q)s`，只记录方法/路径/协议。
- Nginx：默认 `$request`/`$request_uri` 可能包含 query；使用不含 query 的 `log_format`。
- Caddy：默认 access log 的 `request.uri` 包含 query；应在 Caddy 日志 filter/format 中删除 `?` 及其后的 query，或关闭该路径访问日志。不同 Caddy 版本语法不同，修改后执行 `caddy validate`。
- 应用日志：console 后端只记录“已入队”提示，不输出 token 或完整 URL；生产误用 console 会直接失败，不写 outbox。

仓库不包含 Nginx/Caddy 的实际站点配置，反向代理日志必须由运维人员在目标主机上核对。

## 7. 兼容性

- 目标平台：Orange Pi Zero 3、Debian Bookworm ARM64。
- 无新增原生扩展、Redis、队列或外部服务。
- 限流依赖现有 SQLite 数据库；多主机各自使用独立数据库时不共享限流计数。
- 生产数据库迁移、SMTP 真实投递和恢复演练必须由操作员在维护窗口执行；本说明不自动执行任何生产操作。
