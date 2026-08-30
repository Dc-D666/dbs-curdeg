# -*- coding: utf-8 -*-
import json, io, subprocess, time, sys
CLI = r"C:/Users/33031/AppData/Roaming/npm/tencent-channel-cli.cmd"
rows = json.load(io.open("collected.json", encoding="utf-8"))
cand = [r for r in rows if "山东大学" in ((r.get("name") or "") + (r.get("profile") or ""))]
cand.sort(key=lambda r: -(r.get("member_count") or 0))
cand = cand[:15]
out = {}
for i, r in enumerate(cand, 1):
    gid = r["guild_id"]
    p = subprocess.run([CLI, "manage", "get-guild-info", "--guild-id", gid, "--json"], capture_output=True)
    o = p.stdout.decode("utf-8", "replace").strip()
    j = o.find("{")
    try:
        d = json.loads(o[j:])
    except Exception:
        d = None
    if d and d.get("success"):
        out[gid] = d["data"]
    else:
        out[gid] = {"_error": (d or {}).get("error") if d else "parse_fail"}
    print("%d/15 %s -> %s" % (i, r["name"][:20], "ok" if "_error" not in (out[gid] or {}) else "ERR"), file=sys.stderr)
    time.sleep(2)
json.dump(out, io.open("enrich.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
