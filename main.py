import os
import json
import asyncio
import logging
from typing import Dict, Any, List

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

CONFIG_FILE = os.getenv('CONFIG_FILE', 'config.json')
SESSION_NAME = os.getenv('SESSION_NAME', 'userbot_session')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
RUN_MODE = os.getenv('RUN_MODE', 'menu').lower()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger('fav-forwarder')


def default_config() -> Dict[str, Any]:
    return {
        'favorites': [],
        'target_channel_id': None,
        'last_configured_target_title': None,
    }


def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_FILE):
        cfg = default_config()
        save_config(cfg)
        return cfg
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(cfg: Dict[str, Any]) -> None:
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


async def ensure_login() -> None:
    await client.connect()
    if await client.is_user_authorized():
        return

    phone = input('شماره تلگرام را با فرمت بین المللی وارد کن (مثلا +98912xxxxxxx): ').strip()
    await client.send_code_request(phone)
    code = input('کد تایید تلگرام را وارد کن: ').strip()
    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        password = input('رمز تایید دومرحله ای (2FA) را وارد کن: ').strip()
        await client.sign_in(password=password)


async def fetch_channels() -> List[Dict[str, Any]]:
    dialogs = await client.get_dialogs()
    items: List[Dict[str, Any]] = []
    for d in dialogs:
        if d.is_channel:
            items.append({
                'id': int(d.id),
                'title': d.name,
                'username': getattr(d.entity, 'username', None),
            })
    items.sort(key=lambda x: x['title'].lower() if x['title'] else '')
    return items


async def print_channels() -> None:
    channels = await fetch_channels()
    cfg = load_config()
    favs = set(cfg.get('favorites', []))
    target = cfg.get('target_channel_id')

    print('\n===== لیست کانال ها =====')
    for ch in channels:
        star = '★' if ch['id'] in favs else ' '
        target_mark = ' [TARGET]' if ch['id'] == target else ''
        uname = f" @{ch['username']}" if ch.get('username') else ''
        print(f"[{star}] {ch['id']} | {ch['title']}{uname}{target_mark}")
    print('========================\n')


async def choose_favorites() -> None:
    channels = await fetch_channels()
    by_id = {str(ch['id']): ch for ch in channels}
    await print_channels()
    raw = input('آیدی کانال های موردنظر را با کاما وارد کن: ').strip()
    picked = [x.strip() for x in raw.split(',') if x.strip()]
    valid = []
    invalid = []
    for item in picked:
        if item in by_id:
            valid.append(int(item))
        else:
            invalid.append(item)
    cfg = load_config()
    cfg['favorites'] = sorted(set(valid))
    save_config(cfg)
    print('کانال های ستاره دار ذخیره شدند.')
    if invalid:
        print('این موارد پیدا نشدند:', ', '.join(invalid))


async def choose_target() -> None:
    channels = await fetch_channels()
    by_id = {str(ch['id']): ch for ch in channels}
    await print_channels()
    raw = input('آیدی کانال مقصد را وارد کن: ').strip()
    if raw not in by_id:
        print('کانال مقصد معتبر نیست.')
        return
    cfg = load_config()
    cfg['target_channel_id'] = int(raw)
    cfg['last_configured_target_title'] = by_id[raw]['title']
    save_config(cfg)
    print(f"کانال مقصد تنظیم شد: {by_id[raw]['title']}")


async def show_config() -> None:
    cfg = load_config()
    print('\n===== تنظیمات فعلی =====')
    print(json.dumps(cfg, ensure_ascii=False, indent=2))
    print('=======================\n')


async def verify_target_access() -> bool:
    cfg = load_config()
    target = cfg.get('target_channel_id')
    if not target:
        print('اول باید کانال مقصد را تنظیم کنی.')
        return False
    try:
        entity = await client.get_entity(target)
        title = getattr(entity, 'title', str(target))
        print(f'دسترسی کانال مقصد تایید شد: {title}')
        return True
    except Exception as e:
        print(f'به کانال مقصد دسترسی ندارم یا آیدی اشتباه است: {e}')
        return False


@client.on(events.NewMessage)
async def forward_favorites(event):
    try:
        cfg = load_config()
        favorites = set(cfg.get('favorites', []))
        target = cfg.get('target_channel_id')

        if not target:
            return
        if not event.is_channel:
            return
        if event.chat_id not in favorites:
            return
        if getattr(event.message, 'post', False) is False:
            return

        await client.forward_messages(target, event.message)
        logger.info('Forwarded message %s from %s to %s', event.message.id, event.chat_id, target)
    except Exception as e:
        logger.exception('Forward failed: %s', e)


async def interactive_menu() -> None:
    while True:
        print('''\n1) نمایش لیست کانال ها
2) انتخاب/ویرایش کانال های ستاره دار
3) انتخاب/تغییر کانال مقصد
4) نمایش تنظیمات فعلی
5) بررسی دسترسی کانال مقصد
6) شروع مانیتورینگ و فوروارد خودکار
0) خروج\n''')
        cmd = input('انتخاب: ').strip()
        if cmd == '1':
            await print_channels()
        elif cmd == '2':
            await choose_favorites()
        elif cmd == '3':
            await choose_target()
        elif cmd == '4':
            await show_config()
        elif cmd == '5':
            await verify_target_access()
        elif cmd == '6':
            ok = await verify_target_access()
            if not ok:
                continue
            cfg = load_config()
            if not cfg.get('favorites'):
                print('هنوز هیچ کانالی را ستاره دار نکرده ای.')
                continue
            print('مانیتورینگ شروع شد. برای توقف Ctrl+C بزن.')
            await client.run_until_disconnected()
            break
        elif cmd == '0':
            break
        else:
            print('گزینه نامعتبر است.')


async def main() -> None:
    if not API_ID or not API_HASH:
        raise RuntimeError('API_ID و API_HASH باید در متغیرهای محیطی تنظیم شوند.')
    await ensure_login()
    me = await client.get_me()
    logger.info('Logged in as %s (%s)', me.first_name, me.id)

    if RUN_MODE == 'monitor':
        ok = await verify_target_access()
        if not ok:
            raise RuntimeError('کانال مقصد معتبر نیست یا دسترسی کافی نداری.')
        cfg = load_config()
        if not cfg.get('favorites'):
            raise RuntimeError('هیچ کانال ستاره داری تنظیم نشده است.')
        print('مانیتورینگ خودکار شروع شد. برای توقف Ctrl+C بزن.')
        await client.run_until_disconnected()
        return

    await interactive_menu()


if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
