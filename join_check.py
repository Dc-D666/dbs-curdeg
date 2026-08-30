# -*- coding: utf-8 -*-
"""
检查 24 个 >=200 人频道的：① 是否已加入 ② 加入方式(joinType) ③ 帖子是否可浏览
对 DIRECT 类型直接加入；需要验证的（附言/答题/测试题/禁止）输出清单待人工处理
用法: python join_check.py
"""
import json, io, sys, time, subprocess

CLI = r"C:/Users/33031/AppData/Roaming/npm/tencent-channel-cli.cmd"
SRC = "migrant_data/shandong_university_channels.json"
OUT = "migrant_data/join_report.json"
NEEDS = "migrant_data/join_needed.md"


def run(args, stdin=None):
    p = subprocess.run([CLI] + args + ["--json"], capture_output=True,
                       input=stdin.encode() if stdin else None)
    out = p.stdout.decode("utf-8", "replace")
    i = out.find("{")
    out = out[i:] if i >= 0 else ""
    try:
        return json.loads(out)
    except Exception:
        return {"success": False, "error": {"message": "parse_fail:" + out[:200]}}


def main():
    dry = "--apply" not in sys.argv
    chans = [c for c in json.load(io.open(SRC, encoding="utf-8"))["channels"]
             if (c.get("member_count") or 0) >= 200]
    chans.sort(key=lambda c: -(c.get("member_count") or 0))

    mine = set()
    d = run(["manage", "get-my-join-guild-info"])
    dd = d.get("data") or {}
    for k in ("created_guilds", "joined_guilds", "managed_guilds"):
        for g in dd.get(k) or []:
            mine.add(str(g.get("guild_id")))
    print("already in %d guilds (my list)" % len(mine))

    rows = []
    for idx, c in enumerate(chans, 1):
        gid = str(c["guild_id"])
        rec = {"rank": idx, "guild_id": gid, "name": c["name"],
               "member_count": c["member_count"], "guild_number": c.get("guild_number"),
               "share_url": c.get("share_url"), "already_joined": gid in mine}

        s = run(["manage", "get-join-guild-setting", "--guild-id", gid])
        setting = (s.get("data") or {}).get("setting") or {}
        rec["join_type"] = setting.get("joinType") or ((s.get("error") or {}).get("message"))
        rec["questions"] = (setting.get("question") or {}).get("items") or []
        rec["quiz"] = setting.get("quiz") or []
        time.sleep(0.4)

        f = run(["feed", "get-guild-feeds", "--guild-id", gid, "--get-type", "2", "--count", "3"])
        rec["feed_readable_before"] = bool(f.get("success"))
        rec["feed_ret_code"] = (f.get("error") or {}).get("code", 0 if f.get("success") else None)
        rec["feed_err"] = ((f.get("error") or {}).get("message") or "")[:120]
        time.sleep(0.4)

        rec["action"] = "none"
        if not rec["already_joined"] and not rec["feed_readable_before"]:
            if rec["join_type"] == "JOIN_GUILD_TYPE_DIRECT":
                if dry:
                    rec["action"] = "would_join_direct"
                else:
                    j = run(["manage", "join-guild", "--guild-id", gid])
                    rec["action"] = "joined" if j.get("success") else "join_failed"
                    rec["join_result"] = (j.get("error") or {}).get("message") if not j.get("success") else "ok"
                    time.sleep(0.8)
            elif rec["join_type"] == "JOIN_GUILD_TYPE_DISABLE":
                rec["action"] = "blocked_disable"
            elif rec["join_type"]:
                rec["action"] = "need_verification"
        elif rec["already_joined"]:
            rec["action"] = "already_member"
        else:
            rec["action"] = "public_readable_no_join"
        rows.append(rec)
        print("%2d %-26s %-28s joined=%-5s read=%-5s %s" % (
            idx, (c["name"] or "")[:24], str(rec["join_type"]).replace("JOIN_GUILD_TYPE_", "")[:26],
            rec["already_joined"], rec["feed_readable_before"], rec["action"]))
        io.open(OUT, "w", encoding="utf-8").write(json.dumps(rows, ensure_ascii=False, indent=2))

    # 待人工处理清单
    lines = ["# 需要人工提供申请理由/答案的频道清单", "",
             "模式: %s" % ("DRY-RUN（未实际加入）" if dry else "已执行加入"), ""]
    need = [r for r in rows if r["action"] in ("need_verification", "blocked_disable")]
    auto = [r for r in rows if r["action"] in ("joined", "would_join_direct")]
    lines.append("## 一、可直接加入（脚本已自动处理，共 %d 个）" % len(auto))
    for r in auto:
        lines.append("- %s | %s | %s | %s" % (r["name"], r["member_count"], r["guild_id"], r["action"]))
    lines.append("")
    lines.append("## 二、需要你提供申请理由/答案（共 %d 个）" % len(need))
    for r in need:
        lines.append("")
        lines.append("### %s（%s 人）" % (r["name"], r["member_count"]))
        lines.append("- guild_id: `%s`  频道号: `%s`" % (r["guild_id"], r.get("guild_number")))
        lines.append("- 加入方式: `%s`" % r["join_type"])
        lines.append("- 分享链接: %s" % r.get("share_url"))
        lines.append("- 帖子当前可读: %s" % r["feed_readable_before"])
        if r["questions"]:
            lines.append("- 验证问题:")
            for i, q in enumerate(r["questions"], 1):
                lines.append("  %d. %s" % (i, q.get("question") if isinstance(q, dict) else q))
        if r["quiz"]:
            lines.append("- 答题题目:")
            for i, q in enumerate(r["quiz"], 1):
                lines.append("  %d. %s | 选项: %s" % (i, q.get("question"), q.get("options") or q))
        if not r["questions"] and not r["quiz"]:
            lines.append("- 需要: 申请附言（join_guild_comment），无固定问题")
    lines.append("")
    lines.append("## 三、无需加入即可浏览（共 %d 个）" % len([r for r in rows if r["action"] == "public_readable_no_join"]))
    for r in rows:
        if r["action"] == "public_readable_no_join":
            lines.append("- %s | %s | %s" % (r["name"], r["member_count"], r["guild_id"]))
    lines.append("")
    lines.append("## 四、已是成员（共 %d 个）" % len([r for r in rows if r["action"] == "already_member"]))
    for r in rows:
        if r["action"] == "already_member":
            lines.append("- %s | %s | %s | join_type=%s" % (r["name"], r["member_count"], r["guild_id"], r["join_type"]))
    io.open(NEEDS, "w", encoding="utf-8").write("\n".join(lines))
    print("\nreport -> %s\nchecklist -> %s" % (OUT, NEEDS))


if __name__ == "__main__":
    main()
