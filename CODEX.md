# codex 接入（AGENTS.md 片段）

codex 通过 `~/.codex/AGENTS.md` 发现能力。其他电脑接入本 skill 的完整步骤：

## 1. 克隆仓库（任意稳定位置，建议固定不动）

```bash
git clone https://github.com/wanboyang/kust-webvpn-paper-download.git \
    ~/kust-webvpn-paper-download
pip install requests websocket-client
```

## 2. 把下面整段追加到 `~/.codex/AGENTS.md`（Windows 为 `C:\Users\<你>\.codex\AGENTS.md`）

```markdown
## KUST WebVPN 批量论文下载 skill

昆工图书馆 WebVPN 批量下载付费论文的完整操作手册：
`<克隆路径>/kust-webvpn-paper-download/SKILL.md`
（脚本 `assets/kust_journal_batch.py`；断点续跑；出版社分流：IEEE getPDF ✅、
Springer 直链 ✅、Elsevier ⚠️ Turnstile、ACM ❌）。

- **代理格式（2026-11 实测）**：`https://w.libvpn.kust.edu.cn/<路径>?__proto__=https&__host__=<域名>`
- **接入**：PowerShell `Start-Process` 启动专用 Chrome（`--remote-debugging-port=9223` +
  独立 `--user-data-dir`）+ CAS 登录（算术验证码 + 短信）；cookie 随 profile 持久化，
  重启 Chrome 免重登（会话 TTL 约 4.5–5 小时，过期特征 = 落回 CAS 页 / `pub=` 空）
- **批量**：`python assets/kust_journal_batch.py --limit 20`（env `KUST_CDP`/`KUST_VPN` 可调）
- 涉及"昆工 VPN / WebVPN / 付费墙论文下载"任务时**先读该 SKILL.md 再动手**
- 合规红线：机构权限仅个人科研，间隔 ≥12s、单批 10–20 篇，遇 Turnstile 停下请用户手点
```

把 `<克隆路径>` 替换为第 1 步的实际路径。

## 3. 验证

对新 codex 会话说「用昆工 WebVPN 下载这篇论文的正式版 PDF：10.1109/xxx」，
codex 应先读 SKILL.md，再按流程启动 Chrome → 请你登录 → 批量下载。

## 注意

- Windows 环境验证过；Git Bash 直接启动 Chrome 会因 MSYS 路径转换损毁路径，
  务必按 SKILL.md 用 PowerShell `Start-Process`
- 学校 WebVPN 会话 TTL 约 4.5–5 小时，过期后重新登录即可（cookie 保留账号输入）
- 合规：机构权限仅限个人科研用途
