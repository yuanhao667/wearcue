import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain.weather_rules import WeatherInput
from app.services.push_service import PushService, SubscriptionGoneError
from app.services.recommendation_service import (
    recommend_official_outfit,
    recommend_personal_outfit,
)
from app.services.store import store
from app.services.weather_service import WeatherService

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60
# 进程重启后最多补发 2 小时内的提醒，避免因为错过分钟而漏发。
FIRE_WINDOW_SECONDS = 2 * 3600


def _local_now(tz_name: str) -> datetime:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz)


def _build_message(recommendation: dict, weather: dict) -> str:
    items = recommendation.get("items") or []
    names = [
        str(item.get("variant_type") or "").strip()
        for item in items
        if item.get("variant_type")
    ]
    main = "、".join(names[:4]) or recommendation.get("label") or "今日推荐"
    low = round(float(weather.get("apparent_min") or 0))
    high = round(float(weather.get("apparent_max") or 0))
    return f"今日 {low}–{high}°：{main}"


async def _run_due_reminders_once() -> None:
    users = store.list_reminder_users()
    if not users:
        return
    weather_service = WeatherService()
    push = PushService()
    for user in users:
        try:
            tz_name = user.get("timezone") or "UTC"
            now_local = _local_now(tz_name)
            weekday = now_local.isoweekday()
            reminder_days = user.get("reminder_days") or [1, 2, 3, 4, 5]
            if weekday not in reminder_days:
                continue

            reminder_time = user.get("reminder_time") or "07:30"
            try:
                hour_str, minute_str = reminder_time.split(":")
                reminder_dt = now_local.replace(
                    hour=int(hour_str), minute=int(minute_str), second=0, microsecond=0
                )
            except (ValueError, AttributeError):
                continue

            delta = (now_local - reminder_dt).total_seconds()
            if delta < 0 or delta > FIRE_WINDOW_SECONDS:
                continue

            key = "daily:%s" % now_local.strftime("%Y-%m-%d")
            if store.get_delivery(key, user["user_id"]):
                continue

            weather = await weather_service.get_today(
                latitude=float(user["latitude"]),
                longitude=float(user["longitude"]),
                city=user.get("city_name") or "当前位置",
            )
            weather_input = WeatherInput(
                apparent_min=weather["apparent_min"],
                apparent_max=weather["apparent_max"],
                max_precipitation_probability=weather["max_precipitation_probability"],
                total_precipitation=weather["total_precipitation"],
                total_snowfall=weather["total_snowfall"],
                max_wind_speed=weather["max_wind_speed"],
                max_wind_gust=weather["max_wind_gust"],
                uv_index_max=weather["uv_index_max"],
                cold_offset=int(user.get("cold_offset") or 0),
            )
            personal = recommend_personal_outfit(
                weather=weather_input,
                scene="commute",
                audience=user["audience"],
                outfits=store.list_outfits(in_pool=True, user_id=user["user_id"]),
            )
            recommendation = personal or recommend_official_outfit(
                weather=weather_input,
                scene="commute",
                audience=user["audience"],
                city_id=user.get("city_id") or "unknown",
                local_date=weather["date"],
            )
            message = _build_message(recommendation, weather)

            subscriptions = store.enabled_subscriptions(user["user_id"])
            status = "no_subscription"
            if push.configured and subscriptions:
                sent = 0
                for subscription in subscriptions:
                    try:
                        await asyncio.to_thread(push.send, subscription, message)
                        store.set_subscription_result(
                            subscription["id"], "sent", user["user_id"]
                        )
                        sent += 1
                    except SubscriptionGoneError:
                        store.remove_subscription(subscription["id"], user["user_id"])
                    except Exception as exc:  # noqa: BLE001 - 单条失败不阻断其余
                        logger.warning(
                            "push send failed for subscription %s: %s",
                            subscription["id"],
                            exc,
                        )
                        store.set_subscription_result(
                            subscription["id"], "failed", user["user_id"]
                        )
                status = "sent" if sent else "failed"
            store.record_delivery(key, message, status, user["user_id"])
        except Exception:  # noqa: BLE001 - 单用户失败不影响其他用户
            logger.exception("reminder failed for user %s", user.get("user_id"))


async def reminder_loop() -> None:
    while True:
        try:
            await _run_due_reminders_once()
        except Exception:  # noqa: BLE001
            logger.exception("reminder loop error")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
