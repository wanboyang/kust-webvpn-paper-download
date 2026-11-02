# kust-webvpn-paper-download

昆明理工大学图书馆 WebVPN（本地 Chrome CDP）批量下载付费墙论文 PDF 的 agent skill。
适用于 zcode / codex / kimi 等支持 skill 或 AGENTS.md 的 agent。

## 安装到新电脑

```bash
# zcode：克隆进 skills 目录
git clone https://github.com/wanboyang/kust-webvpn-paper-download.git \
    "$HOME/.zcode/skills/kust-webvpn-paper-download"

# codex：克隆到任意固定位置，然后把 CODEX.md 里的片段追加到 ~/.codex/AGENTS.md
git clone https://github.com/wanboyang/kust-webvpn-paper-download.git \
    ~/kust-webvpn-paper-download
# 按 CODEX.md 操作

pip install requests websocket-client
```

然后打开 `SKILL.md` 按步骤操作：启动专用 Chrome（PowerShell Start-Process，端口 9223 +
独立 profile）→ CAS 登录（算术验证码 + 短信）→ `python assets/kust_journal_batch.py --limit 20`。

## 功能

- 代理格式自动适配 2026-11 版 WebVPN：`https://w.libvpn.kust.edu.cn/<路径>?__proto__=https&__host__=<域名>`
- 出版社分流：IEEE getPDF（95%+ 实测）、Springer 直链、Elsevier（Turnstile 风险）、ACM（暂不通）
- 断点续跑 manifest、单篇失败不拖垮批次、CDP 掉线自动重连
- cookie 随 profile 持久化：重启 Chrome 免重登（会话 TTL 约 4.5–5 小时）

## 合规

机构访问权限**仅限个人科研用途**。限速批量（≥12s/篇）、单批 10–20 篇、
不绕过付费墙与人机验证；遇 Turnstile 停下请人工点击。
