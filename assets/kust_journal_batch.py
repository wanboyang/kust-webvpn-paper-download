#!/usr/bin/env python3
"""kust_journal_batch.py -- Download paywalled journal PDFs through KUST WebVPN
using a visible Chrome CDP session. Portable skill asset.

Proxy format (2026-11, path-style SW proxy):
    https://w.libvpn.kust.edu.cn/<path>?__proto__=https&__host__=<host>

Environment:
    KUST_CDP  CDP endpoint           (default http://127.0.0.1:9223)
    KUST_VPN  WebVPN base URL        (default https://w.libvpn.kust.edu.cn)

Usage:
    python kust_journal_batch.py --limit 3
    python kust_journal_batch.py --limit 20 --offset 20 \
        --list journal_paywall_list.jsonl --out-dir ./journal_pdfs

Compliance: personal research use only; >=12s between papers; stop at any
bot-check (Turnstile) and ask the human; never bulk-crawl publishers.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.parse

import requests
import websocket

VPN = os.environ.get("KUST_VPN", "https://w.libvpn.kust.edu.cn")
CDP_HTTP = os.environ.get("KUST_CDP", "http://127.0.0.1:9223")
PAPER_SLEEP = 12
CHUNK_SLEEP = 60
CHUNK_EVERY = 10

# Host guard: VPN base must be https + a public hostname (no
# localhost/loopback/private/reserved). CDP endpoint is deliberately
# 127.0.0.1 -- it is the local Chrome debug bridge, not a server request.


def validate_vpn_base(url):
    m = re.match(r"^(https)://([A-Za-z0-9.\-]+)$", url or "")
    if not m:
        raise SystemExit(f"KUST_VPN must be https://<public-host>, got: {url!r}")
    host = m.group(2)
    bad = ("localhost", "127.", "0.0.0.0", "10.", "192.168.", "169.254.", "[::1]")
    if any(host.startswith(b) for b in bad) or host.endswith(".local"):
        raise SystemExit(f"refusing private/loopback VPN host: {host}")
    return url


VPN = validate_vpn_base(VPN)


def get_ws():
    targets = requests.get(CDP_HTTP + "/json", timeout=5).json()
    for t in targets:
        if t.get("type") == "page":
            return t["webSocketDebuggerUrl"]
    raise RuntimeError("no page target")


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=600)
        self.mid = 0

    def cmd(self, method, params=None):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params or {}}))
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get("id") == self.mid:
                if "error" in resp:
                    raise RuntimeError(f"CDP error: {resp['error']}")
                return resp.get("result", {})

    def nav(self, url):
        self.cmd("Page.navigate", {"url": url})

    def ev(self, expr):
        result = self.cmd("Runtime.evaluate",
                          {"expression": expr, "returnByValue": True,
                           "awaitPromise": True})
        return result.get("result", {}).get("value")

    def location(self):
        return self.ev("location.href") or ""


def proxied(host, path_and_query):
    sep = "&" if "?" in path_and_query else "?"
    return f"{VPN}/{path_and_query}{sep}__proto__=https&__host__={host}"


def fetch_bytes(cdp, url):
    expr = ("(async()=>{try{const r=await fetch(%s,{credentials:'include'});"
            "if(!r.ok)return 'ERR:'+r.status;"
            "const b=await r.arrayBuffer();const u=new Uint8Array(b);let s='';"
            "for(let i=0;i<u.length;i+=0x8000){s+=String.fromCharCode.apply(null,u.subarray(i,i+0x8000));}"
            "return 'OK:'+btoa(s);}catch(e){return 'ERR:'+e.message;}})()" % json.dumps(url))
    got = cdp.ev(expr)
    if got and got.startswith("OK:"):
        raw = base64.b64decode(got[3:])
        if raw[:5] == b"%PDF-" and len(raw) > 20000:
            return raw
    return None


def try_download(cdp, doi, arxiv_id):
    cdp.nav(proxied("doi.org", doi))
    time.sleep(16)
    loc = cdp.location()
    if "w.libvpn" not in loc and "__host__" not in loc:
        return False, f"not_proxied: {loc[:80]}"
    m = re.search(r"__host__=([A-Za-z0-9.\-]+)", loc)
    pub = m.group(1) if m else ""
    arn = None
    if "ieeexplore" in pub:
        am = re.search(r"/document/(\d+)", loc)
        arn = am.group(1) if am else None

    meta = None
    for _ in range(4):
        meta = cdp.ev(
            '(document.querySelector(\'meta[name="citation_pdf_url"]\')||{}).content || null')
        if meta:
            break
        time.sleep(5)

    candidates = []
    if "ieeexplore" in pub and arn:
        candidates.append(("ieee-getpdf",
                           proxied("ieeexplore.ieee.org",
                                   f"stampPDF/getPDF.jsp?tp=&arnumber={arn}")))
    if "link.springer.com" in pub:
        candidates.append(("springer-pdf",
                           proxied("link.springer.com", f"content/pdf/{doi}.pdf")))
    if "dl.acm.org" in pub:
        candidates.append(("acm-pdf", proxied("dl.acm.org", f"doi/pdf/{doi}")))
    if meta:
        mm = re.match(r"https?://([^/]+)(/.*)", meta)
        if mm:
            candidates.append(("citation_pdf_url",
                               proxied(mm.group(1), mm.group(2).lstrip("/"))))
    for _, url in list(candidates):
        if "stamp.jsp" in url and "arnumber=" in url:
            am = re.search(r"arnumber=(\d+)", url)
            if am:
                candidates.append(("ieee-getpdf-meta",
                                   proxied("ieeexplore.ieee.org",
                                           f"stampPDF/getPDF.jsp?tp=&arnumber={am.group(1)}")))

    for label, url in candidates[:6]:
        raw = fetch_bytes(cdp, url)
        if raw:
            with open(os.path.join(OUT_DIR, arxiv_id + ".pdf"), "wb") as f:
                f.write(raw)
            print(f"    -> OK [{label}] {len(raw)//1024} KB", flush=True)
            return True, None
        time.sleep(2)
    return False, f"no_pdf pub={pub} arn={arn} cands={len(candidates)}"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", default=os.path.join(here, "journal_paywall_list.jsonl"))
    ap.add_argument("--out-dir", default=os.path.join(here, "journal_pdfs"))
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--offset", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    manifest = os.path.join(a.out_dir, "journal_pdf_manifest.jsonl")

    items = [json.loads(l) for l in open(a.list, encoding="utf-8") if l.strip()]
    done = set()
    if os.path.exists(manifest):
        for line in open(manifest, encoding="utf-8"):
            try:
                r = json.loads(line)
                if r["status"] == "ok":
                    done.add(r["arxiv_id"])
            except Exception:
                pass
    queue = [it for it in items if it["arxiv_id"] not in done][a.offset:a.offset + a.limit]
    print(f"[journal-batch] total={len(items)} done={len(done)} this-run={len(queue)}", flush=True)

    cdp = CDP(get_ws())
    stats = {"ok": 0, "fail": 0}
    mf = open(manifest, "a", encoding="utf-8")
    for i, it in enumerate(queue):
        aid, doi = it["arxiv_id"], (it.get("doi") or "").replace("https://doi.org/", "")
        if not doi:
            print(f"  {i + 1} {aid} SKIP no-doi", flush=True)
            continue
        ok, err = False, None
        try:
            ok, err = try_download(cdp, doi, aid)
        except Exception as e:  # noqa: BLE001 - a hung paper must not kill the batch
            err = f"{type(e).__name__}: {str(e)[:60]}"
            print(f"    !! exception, reconnecting CDP: {err}", flush=True)
            try:
                time.sleep(10)
                cdp = CDP(get_ws())
            except Exception as e2:  # noqa: BLE001
                print(f"    !! reconnect failed: {e2}; aborting run", flush=True)
                mf.close()
                sys.exit(2)
        stats["ok" if ok else "fail"] += 1
        mf.write(json.dumps({"arxiv_id": aid, "doi": doi,
                             "container": it.get("container"),
                             "status": "ok" if ok else "fail", "err": err},
                            ensure_ascii=False) + "\n")
        mf.flush()
        print(f"  {i + 1}/{len(queue)} {aid} {'OK' if ok else 'FAIL ' + str(err)}", flush=True)
        if i + 1 < len(queue):
            time.sleep(PAPER_SLEEP)
        if (i + 1) % CHUNK_EVERY == 0:
            print(f"  -- chunk pause {CHUNK_SLEEP}s --", flush=True)
            time.sleep(CHUNK_SLEEP)
    mf.close()
    print(f"[journal-batch] DONE {stats}", flush=True)


if __name__ == "__main__":
    main()
