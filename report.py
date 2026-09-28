#!/usr/bin/env python3
"""오늘 스냅샷과 이전 스냅샷(1일·7일 전)을 비교해 reports/YYYY-MM-DD.md 와 .html 을 만든다."""
import json, sys, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAP = ROOT / "data" / "snapshots"
KST = dt.timezone(dt.timedelta(hours=9))
TOP_N = 10          # 24시간 조회 증가 상위
RECENT_TOP_N = 15   # 최근 7일 업로드 표에 보여줄 개수(조회수 순)


def load(date):
    p = SNAP / f"{date}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def nearest_before(date, max_back):
    """date 기준 max_back 일 전 스냅샷. 정확히 없으면 그보다 가까운 과거 중 가장 오래된 것을 쓴다."""
    d = dt.date.fromisoformat(date)
    for back in range(max_back, 0, -1):
        s = load((d - dt.timedelta(days=back)).isoformat())
        if s:
            return s, back
    return None, None


def fmt(n):
    return "—" if n is None else f"{n:,}"


def delta(a, b):
    if a is None or b is None:
        return "—"
    d = a - b
    return f"{'+' if d >= 0 else ''}{d:,}"


def age_days(published_at, now):
    p = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    return (now - p).total_seconds() / 86400


def ago(days):
    if days is None:
        return "—"
    return f"{days * 24:.0f}시간 전" if days < 1 else f"{days:.1f}일 전"


def ago_int(days):
    if days is None:
        return "—"
    return "오늘" if days < 1 else f"{days:.0f}일 전"


def dur(sec):
    if sec is None:
        return "—"
    return f"{sec // 60}:{sec % 60:02d}"


def build(date):
    today = load(date)
    if not today:
        sys.exit(f"스냅샷 없음: {date}")
    d1, d1_back = nearest_before(date, 1)
    d7, d7_back = nearest_before(date, 7)
    now = dt.datetime.fromisoformat(today["collected_at"])

    def prev_ch(snap, cid):
        return (snap or {}).get("channels", {}).get(cid) if snap else None

    # 1) 채널 요약
    rows = []
    for cid, ch in today["channels"].items():
        if "error" in ch:
            rows.append({"name": ch["name"], "error": ch["error"]})
            continue
        p1, p7 = prev_ch(d1, cid), prev_ch(d7, cid)
        vids = ch.get("videos", [])
        last_pub = max((v["published_at"] for v in vids), default=None)
        uploads_7d = sum(1 for v in vids if age_days(v["published_at"], now) <= 7)
        rows.append({
            "name": ch["name"], "verified": ch.get("verified"),
            "subs": ch["subscribers"],
            "subs_d1": delta(ch["subscribers"], p1 and p1.get("subscribers")),
            "subs_d7": delta(ch["subscribers"], p7 and p7.get("subscribers")),
            "views": ch["views"],
            "views_d1": delta(ch["views"], p1 and p1.get("views")),
            "views_d7": delta(ch["views"], p7 and p7.get("views")),
            "video_count": ch["video_count"],
            "uploads_7d": uploads_7d,
            "last_upload_days": round(age_days(last_pub, now), 1) if last_pub else None,
            "subs_drop": bool(p1 and ch["subscribers"] < p1.get("subscribers", 0)),
        })
    rows.sort(key=lambda r: -(r.get("subs") or 0))

    # 2) 24시간 조회 증가 상위 영상 (전일 스냅샷 있을 때만)
    gainers = []
    if d1:
        for cid, ch in today["channels"].items():
            prev_vids = {v["id"]: v for v in (prev_ch(d1, cid) or {}).get("videos", [])}
            for v in ch.get("videos", []):
                pv = prev_vids.get(v["id"])
                if pv:
                    gainers.append({"channel": ch["name"], "title": v["title"], "id": v["id"],
                                    "gain": v["views"] - pv["views"], "views": v["views"]})
        gainers.sort(key=lambda g: -g["gain"])
        gainers = gainers[:TOP_N]

    # 3) 최근 7일 업로드
    recent = []
    for cid, ch in today["channels"].items():
        for v in ch.get("videos", []):
            a = age_days(v["published_at"], now)
            if a <= 7:
                recent.append({"channel": ch["name"], "title": v["title"], "id": v["id"], "age": a,
                               "views": v["views"], "likes": v["likes"], "comments": v["comments"],
                               "duration": v["duration_sec"]})
    recent.sort(key=lambda r: -r["views"])

    # 4) 주의 신호
    alerts = []
    for r in rows:
        if r.get("error"):
            alerts.append(f"{r['name']}: {r['error']}")
            continue
        if r["last_upload_days"] is None:
            alerts.append(f"{r['name']}: 업로드 영상 없음")
        elif r["last_upload_days"] >= 7:
            alerts.append(f"{r['name']}: 마지막 업로드 {r['last_upload_days']:.0f}일 전")
        if r["subs_drop"]:
            alerts.append(f"{r['name']}: 구독자 감소 ({r['subs_d1']})")

    return {"date": date, "collected_at": now.strftime("%Y-%m-%d %H:%M KST"),
            "d1_back": d1_back, "d7_back": d7_back, "rows": rows, "gainers": gainers,
            "recent": recent, "alerts": alerts}


