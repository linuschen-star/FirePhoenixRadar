import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

LAT = 23.783761
LON = 121.437198
TZ = "Asia/Taipei"


def clamp(x, low=0, high=100):
    return max(low, min(high, x))


def confidence(now, target):
    hours = abs((target - now).total_seconds()) / 3600

    if hours <= 1:
        return 90, "★★★★★"
    elif hours <= 2:
        return 75, "★★★★☆"
    elif hours <= 4:
        return 55, "★★★☆☆"
    elif hours <= 8:
        return 35, "★★☆☆☆"
    else:
        return 20, "★☆☆☆☆"


def label(score, rain, visibility):

    risky = False

    if rain >= 60:
        risky = True

    if visibility < 8:
        risky = True

    if score >= 90:
        if risky:
            return "🔥🔥🔥 神級潛勢，但雨霧變數高"
        return "🔥🔥🔥 神級火鳳"

    if score >= 75:
        return "🔥🔥 大火鳳警報"

    if score >= 60:
        return "🔥 有機會"

    if score >= 40:
        return "🌤 可能有晚霞"

    return "☁️ 回家吃飯"


def mode_name(hour):

    if hour < 17:
        return "午後火鳳"

    return "夕照火鳳"


def score_fire_phoenix(
        high,
        mid,
        low,
        visibility,
        wind,
        gust,
        rain,
        hour):

    score = 0

    cloud_material = high + mid

    # 高空雲

    if 30 <= high <= 80:
        score += 35
    elif 15 <= high <= 90:
        score += 20

    # 中層雲

    if 20 <= mid <= 60:
        score += 25
    elif 10 <= mid <= 80:
        score += 15

    # 低層雲

    if low <= 20:
        score += 20
    elif low <= 40:
        score += 10
    elif low <= 60:
        score += 5
    else:
        score -= 15

    # 能見度

    if visibility >= 20:
        score += 10
    elif visibility >= 10:
        score += 5

    # 颱風前緣

    if gust >= 30:
        score += 10

    if 20 <= rain <= 80:
        score += 10

    # 時段

    if hour < 17:
        score += 5
    else:
        score += 10

    # 缺材料封頂

    if cloud_material < 15:
        score = min(score, 30)

    elif cloud_material < 25:
        score = min(score, 45)

    return clamp(score)


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
        "precipitation_probability"
    ])
}

data = requests.get(url, params=params).json()

sunset = datetime.fromisoformat(
    data["daily"]["sunset"][0]
).replace(tzinfo=None)

now = datetime.now(
    ZoneInfo("Asia/Taipei")
).replace(tzinfo=None)

start_window = sunset.replace(
    hour=15,
    minute=0
)

end_window = sunset + timedelta(minutes=30)

results = []

for i, t in enumerate(data["hourly"]["time"]):

    dt = datetime.fromisoformat(t).replace(tzinfo=None)

    if start_window <= dt <= end_window:

        high = data["hourly"]["cloud_cover_high"][i]
        mid = data["hourly"]["cloud_cover_mid"][i]
        low = data["hourly"]["cloud_cover_low"][i]

        visibility = data["hourly"]["visibility"][i] / 1000

        wind = data["hourly"]["wind_speed_10m"][i]
        gust = data["hourly"]["wind_gusts_10m"][i]

        rain = data["hourly"]["precipitation_probability"][i]

        score = score_fire_phoenix(
            high,
            mid,
            low,
            visibility,
            wind,
            gust,
            rain,
            dt.hour
        )

        results.append({
            "time": dt,
            "score": score,
            "mode": mode_name(dt.hour),
            "high": high,
            "mid": mid,
            "low": low,
            "visibility": visibility,
            "wind": wind,
            "gust": gust,
            "rain": rain
        })

best = max(results, key=lambda x: x["score"])

if start_window <= now <= end_window:
    current = min(
        results,
        key=lambda x: abs(
            (x["time"] - now).total_seconds()
        )
    )
    current_text = f"{current['score']}%"
else:
    current_text = "尚未進入觀察窗"

conf, stars = confidence(now, best["time"])

print("====== 火鳳雷達 v0.5 ======")
print("地點：鳳林山觀景點")
print(f"目前時間：{now.strftime('%H:%M')}")
print(f"日落時間：{sunset.strftime('%H:%M')}")
print(
    f"觀察窗："
    f"{start_window.strftime('%H:%M')} – "
    f"{end_window.strftime('%H:%M')}"
)

print()

print(f"今日火鳳潛勢：{best['score']}%")
print(f"即時火鳳指數：{current_text}")
print(f"可信度：{conf}% {stars}")

print()

print(
    f"最佳預測時間："
    f"{best['time'].strftime('%H:%M')}"
)

print(f"火鳳類型：{best['mode']}")

print(
    label(
        best["score"],
        best["rain"],
        best["visibility"]
    )
)

print()

print("最佳時段判斷資料：")
print(f"高空雲：{best['high']}%")
print(f"中層雲：{best['mid']}%")
print(f"低層雲：{best['low']}%")
print(f"能見度：{best['visibility']:.1f} km")
print(f"風速：{best['wind']} km/h")
print(f"陣風：{best['gust']} km/h")
print(f"降雨機率：{best['rain']}%")

print()

print("逐時預測：")

for r in results:

    print(
        f"{r['time'].strftime('%H:%M')} | "
        f"{r['score']:3}% | "
        f"{r['mode']} | "
        f"高 {r['high']:3}% "
        f"中 {r['mid']:3}% "
        f"低 {r['low']:3}% | "
        f"風 {r['wind']:4.1f} "
        f"陣 {r['gust']:4.1f} | "
        f"雨 {r['rain']:3}% | "
        f"能見度 {r['visibility']:.1f}km"
    )
