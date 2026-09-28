#!/usr/bin/env python3
"""유튜브 Data API v3 로 채널·최근 영상 통계를 수집해 data/snapshots/YYYY-MM-DD.json 에 저장한다.

쿼터: 채널 1회(1u) + 채널별 업로드 목록 1회(1u) + 영상 통계 50개당 1회(1u) → 13채널 기준 약 20u/일.
API 키는 환경변수 YOUTUBE_API_KEY 에서만 읽는다. 파일·로그에 키를 남기지 않는다.
"""
import json, os, sys, datetime as dt, re
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
API = "https://www.googleapis.com/youtube/v3"
RECENT_PER_CHANNEL = 25     # 채널당 최근 업로드 몇 개까지 볼지
KST = dt.timezone(dt.timedelta(hours=9))


def api(endpoint, **params):
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        sys.exit("YOUTUBE_API_KEY 환경변수가 없습니다.")
    r = requests.get(f"{API}/{endpoint}", params={**params, "key": key}, timeout=30)
    if r.status_code != 200:
        # 오류 본문에 키가 섞이지 않도록 status 와 reason 만 남긴다
        try:
            reason = r.json()["error"]["errors"][0].get("reason")
        except Exception:
            reason = r.text[:200]
        sys.exit(f"API 오류 {endpoint}: HTTP {r.status_code} {reason}")
    return r.json()


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def iso_duration_to_sec(s):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return None
    h, mi, se = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + se


def collect(channels):
    now = dt.datetime.now(KST)
    ids = [c["id"] for c in channels]
    out = {"collected_at": now.isoformat(timespec="seconds"), "date": now.strftime("%Y-%m-%d"), "channels": {}}

    # 1) 채널 통계 (50개까지 한 번에)
    chan_items = {}
    for batch in chunks(ids, 50):
        res = api("channels", part="snippet,statistics,contentDetails", id=",".join(batch), maxResults=50)
        for it in res.get("items", []):
            chan_items[it["id"]] = it

    # 2) 채널별 최근 업로드 목록
    video_ids_by_channel = {}
    for c in channels:
        it = chan_items.get(c["id"])
        if not it:
            out["channels"][c["id"]] = {"name": c["name"], "error": "채널 조회 실패(ID 확인 필요)"}
            continue
        uploads = it["contentDetails"]["relatedPlaylists"]["uploads"]
        pl = api("playlistItems", part="contentDetails", playlistId=uploads, maxResults=RECENT_PER_CHANNEL)
        video_ids_by_channel[c["id"]] = [p["contentDetails"]["videoId"] for p in pl.get("items", [])]

    # 3) 영상 통계 (50개씩)
    all_vids = [v for vs in video_ids_by_channel.values() for v in vs]
    vid_items = {}
    for batch in chunks(all_vids, 50):
        res = api("videos", part="snippet,statistics,contentDetails", id=",".join(batch), maxResults=50)
        for it in res.get("items", []):
            vid_items[it["id"]] = it

    for c in channels:
        it = chan_items.get(c["id"])
        if not it:
            continue
        st = it["statistics"]
        videos = []
        for vid in video_ids_by_channel.get(c["id"], []):
            v = vid_items.get(vid)
            if not v:
                continue
            vs = v["statistics"]
            videos.append({
                "id": vid,
                "title": v["snippet"]["title"],
                "published_at": v["snippet"]["publishedAt"],
                "duration_sec": iso_duration_to_sec(v["contentDetails"].get("duration")),
                "views": int(vs.get("viewCount", 0)),
                "likes": int(vs.get("likeCount", 0)) if "likeCount" in vs else None,
                "comments": int(vs.get("commentCount", 0)) if "commentCount" in vs else None,
            })
        out["channels"][c["id"]] = {
            "name": c["name"],
            "genre": c.get("genre", ""),
            "verified": c.get("verified", False),
            "title": it["snippet"]["title"],
            "handle": it["snippet"].get("customUrl"),
            "subscribers": int(st.get("subscriberCount", 0)),
            "hidden_subscribers": st.get("hiddenSubscriberCount", False),
            "views": int(st.get("viewCount", 0)),
            "video_count": int(st.get("videoCount", 0)),
            "videos": videos,
        }
    return out


def main():
    cfg = json.loads((ROOT / "channels.json").read_text(encoding="utf-8"))
    channels = [c for c in cfg["channels"] if c.get("enabled", True)]
    snap = collect(channels)
    path = ROOT / "data" / "snapshots" / f"{snap['date']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    # 장기 추이용 CSV (한 줄 = 채널·날짜)
    hist = ROOT / "data" / "history.csv"
    new = not hist.exists()
    with hist.open("a", encoding="utf-8") as f:
        if new:
            f.write("date,channel,subscribers,views,video_count\n")
        for ch in snap["channels"].values():
            if "error" in ch:
                continue
            f.write(f"{snap['date']},{ch['name']},{ch['subscribers']},{ch['views']},{ch['video_count']}\n")
    print(f"저장: {path.relative_to(ROOT)}  채널 {len(snap['channels'])}개, 영상 {sum(len(c.get('videos', [])) for c in snap['channels'].values())}개")


if __name__ == "__main__":
    main()
