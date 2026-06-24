import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import astropy.units as u
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation, AltAz

LAT = 23.783761
LON = 121.437198
ALT_M = 250
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


def fire_label(score, rain, low, visibility):
    bad_weather = rain >= 70 or low >= 70 or visibility < 8
    very_bad_weather = rain >= 75 and low >= 70

    if score >= 90:
        return "🔥🔥🔥 神級潛勢，但雨雲變數極高" if bad_weather else "🔥🔥🔥 神級火鳳"
    if score >= 75:
        return "🔥🔥 大火鳳潛勢，但現場變數高" if bad_weather else "🔥🔥 大火鳳警報"
    if score >= 60:
        return "🌦 有破口機會，但雨雲風險高" if very_bad_weather else "🔥 有機會"
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
    return "午後火鳳" if hour < 17 else "夕照火鳳"


def score_fire_phoenix(high, mid, low, visibility, wind, gust, rain, hour):
    score = 0
    cloud_material = high + mid

    if 30 <= high <= 80:
        score += 35
    elif 15 <= high <= 90:
        score += 20
    elif high > 90:
        score += 10

    if 20 <= mid <= 60:
        score += 25
    elif 10 <= mid <= 80:
        score += 15

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

    if visibility >= 20:
        score += 10
    elif visibility >= 10:
        score += 5
    elif visibility < 5:
        score -= 15
    elif visibility < 8:
        score -= 8

    if gust >= 30 and cloud_material >= 35:
        score += 10
    elif gust >= 22 and cloud_material >= 35:
        score += 5

    if 20 <= rain <= 55 and cloud_material >= 35:
        score += 10
    elif 56 <= rain <= 70 and cloud_material >= 35:
        score += 5
    elif rain > 75:
        score -= 12

    if cloud_material >= 25:
        score += 5 if hour < 17 else 10

    if cloud_material < 15:
        score = min(score, 30)
    elif cloud_material < 25:
        score = min(score, 45)

    if low >= 80 and rain >= 70:
        score = min(score, 35)
    elif low >= 70 and rain >= 70:
        score = min(score, 48)
    elif low >= 65 and rain >= 75:
        score = min(score, 50)

    if visibility < 5:
        score = min(score, 45)

    return clamp(score)


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

    if 0.40 <= moon_phase <= 0.60:
        score -= 25
    elif 0.30 <= moon_phase <= 0.70:
        score -= 15

    if total_cloud >= 180:
        score = min(score, 30)
    elif total_cloud >= 130:
        score = min(score, 45)

    return clamp(score)


def az_label(az):
    dirs = [
        (0, "北"), (22.5, "北北東"), (45, "東北"), (67.5, "東北東"),
        (90, "東"), (112.5, "東南東"), (135, "東南"), (157.5, "南南東"),
        (180, "南"), (202.5, "南南西"), (225, "西南"), (247.5, "西南西"),
        (270, "西"), (292.5, "西北西"), (315, "西北"), (337.5, "北北西"),
        (360, "北")
    ]
    return min(dirs, key=lambda x: abs(x[0] - az))[1]


def score_milky_way_core(alt):
    if alt < 0:
        return 0
    if alt < 5:
        return 20
    if alt < 10:
        return 40
    if alt < 20:
        return 70
    if alt < 45:
        return 100
    return 85


