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


def estimate_moon_phase(date):
    known_new_moon = datetime(2000, 1, 6, 18, 14)
    lunar_cycle = 29.53058867
    days = (date - known_new_moon).total_seconds() / 86400
    return (days % lunar_cycle) / lunar_cycle


def moon_label(phase):
    if phase < 0.08 or phase > 0.92:
        return "新月附近，適合銀河"
    if 0.42 <= phase <= 0.58:
        return "滿月附近，星空受月光影響"
    if phase < 0.25:
        return "眉月，星空條件佳"
    if phase < 0.42:
        return "上弦月附近，月光略影響"
    if phase < 0.75:
        return "下半月，月光仍有影響"
    return "殘月，後半夜較適合星空"


def fire_label(score, rain, low, visibility, sunlight):
    if sunlight <= 15:
        return "🌧 雨幕遮光，火鳳機率低"

    if score >= 75:
        if rain >= 70 or low >= 70 or visibility < 8 or sunlight < 40:
            return "🔥🔥 大火鳳潛勢，但現場變數高"
        return "🔥🔥 大火鳳警報"

    if score >= 60:
        if rain >= 65 or low >= 65 or visibility < 8 or sunlight < 35:
            return "🌦 有破口機會，但雨雲風險高"
        return "🔥 有機會"

    if score >= 40:
        return "🌤 可能有晚霞，順路可看"

    return "☁️ 機率低，回家吃飯"


def star_label(score):
    if score >= 85:
        return "🌌🌌🌌 星空爆棚，適合銀河／星軌"
    if score >= 70:
        return "🌌🌌 星空條件佳，值得上山"
    if score >= 55:
        return "🌌 有機會，適合測拍"
    if score >= 40:
        return "🌙 普通，可順路看看"
    return "☁️ 星空條件差，回家睡覺"


def fire_mode_name(hour):
    if hour < 17:
        return "午後火鳳"
    return "夕照火鳳"


def sunlight_penetration_score(shortwave, direct, rain, low, mid, visibility):
    """
    火鳳最關鍵不是只有雲材，而是夕陽有沒有打進來。

    shortwave_radiation:
        地表短波輻射，代表整體日照還剩多少。
    direct_radiation:
        直射輻射，代表太陽是否仍直接穿透雲層。

    傍晚如果 direct_radiation 接近 0，加上降雨機率高，
    就算高雲漂亮，也通常只是灰雲，不會燒。
    """

    score = 0

    if shortwave >= 300:
        score += 35
    elif shortwave >= 180:
        score += 28
    elif shortwave >= 100:
        score += 20
    elif shortwave >= 40:
        score += 10
    elif shortwave >= 10:
        score += 4
    else:
        score -= 20

    if direct >= 180:
        score += 40
    elif direct >= 90:
        score += 30
    elif direct >= 30:
        score += 15
    elif direct >= 5:
        score += 5
    else:
        score -= 35

    if rain >= 90:
        score -= 35
    elif rain >= 75:
        score -= 25
    elif rain >= 60:
        score -= 12
    elif rain <= 30:
        score += 5

    if low >= 80:
        score -= 30
    elif low >= 60:
        score -= 18
    elif low >= 40:
        score -= 8
    elif low <= 25:
        score += 10

    if mid >= 90:
        score -= 12
    elif mid >= 75:
        score -= 6

    if visibility >= 15:
        score += 10
    elif visibility >= 8:
        score += 4
    elif visibility < 5:
        score -= 18

    # 關鍵防呆：正在下雨 + 沒直射光，直接視為無夕陽穿透。
    if rain >= 85 and direct < 10:
        score = min(score, 12)

    if rain >= 85 and shortwave < 30:
        score = min(score, 10)

    if visibility < 5 and direct < 10:
        score = min(score, 15)

    return clamp(score)


def fire_failure_reason(best):
    reasons = []

    if best["sunlight"] <= 15:
        reasons.append("夕陽光照不足")
    elif best["sunlight"] <= 35:
        reasons.append("夕陽穿透偏弱")

    if best["direct_radiation"] < 10:
        reasons.append("直射光幾乎消失")

    if best["shortwave_radiation"] < 30:
        reasons.append("地表短波輻射過低")

    if best["rain"] >= 85:
        reasons.append("降雨機率極高")
    elif best["rain"] >= 65:
        reasons.append("降雨機率偏高")

    if best["visibility"] < 5:
        reasons.append("能見度差")
    elif best["visibility"] < 8:
        reasons.append("能見度偏差")

    if best["low"] >= 70:
        reasons.append("低層雲阻擋地平線")
    elif best["low"] >= 45:
        reasons.append("低層雲偏多")

    if best["high"] < 20 and best["mid"] < 20:
        reasons.append("缺少可被夕陽點燃的雲材")

    if not reasons:
        return "主要限制：雲層與夕陽角度變化"

    return "主要敗因：" + "、".join(reasons)


