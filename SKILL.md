---
name: kust-webvpn-paper-download
description: 用昆明理工大学图书馆 WebVPN（本地 Chrome CDP）批量下载付费墙期刊/会议论文 PDF。触发词：昆工图书馆 VPN、WebVPN、CCF 期刊正式版、付费墙论文下载、机构访问下载。
---

# 昆明理工大学图书馆 WebVPN 论文下载

经学校 WebVPN（`https://w.libvpn.kust.edu.cn`）以机构订阅权限批量获取论文正式版 PDF。
**只能在本地电脑的 Chrome 里走通**（WebVPN 是 Service-Worker 代理），远程服务器无法直连。

## 合规红线

机构访问权限**仅限个人科研用途**：每篇间隔 ≥12 秒、每 10 篇休息 60 秒、
单批 10–20 篇、不对出版商全库爬取。遇 Cloudflare Turnstile 等人机验证时
暂停并请用户手动点击，不绕过付费墙。

## 前置条件

- Windows + Chrome（本方法在其他系统未验证，macOS/Linux 需自行调整启动命令）
- Python 3：`pip install requests websocket-client`
- 论文清单 JSONL：每行 `{"arxiv_id","doi","container"}`（DOI 可为空时走标题检索，未实现）
- 脚本：本 skill 的 `assets/kust_journal_batch.py`（可移植，参数经环境变量/命令行）

## 第一步：启动专用 Chrome（关键，坑最多）

**必须用 PowerShell `Start-Process` 内联命令**（不要写 .ps1 文件——中文编码易炸；
不要从 Git Bash 直接启动——MSYS 路径转换会损毁 chrome.exe 路径）：

```powershell
powershell -Command "Start-Process 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList '--remote-debugging-port=9223','--remote-allow-origins=*','--user-data-dir=C:\Users\<你>\AppData\Local\Temp\kust_chrome_profile_v2','--no-first-run','--no-default-browser-check','--window-size=1200,900','https://w.libvpn.kust.edu.cn'"
```

坑位清单：
- **9222 端口常被其他工作浏览器占用**（本项目微信小程序浏览器等）——用 9223 或先查 `netstat -ano | findstr 9223`
- **同一 profile 目录不能双开**（ProcessSingleton 锁，报"Lock file can not be created"）——锁死就换新 profile 目录或杀旧实例
- 启动后验证：`curl http://127.0.0.1:9223/json/version`

## 第二步：登录（人工，一次性）

在弹出的窗口里完成 CAS 登录（账号密码 + **算术验证码** + **短信二次验证**），
看到"可访问的应用列表"即成功。**cookie 持久化在 profile 里**：之后重启 Chrome
同一 profile 无需重登，直到学校服务端会话 TTL 过期。

登录态检测（CDP 取页面文本查"资源检索/外文资源"关键词）。

## 代理 URL 格式（2026-11 实测，旧格式已废弃）

```
✅ https://w.libvpn.kust.edu.cn/<原路径>?__proto__=https&__host__=<原域名>
❌ https://w.libvpn.kust.edu.cn/-https://<域名>/<路径>   （9 月旧格式，已失效）
```

SW 代理会**自动跟随跨域重定向**：导航到 `.../10.1109/xxx?__proto__=https&__host__=doi.org`
会直接落到 `.../document/<arnumber>?__proto__=https&__host__=ieeexplore.ieee.org`。

## 第三步：批量下载

```bash
python kust_journal_batch.py --limit 3          # 冒烟
python kust_journal_batch.py --limit 20         # 一批（合规节奏）
python kust_journal_batch.py --limit 20 --offset 20
# 环境变量：KUST_CDP（默认 http://127.0.0.1:9223）、KUST_VPN
# 参数：--list 清单路径、--out-dir 输出目录
```

流程：导航代理化 doi.org → 识别出版社 → 分流抓取（页内
`fetch(url,{credentials:'include'})` 转 base64 → 校验 `%PDF-` 魔数 + >20KB）：

| 出版社 | 通道 | 实测 |
|---|---|---|
| IEEE | 落点 URL 抽 `arnumber` → `/stampPDF/getPDF.jsp` 页内 fetch | ✅ 95%+ 成功率 |
| Springer | `/content/pdf/<doi>.pdf` 直接 fetch | 直链，应该顺 |
| ACM | `/doi/pdf/<doi>` | ❌ Cloudflare 防护，暂无解 |
| Elsevier | 轮询 `citation_pdf_url` | ⚠️ Turnstile 风险 |

## 接力 runner 模式（长时间批量）

后台 bash 循环 + 两条保险（见 `assets/journal_chain.sh` 模板）：
1. 每批前 `curl 127.0.0.1:9223` 检查 CDP，断了用上述 PowerShell 命令自动重启
   Chrome（cookie 在 profile，**不用重登**）
2. 批后 grep 日志里的 `not_proxied`——出现即会话过期，熔断并标记 LOGIN_REQUIRED

## 排障速查（全部实战踩过）

| 症状 | 根因 | 处理 |
|---|---|---|
| 端口拒绝连接 | Chrome 窗口被关/没起 | 重启 Chrome（同 profile 免重登） |
| Lock file can not be created | profile 双开锁 | 换新 profile 目录或杀旧实例 |
| 9222 上是别的页面 | 端口被工作浏览器占用 | 换 9223 并同步改脚本 `KUST_CDP` |
| 落点 `not_proxied` | 会话过期（早期特征） | 重新登录 |
| **落点变 `cas.kmust.edu.cn` / `pub=` 空 / cands=0** | **会话过期（真实特征，2026-11-02 实测：登录后 ~4.5-5h TTL）** | **重新登录** |
| DOI Not Found 页 | DOI 本身错误（不是代理问题） | 核对清单 |
| WebSocketTimeoutException | 单请求挂起 | CDP 重连 + 重试该篇（勿弃批） |
| 0 candidates | SPA 未渲染完 / 旧代理格式 | 轮询 meta 或走出版社直链 |
| Git Bash 启动 Chrome 路径损坏 | MSYS 路径转换 | 用 PowerShell Start-Process |

## 移植到其他电脑

1. 拷贝整个 skill 目录（或 `git clone` 本仓库；**codex 用户见仓库根 `CODEX.md`**——含
   可直接粘贴到 `~/.codex/AGENTS.md` 的接入片段）
2. `pip install requests websocket-client`，确认 Chrome 路径
3. 把脚本里/命令里的用户名路径换成新机的（profile 目录、chrome.exe）
4. 首次使用需人工登录一次；之后 cookie 随 profile 目录走
5. 环境变量 `KUST_CDP` / `KUST_VPN` 可改端口与 VPN 主机（其他学校 WebVPN 若同架构可直接换主机名）

## 与项目管线的衔接

- 清单来源：cv-survey 库 `05_extraction/journal_paywall_list.jsonl`（Crossref DOI + 无 OA 副本）
- 下载完成后：`scp` 回传远程 `04_fulltext/journal/`，按 arxiv_id 关联入库（has_journal_pdf 状态）
- 免费部分已由 Unpaywall 阶段覆盖（`cv_journal_oa.py`），VPN 只兜付费墙
