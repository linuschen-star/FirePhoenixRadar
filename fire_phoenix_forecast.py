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
    if hours <= 2:
        return 75, "★★★★☆"
    if hours <= 4:
        return 55, "★★★☆☆"
    if hours <= 8:
        return 35, "★★☆☆☆"

    return 20, "★☆☆☆☆"


def label(score, rain, low, visibility):
    bad_weather = rain >= 70 or low >= 70 or visibility < 8
    very_bad_weather = rain >= 75 and low >= 70

    if score >= 90:
        if bad_weather:
            return "🔥🔥🔥 神級潛勢，但雨雲變數極高"
        return "🔥🔥🔥 神級火鳳"

    if score >= 75:
        if bad_weather:
            return "🔥🔥 大火鳳潛勢，但現場變數高"
        return "🔥🔥 大火鳳警報"

    if score >= 60:
        if very_bad_weather:
            return "🌦 有破口機會，但雨雲風險高"
        return "🔥 有機會"

    if score >= 40:
        return "🌤 可能有晚霞，順路可看"

    return "☁️ 機率低，回家吃飯"


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
    hour
):
    score = 0
    cloud_material = high + mid

    # 高空雲：火鳳翅膀
    if 30 <= high <= 80:
        score += 35
    elif 15 <= high <= 90:
        score += 20
    elif high > 90:
        score += 10

    # 中層雲：火燒層次
    if 20 <= mid <= 60:
        score += 25
    elif 10 <= mid <= 80:
        score += 15

    # 低層雲：太厚會蓋死光線
    if low <= 20:
        score += 20
    elif low <= 40:
        score += 10
    elif low <= 60:
        score += 5
    elif low <= 75:
        score -= 10
    else:
        score -= 25

    # 能見度：太低代表霧、雨、濕氣太重
    if visibility >= 20:
        score += 10
    elif visibility >= 10:
        score += 5
    elif visibility < 5:
        score -= 15
    elif visibility < 8:
        score -= 8

    # 陣風：可能代表颱風前緣或天氣變化
    if gust >= 30 and cloud_material >= 35:
        score += 10
    elif gust >= 22 and cloud_material >= 35:
        score += 5

    # 降雨機率：適量可帶來戲劇性，太高會蓋死
    if 20 <= rain <= 55 and cloud_material >= 35:
        score += 10
    elif 56 <= rain <= 70 and cloud_material >= 35:
        score += 5
    elif rain > 75:
        score -= 12

    # 時段加權
    if cloud_material >= 25:
        if hour < 17:
            score += 5
        else:
            score += 10

    # 缺火鳳材料封頂
    if cloud_material < 15:
        score = min(score, 30)
    elif cloud_material < 25:
        score = min(score, 45)

    # 低雲 + 雨雲雙重封頂
    if low >= 80 and rain >= 70:
        score = min(score, 35)
    elif low >= 70 and rain >= 70:
        score = min(score, 48)
    elif low >= 65 and rain >= 75:
        score = min(score, 50)

    # 能見度過低封頂
    if visibility < 5:
        score = min(score, 45)

    return clamp(score)


def fetch_weather():
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

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def main():
    data = fetch_weather()

    sunset = datetime.fromisoformat(
        data["daily"]["sunset"][0]
    ).replace(tzinfo=None)

    now = datetime.now(
        ZoneInfo("Asia/Taipei")
    ).replace(tzinfo=None)

    start_window = sunset.replace(hour=15, minute=0)
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
                high=high,
                mid=mid,
                low=low,
                visibility=visibility,
                wind=wind,
                gust=gust,
                rain=rain,
                hour=dt.hour
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

    if not results:
        print("找不到觀察窗內的氣象資料")
        return

    best = max(results, key=lambda x: x["score"])

    if start_window <= now <= end_window:
        current = min(
            results,
            key=lambda x: abs((x["time"] - now).total_seconds())
        )
        current_text = f"{current['score']}%"
    else:
        current_text = "尚未進入觀察窗"

    conf, stars = confidence(now, best["time"])

    print("====== 火鳳雷達 v0.6 ======")
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

    print(f"最佳預測時間：{best['time'].strftime('%H:%M')}")
    print(f"火鳳類型：{best['mode']}")
    print(
        label(
            score=best["score"],
            rain=best["rain"],
            low=best["low"],
            visibility=best["visibility"]
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


if __name__ == "__main__":
    main()