def score_fire_phoenix(high, mid, low, visibility, wind, gust, rain, hour, shortwave, direct):
    cloud_score = 0
    cloud_material = high + mid

    if 30 <= high <= 80:
        cloud_score += 35
    elif 15 <= high <= 90:
        cloud_score += 20
    elif high > 90:
        cloud_score += 10

    if 20 <= mid <= 60:
        cloud_score += 25
    elif 10 <= mid <= 80:
        cloud_score += 15
    elif mid > 80:
        cloud_score += 8

    if low <= 20:
        cloud_score += 20
    elif low <= 40:
        cloud_score += 10
    elif low <= 60:
        cloud_score += 5
    elif low <= 75:
        cloud_score -= 10
    else:
        cloud_score -= 25

    if visibility >= 20:
        cloud_score += 10
    elif visibility >= 10:
        cloud_score += 5
    elif visibility < 5:
        cloud_score -= 15
    elif visibility < 8:
        cloud_score -= 8

    if gust >= 30 and cloud_material >= 35:
        cloud_score += 10
    elif gust >= 22 and cloud_material >= 35:
        cloud_score += 5

    # 小雨或遠方陣雨可能製造破口與反射，但高雨率會壓低。
    if 20 <= rain <= 55 and cloud_material >= 35:
        cloud_score += 8
    elif 56 <= rain <= 70 and cloud_material >= 35:
        cloud_score += 2
    elif rain > 85:
        cloud_score -= 15
    elif rain > 75:
        cloud_score -= 10

    if cloud_material >= 25:
        if hour < 17:
            cloud_score += 5
        else:
            cloud_score += 10

    if cloud_material < 15:
        cloud_score = min(cloud_score, 30)
    elif cloud_material < 25:
        cloud_score = min(cloud_score, 45)

    if low >= 80 and rain >= 70:
        cloud_score = min(cloud_score, 30)
    elif low >= 70 and rain >= 70:
        cloud_score = min(cloud_score, 42)
    elif low >= 65 and rain >= 75:
        cloud_score = min(cloud_score, 45)

    if visibility < 5:
        cloud_score = min(cloud_score, 40)

    cloud_score = clamp(cloud_score)

    sunlight = sunlight_penetration_score(
        shortwave=shortwave,
        direct=direct,
        rain=rain,
        low=low,
        mid=mid,
        visibility=visibility
    )

    # v0.7.3 核心：火鳳 = 雲材 * 夕陽穿透
    # 有雲材但無陽光，分數必須被壓低。
    final_score = round((cloud_score * 0.65) + (sunlight * 0.35))

    if sunlight <= 10:
        final_score = min(final_score, 20)
    elif sunlight <= 20:
        final_score = min(final_score, 32)
    elif sunlight <= 35 and rain >= 75:
        final_score = min(final_score, 45)

    if direct < 5 and rain >= 80:
        final_score = min(final_score, 18)

    if shortwave < 20 and rain >= 80:
        final_score = min(final_score, 16)

    return clamp(final_score), cloud_score, sunlight


def score_star_sky(high, mid, low, visibility, rain, moon_phase):
    score = 0
    total_cloud = high + mid + low

    if low <= 10:
        score += 30
    elif low <= 25:
        score += 20
    elif low <= 45:
        score += 8
    else:
        score -= 25

    if mid <= 15:
        score += 20
    elif mid <= 35:
        score += 10
    else:
        score -= 15

    if high <= 20:
        score += 20
    elif high <= 45:
        score += 8
    else:
        score -= 10

    if visibility >= 25:
        score += 20
    elif visibility >= 15:
        score += 12
    elif visibility >= 8:
        score += 5
    else:
        score -= 20

    if rain <= 10:
        score += 10
    elif rain <= 30:
        score += 3
    else:
        score -= 25

    if 0.42 <= moon_phase <= 0.58:
        score -= 25
    elif 0.30 <= moon_phase <= 0.70:
        score -= 15

    if total_cloud >= 180:
        score = min(score, 30)
    elif total_cloud >= 130:
        score = min(score, 45)

    if visibility < 3:
        score = min(score, 20)

    if visibility < 1:
        score = min(score, 16)

    return clamp(score)


