# fire_phoenix_forecast.py
# 火鳳雷達 v0.4
# pip install requests

import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

LAT = 23.783761
LON = 121.437198
TZ = "Asia/Taipei"

def clamp(x, low=0, high=100):
    return max(low, min(high, x))

def label(score):
    if score >= 90:
        return "🔥🔥🔥 神級火鳳，立刻上山"
    if score >= 75:
        return "🔥🔥 大火鳳警報，值得等"
    if score >= 60:
        return "🔥 有機會，建議上去看"
    if score >= 40:
        return "🌤 可能有晚霞，順路可看"
    return "☁️ 機率低，回家吃飯"

def confidence(now, best_time):
    hours = abs((best_time - now).total_seconds()) / 3600
    if hours <= 1:
        return 90, "★★★★★"
    if hours <= 2:
        return 75, "★★★★☆"
    if hours <= 4:
        return 55, "★★★☆☆"
    if hours <= 8:
        return 35, "★★☆☆☆"
    return 20, "★☆☆☆☆"

def mode_name(dt, sunset_time):
    if dt.hour < 17:
        return "午後火鳳"
    if dt <= sunset_time + timedelta(minutes=30):
        return "夕照火鳳"
    return "餘暉觀察"

def score_fire_phoenix(high, mid, low, visibility_km, wind_speed, wind_gusts, rain_prob, dt, sunset_time):
    score = 0
    cloud_material = high + mid

    if cloud_material < 15:
        base_cap = 35
    elif cloud_material < 30:
        base_cap = 55
    else:
        base_cap = 100

    if 35 <= high <= 85:
        score += 38
    elif 20 <= high < 35 or 85 < high <= 95:
        score += 24
    elif 8 <= high < 20:
        score += 10

    if 20 <= mid <= 75:
        score += 24
    elif 8 <= mid < 20 or 75 < mid <= 90:
        score += 12

    if low <= 20:
        score += 18
    elif low <= 40:
        score += 12
    elif low <= 65:
        score += 5
    else:
        score -= 18

    if visibility_km >= 25:
        score += 10
    elif visibility_km >= 15:
        score += 7
    elif visibility_km >= 8:
        score += 3

    storm_edge_bonus = 0
    if wind_speed >= 18 and cloud_material >= 35 and low <= 70:
        storm_edge_bonus += 10
    if wind_gusts >= 30 and cloud_material >= 35 and low <= 75:
        storm_edge_bonus += 8
    if 20 <= rain_prob <= 70 and cloud_material >= 35 and low <= 75:
        storm_edge_bonus += 7
    storm_edge_bonus = min(storm_edge_bonus, 20)
    score += storm_edge_bonus

    if cloud_material >= 25:
        if 15 <= dt.hour < 17:
            score += 8
        elif 17 <= dt.hour <= sunset_time.hour:
            score += 10
        elif sunset_time <= dt <= sunset_time + timedelta(minutes=30):
            score += 8

    if cloud_material < 15:
        score = min(score, 30)
    elif cloud_material < 25:
        score = min(score, 45)

    return clamp(min(score, base_cap + min(storm_edge_bonus, 15)))

def parse_time(t):
    return datetime.fromisoformat(t)

def main():
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": LAT,
        "longitude": LON,
        "timezone": TZ,
        "forecast_days": 1,
        "daily": "sunset",
        "hourly": ",".join([
            "cloud_cover_low",
            "cloud_cover_mid",
            "cloud_cover_high",
            "visibility",
            "wind_speed_10m",
            "wind_gusts_10m",
            "precipitation_probability",
        ]),
    }

    data = requests.get(url, params=params, timeout=15).json()
    now = datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None)

    sunset_time = parse_time(data["daily"]["sunset"][0])
    start_window = sunset_time.replace(hour=15, minute=0)
    end_window = sunset_time + timedelta(minutes=30)

    hourly = data["hourly"]
    results = []

    for i, t in enumerate(hourly["time"]):
        dt = parse_time(t)
        if start_window <= dt <= end_window:
            high = hourly["cloud_cover_high"][i]
            mid = hourly["cloud_cover_mid"][i]
            low = hourly["cloud_cover_low"][i]
            visibility_km = hourly["visibility"][i] / 1000
            wind_speed = hourly["wind_speed_10m"][i]
            wind_gusts = hourly["wind_gusts_10m"][i]
            rain_prob = hourly["precipitation_probability"][i]

            s = score_fire_phoenix(high, mid, low, visibility_km, wind_speed, wind_gusts, rain_prob, dt, sunset_time)

            results.append({
                "time": dt,
                "mode": mode_name(dt, sunset_time),
                "score": s,
                "high": high,
                "mid": mid,
                "low": low,
                "visibility_km": round(visibility_km, 1),
                "wind_speed": wind_speed,
                "wind_gusts": wind_gusts,
                "rain_prob": rain_prob,
            })

    best = max(results, key=lambda x: x["score"])

    # 即時指數：找現在最近的小時資料
    current = min(results, key=lambda x: abs((x["time"] - now).total_seconds()))
    conf_score, conf_stars = confidence(now, best["time"])

    print("====== 火鳳雷達 v0.4 ======")
    print("地點：鳳林山觀景點")
    print(f"目前時間：{now.strftime('%H:%M')}")
    print(f"日落時間：{sunset_time.strftime('%H:%M')}")
    print(f"觀察窗：{start_window.strftime('%H:%M')} – {end_window.strftime('%H:%M')}")
    print()
    print(f"今日火鳳潛勢：{best['score']}%")
    print(f"即時火鳳指數：{current['score']}%")
    print(f"可信度：{conf_score}% {conf_stars}")
    print()
    print(f"最佳預測時間：{best['time'].strftime('%H:%M')}")
    print(f"火鳳類型：{best['mode']}")
    print(label(best["score"]))
    print()
    print("最佳時段判斷資料：")
    print(f"高空雲：{best['high']}%")
    print(f"中層雲：{best['mid']}%")
    print(f"低層雲：{best['low']}%")
    print(f"能見度：{best['visibility_km']} km")
    print(f"風速：{best['wind_speed']} km/h")
    print(f"陣風：{best['wind_gusts']} km/h")
    print(f"降雨機率：{best['rain_prob']}%")
    print()
    print("逐時預測：")
    for r in results:
        print(
            f"{r['time'].strftime('%H:%M')} | "
            f"{r['score']:>3}% | {r['mode']} | "
            f"高 {r['high']:>3}% 中 {r['mid']:>3}% 低 {r['low']:>3}% | "
            f"風 {r['wind_speed']:>4} 陣 {r['wind_gusts']:>4} | "
            f"雨 {r['rain_prob']:>3}% | "
            f"能見度 {r['visibility_km']}km"
        )

if __name__ == "__main__":
    main()
