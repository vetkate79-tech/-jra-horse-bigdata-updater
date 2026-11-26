"""Resolve NAR requests to official card URLs; availability is not implied."""
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

TRACKS = {"門別":36,"盛岡":10,"水沢":11,"浦和":18,"船橋":19,"大井":20,"川崎":21,"金沢":22,"笠松":23,"名古屋":24,"園田":27,"姫路":28,"高知":31,"佐賀":32,"帯広":3}
def resolve(request, day=None):
    match = re.fullmatch(r"\s*([一-龯]+)\s*([0-9]{1,2})\s*[RrＲ]?\s*", request)
    if not match:
        raise ValueError("expected venue and race number")
    track, number = match.group(1), int(match.group(2))
    if track not in TRACKS or not 1 <= number <= 12:
        raise ValueError("unknown venue or race number")
    day = day or datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError("noncanonical date")
    query = urlencode({"k_raceDate":day.replace("-","/"),"k_raceNo":number,"k_babaCode":TRACKS[track]})
    return {"track":track,"date":day,"race_no":number,
            "model":"banei" if track=="帯広" else "nar_flat",
            "card_url":"https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/DebaTable?"+query,
            "status":"UNVERIFIED_REQUEST"}