def star_failure_reason(best):
    reasons = []

    if best["visibility"] < 3:
        reasons.append("能見度過低")
    elif best["visibility"] < 8:
        reasons.append("能見度偏差")

    if best["high"] >= 60:
        reasons.append("高空雲過多")
    elif best["high"] >= 40:
        reasons.append("高空雲偏多")

    if best["mid"] >= 40:
        reasons.append("中層雲偏多")

    if best["low"] >= 45:
        reasons.append("低層雲偏多")

    if best["rain"] >= 30:
        reasons.append("降雨機率偏高")

    if not reasons:
        return "主要限制：月光或雲層變化"

    return "主要敗因：" + "、".join(reasons)


def fetch_weather():
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": LAT,
        "longitude": LON,
        "timezone": TZ,
        "forecast_days": 2,
        "daily": ",".join([
            "sunset",
            "sunrise"
        ]),
        "hourly": ",".join([
            "cloud_cover_low",
            "cloud_cover_mid",
            "cloud_cover_high",
            "visibility",
            "wind_speed_10m",
            "wind_gusts_10m",
            "precipitation_probability",
            "shortwave_radiation",
            "direct_radiation"
        ])
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def build_fire_results(data, sunset):
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
            shortwave = data["hourly"]["shortwave_radiation"][i]
            direct = data["hourly"]["direct_radiation"][i]

            score, cloud_score, sunlight = score_fire_phoenix(
                high=high,
                mid=mid,
                low=low,
                visibility=visibility,
                wind=wind,
                gust=gust,
                rain=rain,
                hour=dt.hour,
                shortwave=shortwave,
                direct=direct
            )

            results.append({
                "time": dt,
                "score": score,
                "cloud_score": cloud_score,
                "sunlight": sunlight,
                "mode": fire_mode_name(dt.hour),
                "high": high,
                "mid": mid,
                "low": low,
                "visibility": visibility,
                "wind": wind,
                "gust": gust,
                "rain": rain,
                "shortwave_radiation": shortwave,
                "direct_radiation": direct
            })

    return results, start_window, end_window


def build_star_results(data, sunset, next_sunrise, moon_phase):
    start_window = sunset + timedelta(hours=1)
    end_window = next_sunrise - timedelta(hours=1)
    results = []

    for i, t in enumerate(data["hourly"]["time"]):
        dt = datetime.fromisoformat(t).replace(tzinfo=None)

        if start_window <= dt <= end_window:
            high = data["hourly"]["cloud_cover_high"][i]
            mid = data["hourly"]["cloud_cover_mid"][i]
            low = data["hourly"]["cloud_cover_low"][i]
            visibility = data["hourly"]["visibility"][i] / 1000
            rain = data["hourly"]["precipitation_probability"][i]

            score = score_star_sky(
                high=high,
                mid=mid,
                low=low,
                visibility=visibility,
                rain=rain,
                moon_phase=moon_phase
            )

            results.append({
                "time": dt,
                "score": score,
                "high": high,
                "mid": mid,
                "low": low,
                "visibility": visibility,
                "rain": rain
            })

    return results, start_window, end_window