def yt(id_):
    return f"https://www.youtube.com/watch?v={id_}"


def to_markdown(r):
    L = [f"# 유튜브 일일 리포트 — {r['date']}", "", f"수집 시각: {r['collected_at']}"]
    if r["d1_back"] is None:
        L.append("전일 비교: 없음(첫 수집). 내일부터 Δ1일·조회 증가 상위가 채워집니다.")
    elif r["d1_back"] != 1:
        L.append(f"전일 비교: {r['d1_back']}일 전 스냅샷 기준(중간 누락).")
    if r["d7_back"] and r["d7_back"] != 7:
        L.append(f"주간 비교: {r['d7_back']}일 전 스냅샷 기준.")
    L += ["", "## 1. 채널 요약", "",
          "| 채널 | 구독자 | Δ1일 | Δ7일 | 총조회수 | Δ1일 | Δ7일 | 영상수 | 7일 업로드 | 마지막 업로드 |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for x in r["rows"]:
        if x.get("error"):
            L.append(f"| {x['name']} | 오류: {x['error']} | | | | | | | | |")
            continue
        name = x["name"] + ("" if x.get("verified") else " ※")
        L.append(f"| {name} | {fmt(x['subs'])} | {x['subs_d1']} | {x['subs_d7']} | {fmt(x['views'])} | {x['views_d1']} | {x['views_d7']} | {fmt(x['video_count'])} | {x['uploads_7d']} | {ago_int(x['last_upload_days'])} |")
    if any(not x.get("verified") for x in r["rows"] if not x.get("error")):
        L.append("")
        L.append("※ 채널 ID가 검색 추정인 채널. channels.json 에서 확인 후 verified 로 바꿔 주세요.")
    L += ["", "## 2. 지난 24시간 조회 증가 상위", ""]
    if not r["gainers"]:
        L.append("전일 스냅샷이 없어 계산 불가(첫 수집).")
    else:
        L += ["| # | 채널 | 영상 | +조회 | 누적 |", "|---:|---|---|---:|---:|"]
        for i, g in enumerate(r["gainers"], 1):
            L.append(f"| {i} | {g['channel']} | [{g['title']}]({yt(g['id'])}) | {delta(g['gain'], 0)} | {fmt(g['views'])} |")
    total_recent = len(r["recent"])
    L += ["", f"## 3. 최근 7일 업로드 영상 (전체 {total_recent}개 중 조회수 상위 {min(RECENT_TOP_N, total_recent)})", ""]
    if not r["recent"]:
        L.append("최근 7일 업로드 없음.")
    else:
        L += ["| 채널 | 영상 | 길이 | 게시 | 조회 | 좋아요 | 댓글 |", "|---|---|---:|---:|---:|---:|---:|"]
        for v in r["recent"][:RECENT_TOP_N]:
            L.append(f"| {v['channel']} | [{v['title']}]({yt(v['id'])}) | {dur(v['duration'])} | {ago(v['age'])} | {fmt(v['views'])} | {fmt(v['likes'])} | {fmt(v['comments'])} |")
    L += ["", "## 4. 주의 신호", ""]
    L += [f"- {a}" for a in r["alerts"]] or ["- 없음"]
    L.append("")
    return "\n".join(L)


def to_html(r):
    """이메일용 단순 HTML. 외부 CSS 없이 인라인만."""
    import html as h
    td = 'style="padding:4px 8px;border-bottom:1px solid #ddd;white-space:nowrap"'
    tdr = td.replace('nowrap"', 'nowrap;text-align:right"')
    th = 'style="padding:4px 8px;border-bottom:2px solid #333;text-align:left"'

    def table(headers, rows_html):
        return ("<table style=\"border-collapse:collapse;font-size:13px\"><tr>" +
                "".join(f"<th {th}>{h.escape(x)}</th>" for x in headers) + "</tr>" + rows_html + "</table>")

    parts = [f"<h2>유튜브 일일 리포트 — {r['date']}</h2><p>수집 시각: {r['collected_at']}</p>"]
    if r["d1_back"] is None:
        parts.append("<p>전일 비교: 없음(첫 수집).</p>")
    body = ""
    for x in r["rows"]:
        if x.get("error"):
            body += f"<tr><td {td}>{h.escape(x['name'])}</td><td {td} colspan=9>오류: {h.escape(x['error'])}</td></tr>"
            continue
        name = h.escape(x["name"]) + ("" if x.get("verified") else " ※")
        cells = [name, fmt(x["subs"]), x["subs_d1"], x["subs_d7"], fmt(x["views"]), x["views_d1"], x["views_d7"], fmt(x["video_count"]), str(x["uploads_7d"]), ago_int(x["last_upload_days"])]
        body += "<tr>" + f"<td {td}>{cells[0]}</td>" + "".join(f"<td {tdr}>{c}</td>" for c in cells[1:]) + "</tr>"
    parts.append("<h3>1. 채널 요약</h3>" + table(["채널", "구독자", "Δ1일", "Δ7일", "총조회수", "Δ1일", "Δ7일", "영상수", "7일 업로드", "마지막 업로드"], body))
    parts.append("<h3>2. 지난 24시간 조회 증가 상위</h3>")
    if not r["gainers"]:
        parts.append("<p>전일 스냅샷이 없어 계산 불가(첫 수집).</p>")
    else:
        body = "".join(f"<tr><td {tdr}>{i}</td><td {td}>{h.escape(g['channel'])}</td><td {td}><a href=\"{yt(g['id'])}\">{h.escape(g['title'])}</a></td><td {tdr}>{delta(g['gain'], 0)}</td><td {tdr}>{fmt(g['views'])}</td></tr>"
                       for i, g in enumerate(r["gainers"], 1))
        parts.append(table(["#", "채널", "영상", "+조회", "누적"], body))
    parts.append(f"<h3>3. 최근 7일 업로드 영상 (전체 {len(r['recent'])}개 중 조회수 상위 {min(RECENT_TOP_N, len(r['recent']))})</h3>")
    if not r["recent"]:
        parts.append("<p>최근 7일 업로드 없음.</p>")
    else:
        body = "".join(f"<tr><td {td}>{h.escape(v['channel'])}</td><td {td}><a href=\"{yt(v['id'])}\">{h.escape(v['title'])}</a></td><td {tdr}>{dur(v['duration'])}</td><td {tdr}>{ago(v['age'])}</td><td {tdr}>{fmt(v['views'])}</td><td {tdr}>{fmt(v['likes'])}</td><td {tdr}>{fmt(v['comments'])}</td></tr>"
                       for v in r["recent"][:RECENT_TOP_N])
        parts.append(table(["채널", "영상", "길이", "게시", "조회", "좋아요", "댓글"], body))
    parts.append("<h3>4. 주의 신호</h3><ul>" + "".join(f"<li>{h.escape(a)}</li>" for a in r["alerts"]) + ("" if r["alerts"] else "<li>없음</li>") + "</ul>")
    return "<html><body style=\"font-family:sans-serif\">" + "".join(parts) + "</body></html>"


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else dt.datetime.now(KST).strftime("%Y-%m-%d")
    r = build(date)
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / f"{date}.md").write_text(to_markdown(r), encoding="utf-8")
    (out / f"{date}.html").write_text(to_html(r), encoding="utf-8")
    print(f"리포트: reports/{date}.md, reports/{date}.html  (경고 {len(r['alerts'])}건)")


if __name__ == "__main__":
    main()