def fetch_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "timezone": TZ,
        "forecast_days": 2,
        "daily": "sunset,sunrise,moon_phase",
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

            score = score_fire_phoenix(high, mid, low, visibility, wind, gust, rain, dt.hour)

            results.append({
                "time": dt,
                "score": score,
                "mode": fire_mode_name(dt.hour),
                "high": high,
                "mid": mid,
                "low": low,
                "visibility": visibility,
                "wind": wind,
                "gust": gust,
                "rain": rain
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

            score = score_star_sky(high, mid, low, visibility, rain, moon_phase)

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


def build_milky_way_core_results(start_window, end_window):
    location = EarthLocation(
        lat=LAT * u.deg,
        lon=LON * u.deg,
        height=ALT_M * u.m
    )

    galactic_center = SkyCoord(
        ra="17h45m40.04s",
        dec="-29d00m28.1s",
        frame="icrs"
    )

    results = []
    t = start_window

    while t <= end_window:
        aware_t = t.replace(tzinfo=ZoneInfo(TZ))
        time = Time(aware_t)
        frame = AltAz(obstime=time, location=location)
        altaz = galactic_center.transform_to(frame)

        alt = altaz.alt.degree
        az = altaz.az.degree

        results.append({
            "time": t,
            "alt": alt,
            "az": az,
            "az_label": az_label(az),
            "core_score": score_milky_way_core(alt)
        })

        t += timedelta(minutes=15)

    visible = [r for r in results if r["alt"] > 0]
    photo_good = [r for r in results if r["alt"] >= 10]
    highest = max(results, key=lambda x: x["alt"])

    return {
        "all": results,
        "rise": visible[0] if visible else None,
        "full_out": photo_good[0] if photo_good else None,
        "photo_start": photo_good[0] if photo_good else None,
        "photo_end": photo_good[-1] if photo_good else None,
        "highest": highest
    }


def merge_star_and_milky_way(star_results, mw_results):
    merged = []

    for s in star_results:
        nearest_mw = min(
            mw_results["all"],
            key=lambda x: abs((x["time"] - s["time"]).total_seconds())
        )

        final_score = round((s["score"] * 0.65) + (nearest_mw["core_score"] * 0.35))

        merged.append({
            **s,
            "mw_alt": nearest_mw["alt"],
            "mw_az": nearest_mw["az"],
            "mw_az_label": nearest_mw["az_label"],
            "mw_core_score": nearest_mw["core_score"],
            "final_score": clamp(final_score)
        })

    return merged


def print_fire_report(now, sunset, fire_results, start_window, end_window):
    best = max(fire_results, key=lambda x: x["score"])

    if start_window <= now <= end_window:
        current = min(fire_results, key=lambda x: abs((x["time"] - now).total_seconds()))
        current_text = f"{current['score']}%"
    else:
        current_text = "尚未進入觀察窗"

    conf, stars = confidence(now, best["time"])

    print("====== 火鳳雷達 v0.8 ======")
    print("地點：鳳林山觀景點")
    print(f"目前時間：{now.strftime('%H:%M')}")
    print(f"日落時間：{sunset.strftime('%H:%M')}")
    print(f"火鳳觀察窗：{start_window.strftime('%H:%M')} – {end_window.strftime('%H:%M')}")
    print()
    print(f"今日火鳳潛勢：{best['score']}%")
    print(f"即時火鳳指數：{current_text}")
    print(f"可信度：{conf}% {stars}")
    print()
    print(f"最佳預測時間：{best['time'].strftime('%H:%M')}")
    print(f"火鳳類型：{best['mode']}")
    print(fire_label(best["score"], best["rain"], best["low"], best["visibility"]))
    print()


def print_star_report(now, star_results, merged_results, start_window, end_window, moon_phase, mw):
    best = max(merged_results, key=lambda x: x["final_score"])

    if start_window <= now <= end_window:
        current = min(merged_results, key=lambda x: abs((x["time"] - now).total_seconds()))
        current_text = f"{current['final_score']}%"
    else:
        current_text = "尚未進入星空觀察窗"

    conf, stars = confidence(now, best["time"])

    print("====== 星空雷達 v0.8 ======")
    print("地點：鳳林山觀景點")
    print(f"星空觀察窗：{start_window.strftime('%H:%M')} – {end_window.strftime('%H:%M')}")
    print()
    print(f"今晚星空潛勢：{best['final_score']}%")
    print(f"即時星空指數：{current_text}")
    print(f"可信度：{conf}% {stars}")
    print(f"月相指數：{moon_phase:.2f}")
    print()
    print(f"最佳預測時間：{best['time'].strftime('%H:%M')}")
    print(star_label(best["final_score"]))
    print()
    print("銀河中心資訊：")

    if mw["rise"]:
        r = mw["rise"]
        print(f"銀河中心升起：{r['time'].strftime('%H:%M')} | 方位 {r['az']:.0f}° {r['az_label']}")
    else:
        print("銀河中心升起：今晚觀察窗內未升起")

    if mw["full_out"]:
        r = mw["full_out"]
        print(f"銀河中心完全浮出地面：{r['time'].strftime('%H:%M')} | 方位 {r['az']:.0f}° {r['az_label']}")
    else:
        print("銀河中心完全浮出地面：今晚不明顯")

    if mw["photo_start"] and mw["photo_end"]:
        print(
            f"建議銀河拍攝窗："
            f"{mw['photo_start']['time'].strftime('%H:%M')} – "
            f"{mw['photo_end']['time'].strftime('%H:%M')}"
        )
    else:
        print("建議銀河拍攝窗：今晚不建議主攻銀河中心")

    h = mw["highest"]
    print(
        f"銀河中心最高點：{h['time'].strftime('%H:%M')} | "
        f"仰角 {h['alt']:.0f}° | 方位 {h['az']:.0f}° {h['az_label']}"
    )

    print()
    print("最佳星空時段判斷資料：")
    print(f"高空雲：{best['high']}%")
    print(f"中層雲：{best['mid']}%")
    print(f"低層雲：{best['low']}%")
    print(f"能見度：{best['visibility']:.1f} km")
    print(f"降雨機率：{best['rain']}%")
    print(f"銀河中心仰角：{best['mw_alt']:.0f}°")
    print(f"銀河中心方位：{best['mw_az']:.0f}° {best['mw_az_label']}")
    print()
    print("星空逐時預測：")

    for r in merged_results:
        print(
            f"{r['time'].strftime('%H:%M')} | "
            f"{r['final_score']:3}% | "
            f"天氣 {r['score']:3}% | "
            f"銀河 {r['mw_core_score']:3}% | "
            f"仰角 {r['mw_alt']:5.1f}° | "
            f"方位 {r['mw_az']:6.1f}° {r['mw_az_label']} | "
            f"高 {r['high']:3}% 中 {r['mid']:3}% 低 {r['low']:3}% | "
            f"雨 {r['rain']:3}% | "
            f"能見度 {r['visibility']:.1f}km"
        )


def main():
    data = fetch_weather()

    now = datetime.now(ZoneInfo(TZ)).replace(tzinfo=None)

    sunset = datetime.fromisoformat(data["daily"]["sunset"][0]).replace(tzinfo=None)
    next_sunrise = datetime.fromisoformat(data["daily"]["sunrise"][1]).replace(tzinfo=None)
    moon_phase = data["daily"]["moon_phase"][0]

    fire_results, fire_start, fire_end = build_fire_results(data, sunset)

    star_results, star_start, star_end = build_star_results(
        data=data,
        sunset=sunset,
        next_sunrise=next_sunrise,
        moon_phase=moon_phase
    )

    mw_results = build_milky_way_core_results(
        start_window=star_start,
        end_window=star_end
    )

    merged_star_results = merge_star_and_milky_way(
        star_results=star_results,
        mw_results=mw_results
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
            merged_results=merged_star_results,
            start_window=star_start,
            end_window=star_end,
            moon_phase=moon_phase,
            mw=mw_results
        )


if __name__ == "__main__":
    main()
