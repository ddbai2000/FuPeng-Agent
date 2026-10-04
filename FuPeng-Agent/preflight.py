"""FuPeng Agent — 采集前置复查（铁律 1：每次采集前先看看做过什么，省算力）。

用法:
    python preflight.py            # 打印已转录/已蒸馏/待蒸馏汇总，不改动任何状态
    python preflight.py --json     # 输出 JSON（供 agent / cron 解析）

只做**只读复查**：扫 state.json（seen/distilled）+ transcripts/*.txt + docs/skills/，
打印一份"已做过什么 / 还能做什么"的清单，绝不下载、绝不转录。
agent 读完后，再决定要不要跑 collect_and_transcribe.py（只采未 seen 的）。

退出码:
    0 = 有"已转录未蒸馏"或"可新采"的工作（建议继续流程）
    3 = 全空、无新动态（NO_WORK，采集脚本可跳过，省算力）
"""
import json, os, sys, glob, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # FuPeng-agent/
STATE = os.path.join(HERE, "state.json")
TRANS = os.path.join(HERE, "transcripts")
SKILLS = os.path.join(ROOT, "docs", "skills")


def _state():
    if not os.path.exists(STATE):
        return {"seen": {}, "asr_jobs": [], "distilled": {}}
    try:
        with open(STATE, encoding="utf-8") as f:
            d = json.load(f)
        d.setdefault("seen", {}); d.setdefault("asr_jobs", []); d.setdefault("distilled", {})
        return d
    except Exception:
        return {"seen": {}, "asr_jobs": [], "distilled": {}}


def _transcripts():
    """transcripts/*.txt（排除 .log）-> {key: bytes}"""
    out = {}
    for p in glob.glob(os.path.join(TRANS, "*.txt")):
        base = os.path.splitext(os.path.basename(p))[0]
        # 文件名形如 youtube_<vid>.txt -> key youtube:<vid>
        key = base.replace("_", ":", 1) if base[:1] in "y" else base
        # 更稳：把前缀按平台还原（仅 youtube 前缀常见）
        if base.startswith("youtube_"):
            key = "youtube:" + base[len("youtube_"):]
        elif base.startswith("bilibili_"):
            key = "bilibili:" + base[len("bilibili_"):]
        elif base.startswith("douyin_"):
            key = "douyin:" + base[len("douyin_"):]
        out[key] = os.path.getsize(p)
    return out


def _skills():
    """docs/skills/ 下有哪些技能目录"""
    if not os.path.isdir(SKILLS):
        return []
    return sorted(d for d in os.listdir(SKILLS)
                  if os.path.isdir(os.path.join(SKILLS, d))
                  and os.path.exists(os.path.join(SKILLS, d, "SKILL.md")))


def report():
    s = _state()
    seen = set(s["seen"].keys())
    distilled = set(s["distilled"].keys())
    tr = _transcripts()
    jobs = {m["key"]: m for m in s["asr_jobs"]}

    # 已转录且未蒸馏 = 可立即蒸馏（省算力：不必重跑 ASR）
    distilled_now = sorted(set(tr) & set(k for k in tr if k not in distilled))
    # 待蒸馏：有转录文件 + 未 distilled
    pending_distill = [k for k in sorted(tr) if k not in distilled]

    # 已 seen（含 seen 但还没转录完的）
    no_transcript_seen = sorted(k for k in seen if k not in tr)

    summary = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "seen_total": len(seen),
        "transcribed_total": len(tr),
        "distilled_total": len(distilled),
        "skills_installed": _skills(),
        "pending_distill": pending_distill,        # 有转录未蒸馏 -> 直接进蒸馏，别再 ASR
        "seen_no_transcript": no_transcript_seen,  # 见过但还没转完（在途/queued）
        "new_to_collect": "仅当跑 collect 时才会发现；preflight 不联网",
    }
    return summary


def main():
    as_json = "--json" in sys.argv
    r = report()

    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print("=" * 60)
        print("FuPeng 采集前置复查（铁律 1：先看做过什么再动手）")
        print("=" * 60)
        print(f"seen（见过）        : {r['seen_total']}")
        print(f"已转录              : {r['transcribed_total']}")
        print(f"已蒸馏              : {r['distilled_total']}")
        print(f"已安装技能          : {', '.join(r['skills_installed']) or '(无)'}")
        print("-" * 60)
        if r["pending_distill"]:
            print("【有转录未蒸馏】→ 直接进蒸馏，别再跑 ASR（省算力）:")
            for k in r["pending_distill"]:
                print(f"  - {k}")
        else:
            print("无「已转录未蒸馏」→ 蒸馏环节 NO_WORK。")
        if r["seen_no_transcript"]:
            print(f"【见过但转录未落盘（在途/queued）】{len(r['seen_no_transcript'])} 条: "
                  f"{', '.join(r['seen_no_transcript'][:10])}")
        print("-" * 60)
        work = bool(r["pending_distill"]) or bool(r["seen_no_transcript"])
        print("结论: " + ("有活（先蒸馏/继续 ASR，再考虑新采集）" if work
                         else "全空（NO_WORK，可跳过采集，省算力）"))
    sys.exit(0 if (r["pending_distill"] or r["seen_no_transcript"]) else 3)


if __name__ == "__main__":
    main()
