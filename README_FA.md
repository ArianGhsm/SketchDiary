# Telegram Favorite Channel Forwarder

A user-account Telegram forwarder built with Telethon.

## Features
- List joined channels
- Mark selected channels as favorites
- Pick a target channel
- Forward new posts from favorite channels to target channel immediately

## Local run
1. Create Telegram API credentials at my.telegram.org
2. Copy `.env.example` values into your shell or hosting provider env vars
3. Install requirements:
   pip install -r requirements.txt
4. Run:
   python main.py

## Notes
- This uses a Telegram user account, not a Bot API token.
- Your account must be able to post in the target channel.
- Favorites are app-side and stored in `config.json`.