def print_fire_report(now, sunset, fire_results, start_window, end_window):
    best = max(fire_results, key=lambda x: x["score"])

    if start_window <= now <= end_window:
        current = min(
            fire_results,
            key=lambda x: abs((x["time"] - now).total_seconds())
        )
        current_text = f"{current['score']}%"
    else:
        current_text = "尚未進入觀察窗"

    conf, stars = confidence(now, best["time"])

    print("====== 火鳳雷達 v0.7.3 ======")
    print("地點：鳳林山觀景點")
    print(f"目前時間：{now.strftime('%H:%M')}")
    print(f"日落時間：{sunset.strftime('%H:%M')}")
    print(f"火鳳觀察窗：{start_window.strftime('%H:%M')} – {end_window.strftime('%H:%M')}")
    print()
    print(f"今日火鳳潛勢：{best['score']}%")
    print(f"雲材分數：{best['cloud_score']}%")
    print(f"光照穿透：{best['sunlight']}%")
    print(f"即時火鳳指數：{current_text}")
    print(f"可信度：{conf}% {stars}")
    print()
    print(f"最佳預測時間：{best['time'].strftime('%H:%M')}")
    print(f"火鳳類型：{best['mode']}")
    print(
        fire_label(
            score=best["score"],
            rain=best["rain"],
            low=best["low"],
            visibility=best["visibility"],
            sunlight=best["sunlight"]
        )
    )
    print(fire_failure_reason(best))
    print()
    print("最佳火鳳時段判斷資料：")
    print(f"高空雲：{best['high']}%")
    print(f"中層雲：{best['mid']}%")
    print(f"低層雲：{best['low']}%")
    print(f"能見度：{best['visibility']:.1f} km")
    print(f"風速：{best['wind']} km/h")
    print(f"陣風：{best['gust']} km/h")
    print(f"降雨機率：{best['rain']}%")
    print(f"短波輻射：{best['shortwave_radiation']} W/m²")
    print(f"直射輻射：{best['direct_radiation']} W/m²")
    print()
    print("火鳳逐時預測：")

    for r in fire_results:
        print(
            f"{r['time'].strftime('%H:%M')} | "
            f"{r['score']:3}% | "
            f"雲材 {r['cloud_score']:3}% | "
            f"光照 {r['sunlight']:3}% | "
            f"{r['mode']} | "
            f"高 {r['high']:3}% "
            f"中 {r['mid']:3}% "
            f"低 {r['low']:3}% | "
            f"風 {r['wind']:4.1f} "
            f"陣 {r['gust']:4.1f} | "
            f"雨 {r['rain']:3}% | "
            f"能見度 {r['visibility']:.1f}km | "
            f"短波 {r['shortwave_radiation']:5.1f} | "
            f"直射 {r['direct_radiation']:5.1f}"
        )


def print_star_report(now, star_results, start_window, end_window, moon_phase):
    best = max(star_results, key=lambda x: x["score"])

    if start_window <= now <= end_window:
        current = min(
            star_results,
            key=lambda x: abs((x["time"] - now).total_seconds())
        )
        current_text = f"{current['score']}%"
    else:
        current_text = "尚未進入星空觀察窗"

    conf, stars = confidence(now, best["time"])

    print()
    print("====== 星空雷達 v0.7.3 ======")
    print("地點：鳳林山觀景點")
    print(f"星空觀察窗：{start_window.strftime('%H:%M')} – {end_window.strftime('%H:%M')}")
    print()
    print(f"今晚星空潛勢：{best['score']}%")
    print(f"即時星空指數：{current_text}")
    print(f"可信度：{conf}% {stars}")
    print(f"月相指數：{moon_phase:.2f}，{moon_label(moon_phase)}")
    print(star_failure_reason(best))
    print()
    print(f"最佳預測時間：{best['time'].strftime('%H:%M')}")
    print(star_label(best["score"]))
    print()
    print("最佳星空時段判斷資料：")
    print(f"高空雲：{best['high']}%")
    print(f"中層雲：{best['mid']}%")
    print(f"低層雲：{best['low']}%")
    print(f"能見度：{best['visibility']:.1f} km")
    print(f"降雨機率：{best['rain']}%")
    print()
    print("星空逐時預測：")

    for r in star_results:
        print(
            f"{r['time'].strftime('%H:%M')} | "
            f"{r['score']:3}% | "
            f"高 {r['high']:3}% "
            f"中 {r['mid']:3}% "
            f"低 {r['low']:3}% | "
            f"雨 {r['rain']:3}% | "
            f"能見度 {r['visibility']:.1f}km"
        )


def main():
    data = fetch_weather()

    now = datetime.now(
        ZoneInfo("Asia/Taipei")
    ).replace(tzinfo=None)

    sunset = datetime.fromisoformat(
        data["daily"]["sunset"][0]
    ).replace(tzinfo=None)

    next_sunrise = datetime.fromisoformat(
        data["daily"]["sunrise"][1]
    ).replace(tzinfo=None)

    moon_phase = estimate_moon_phase(now)

    fire_results, fire_start, fire_end = build_fire_results(data, sunset)

    star_results, star_start, star_end = build_star_results(
        data=data,
        sunset=sunset,
        next_sunrise=next_sunrise,
        moon_phase=moon_phase
    )

    if fire_results:
        print_fire_report(
            now=now,
            sunset=sunset,
            fire_results=fire_results,
            start_window=fire_start,
            end_window=fire_end
        )

    if star_results:
        print_star_report(
            now=now,
            star_results=star_results,
            start_window=star_start,
            end_window=star_end,
            moon_phase=moon_phase
        )


if __name__ == "__main__":
    main()
