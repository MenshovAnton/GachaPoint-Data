#!/usr/bin/env python3
"""
GachaPoint Notification Module — Telegram Failure & Event Alerts
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from typing import Optional


def get_credentials() -> tuple[Optional[str], Optional[str]]:
    """Retrieves token and chat_id from environment or optional .env file."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k == "TELEGRAM_BOT_TOKEN" and not token:
                            token = v
                        elif k == "TELEGRAM_CHAT_ID" and not chat_id:
                            chat_id = v
            except Exception:
                pass

    return token, chat_id


def send_telegram_message(text: str, parse_mode: str = "HTML") -> bool:
    """Sends a message via Telegram Bot API. Returns True if successful, False otherwise."""
    token, chat_id = get_credentials()
    if not token or not chat_id:
        print("[Telegram] Alerting skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "GachaPointBot/1.0"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                print("[Telegram] Notification sent successfully.")
                return True
            else:
                print(f"[Telegram] Failed with status {response.status}")
                return False
    except Exception as e:
        print(f"[Telegram] Error sending alert: {e}", file=sys.stderr)
        return False


def notify_failure(summary: str, details: Optional[str] = None):
    """Sends a critical failure notification to Telegram."""
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "MenshovAnton/GachaPoint-Data")
    run_id = os.environ.get("GITHUB_RUN_ID")

    link = f"{server_url}/{repo}/actions/runs/{run_id}" if run_id else f"{server_url}/{repo}"

    msg = (
        f"🚨 <b>[GachaPoint Bot Alert: Sync Failure]</b>\n\n"
        f"<b>Summary:</b> {summary}\n"
    )
    if details:
        clean_details = details[:800].replace("<", "&lt;").replace(">", "&gt;")
        msg += f"<pre>{clean_details}</pre>\n\n"

    msg += f"🔗 <a href=\"{link}\">View Workflow Run</a>"
    send_telegram_message(msg)


def notify_new_codes(new_codes: list[dict]):
    """Sends an informational notification when new promo codes are added."""
    if not new_codes:
        return

    game_names = {0: "Genshin Impact", 1: "Honkai: Star Rail", 2: "Zenless Zone Zero", 3: "Honkai Impact 3rd"}
    msg = f"🎁 <b>[GachaPoint: New Promo Codes Found]</b>\n\n"

    for c in new_codes:
        g_name = game_names.get(c.get("game_type", 0), "Gacha")
        code = c.get("code", "")
        rewards = c.get("rewards_description_ru") or c.get("rewards_description_en") or "Награды"
        is_stream = "🔥 [STREAM]" if c.get("is_stream") else "✨"
        msg += f"• <b>{g_name}</b> {is_stream} <code>{code}</code>\n  {rewards}\n"

    send_telegram_message(msg)


def notify_suspicious_announcement(game_name: str, title: str, reason: str, post_url: Optional[str] = None):
    """Sends an alert when an announcement contains unknown characters or ambiguous info requiring manual verification."""
    msg = (
        f"⚠️ <b>[GachaPoint Bot: Требуется проверка анонса]</b>\n\n"
        f"<b>Игра:</b> {game_name}\n"
        f"<b>Новость:</b> {title}\n"
        f"<b>Причина:</b> {reason}\n"
    )
    if post_url:
        msg += f"🔗 <a href=\"{post_url}\">Открыть публикацию HoYoLAB</a>\n\n"
    msg += "<i>Бот не стал добавлять непроверенные данные, чтобы исключить сливы и ошибки. Проверьте и примените вручную.</i>"
    send_telegram_message(msg)


def notify_code_review(items: list[dict]):
    """Sends a digest of promo codes that need manual verification."""
    if not items:
        return

    game_names = {0: "Genshin Impact", 1: "Honkai: Star Rail", 2: "Zenless Zone Zero", 3: "Honkai Impact 3rd"}
    redeem_urls = {
        0: "https://genshin.hoyoverse.com/ru/gift?code={code}",
        1: "https://hsr.hoyoverse.com/gift?code={code}",
        2: "https://zenless.hoyoverse.com/redemption?code={code}",
        3: "https://act.hoyoverse.com/puzzle/bh3/pz_u6h7mQo34g/index.html?cdkey={code}",
    }

    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "MenshovAnton/GachaPoint-Data")
    verify_url = f"{server_url}/{repo}/actions/workflows/verify-code.yml"

    msg = "🔎 <b>[GachaPoint: коды требуют проверки]</b>\n\n"
    for item in items[:10]:
        game_type = int(item.get("game_type", 0))
        code = item.get("code", "")
        rewards = item.get("rewards_description_ru") or item.get("rewards_description_en") or "Награды не распознаны"
        source = item.get("source_url") or "официальный источник не найден"
        template = redeem_urls.get(game_type, "")
        redeem = template.format(code=code) if template else ""
        msg += (
            f"• <b>{game_names.get(game_type, 'Gacha')}</b> <code>{code}</code>\n"
            f"  {rewards}\n"
            f"  Источник: {source}\n"
        )
        if redeem:
            msg += f"  Проверить: <a href=\"{redeem}\">открыть страницу активации</a>\n"

    if len(items) > 10:
        msg += f"\n…и ещё {len(items) - 10} код(ов) в quarantine_codes.json."

    msg += (
        f"\n🔗 <a href=\"{verify_url}\">Подтвердить в GitHub Actions</a>\n"
        "<i>Или локально: python -m scripts.tools.apply_code_checks --set GAME CODE ok</i>"
    )
    send_telegram_message(msg)


def notify_new_banners(new_banners: list[dict]):
    """Sends an alert when new verified official banners are scheduled."""
    if not new_banners:
        return
    game_names = {0: "Genshin Impact", 1: "Honkai: Star Rail", 2: "Zenless Zone Zero", 3: "Honkai Impact 3rd"}
    msg = f"🗓️ <b>[GachaPoint: Обнаружены новые официальные баннеры]</b>\n\n"
    for b in new_banners:
        g_name = game_names.get(b.get("game_type", 0), "Gacha")
        ver = b.get("version", "?")
        phase = b.get("phase", "?")
        fives = ", ".join(b.get("featured_five_stars_ru") or b.get("featured_five_stars_en") or [])
        dates = f"{b.get('start_date', '?')} — {b.get('end_date', '?')}"
        msg += f"• <b>{g_name} v{ver} (Фаза {phase})</b>\n  5★: {fives}\n  Сроки: {dates}\n"
    send_telegram_message(msg)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--failure":
        error_msg = sys.argv[2] if len(sys.argv) > 2 else "Unknown workflow error"
        notify_failure("GitHub Actions Step Failed", error_msg)
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        send_telegram_message("🤖 <b>[GachaPoint Bot]</b> Test notification: Telegram integration is working!")
