# Changelog

## v1.1.1 — 2026-11-19

### 修复

- 为注册和重发验证邮件增加共享 SQLite 限流：覆盖 IP、邮箱和全局发送量，并保留适合共享公网 IP 的较宽 IP 配额。
- 重发验证邮件时，先发送新邮件，成功后才激活新 token；SMTP 失败时保留旧的有效验证链接。
- 使用账户当前有效 token 指针和自增 token id 处理并发重发；并发成功发送不会互相作废到零有效 token。
- `auth_accounts` 增加可空的 `active_verification_token_id`，启动迁移在 SQLite 写锁内串行执行并回填最新有效 token，兼容 v1.1.0 数据库和多 Worker 启动。
- 验证接口同时检查 token 的 `used_at`、`expires_at` 和 active 指针；旧 token 不会因为迁移被无故取消，多个旧 token 只保留最新 active。
- 重发在 SMTP 前和激活事务内都会复核 `email_verified_at`；验证与重发并发时不会向已验证账户重新设置 active token，也不会在确认已验证后继续发送邮件。
- 验证 token 清理同时约束 token id 和 account id，避免清理操作误删其他账户 token 或清空其他账户 active 指针。
- 生产环境启动时校验 `PUBLIC_BASE_URL`：必须解析到公网地址的外部 HTTPS URL，拒绝 localhost、明文 HTTP、私网/保留地址、异常端口、凭据和 query/fragment；DNS 失败 fail-closed，测试环境仍允许本地 HTTP。
- 限流存储遇到 SQLite 连接/锁/繁忙时返回明确的 `503 RATE_LIMIT_UNAVAILABLE`，并正确回滚，不伪装成 429。
- Gunicorn 访问日志改为只记录方法/路径/协议，不再记录查询字符串中的验证 token。
- console 邮件后端不再输出包含 token 的完整验证 URL；生产环境误用 console 时直接失败，不写 outbox 或应用日志。
- 验证失败、注册邮件发送失败、未验证登录场景下，前端提供明确的重发验证入口。
- 新增注册/重发限流、并发重发、并发验证、SMTP 后激活前验证、真实事务回滚、token 所有权、并发/多进程迁移、旧 token 回填、SMTP 失败、数据库异常、DNS 校验、API 验证、日志脱敏和生产邮件后端保护测试。

### 已知限制

- 自动定期备份仍未实现。
- SMTP 真实投递和生产恢复演练仍需部署环境验证。
- Caddy 等外部反向代理的访问日志需由运维人员单独配置为不记录 query string。

## v1.1.0 — 2026-11-18

### 新功能

- 邮箱注册、邮箱验证和邮箱登录。
- 多用户账户体系，以及按 Session 用户隔离的任务、成绩、笔记、学习记录、闪卡、错题、设置和上传文件。
- 基于浏览器 IndexedDB 的访客模式；访客数据只保存在当前设备，不等同于云端账户。
- 支持用户明确确认后，将访客数据导入正式账户；导入按当前 Session 用户执行，保持幂等且不覆盖已有记录。
- 访客模式不依赖云端账户，AI 功能不可用。
- 新增账户认证、访客数据导入及相关安全处理。

### 安全与可靠性

- 加强 Session 身份绑定和跨用户数据访问隔离。
- 增强上传文件的用户归属验证，未授权文件不可通过猜测路径访问。
- 改进访客模式切换与 CSRF 来源校验。
- 登录限流改为 SQLite 共享计数，支持使用同一数据库的 Gunicorn 多 Worker；不再按进程各自计数。
- 补充旧数据库初始化、旧数据归属迁移和幂等性测试。

### 数据、备份与迁移工具

- 提供旧单用户数据向邮箱账户归属的显式迁移脚本 `scripts/migrate_iteration1.py`。
- 提供手动 SQLite + uploads 备份脚本 `scripts/backup_db.sh`。
- 提供带完整性检查、上传文件哈希校验和临时恢复检查的快照脚本 `scripts/backup_snapshot.py`。
- 提供显式数据库恢复脚本 `scripts/restore_snapshot.py`；上传文件恢复仍需按文档手动完成。

### 文档与开发体验

- 更新 README 和 API 文档，反映当前多用户架构、邮箱认证、访客模式和实际 API 行为。
- 新增 `SECURITY.md`。
- 完善部署、SMTP、HTTPS、备份与恢复说明。
- 新增 GitHub Actions CI，在 Push 和 Pull Request 时运行后端 pytest，并对前端 JavaScript 执行 `node --check`。
- 完善认证、隔离、访客导入和旧数据库兼容性测试覆盖。

### 技术栈

- Python / Flask
- SQLite
- Vanilla JavaScript
- IndexedDB
- Gunicorn
- GitHub Actions

### 尚未完成或未经生产验证

- 尚未实现自动定期备份；现有备份和恢复脚本需要手动执行，且没有 cron/systemd timer。
- 尚未实现密码找回、登录邮箱变更/重新验证、2FA 或账户冻结流程。
- 访客数据仅保存在当前浏览器；清除站点数据、换浏览器或换设备可能丢失，且不支持跨设备同步。
- 多主机如果各自使用独立数据库，不共享登录限流状态。
- SMTP 真实投递、HTTPS 反向代理和生产环境恢复演练尚未在本发布流程中验证。
- 上传文件恢复没有一键脚本；需按部署文档手动恢复并核对哈希。
