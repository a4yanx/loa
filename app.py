import requests, schedule, time
from dotenv import load_dotenv
import os

load_dotenv()

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

last_event_id = None

def fetch_github_events():
    global last_event_id
    url = f"https://api.github.com/users/{GITHUB_USERNAME}/events"
    try:
        res = requests.get(url)
        events = res.json()

        for event in events:
            if event["id"] == last_event_id:
                break

            if event["type"] in ["ForkEvent", "PullRequestEvent", "PushEvent"]:
                repo = event["repo"]["name"]
                type_ = event["type"].replace("Event", "")
                time_ = event["created_at"]

                text = f"🧠 {type_} di {repo}\n🕒 {time_}"

                if event["type"] == "ForkEvent":
                    text += f"\n🔗 Forked to: {event['payload']['forkee']['html_url']}"

                if event["type"] == "PullRequestEvent":
                    pr = event["payload"]["pull_request"]
                    text += f"\n📄 PR: {pr['title']}\n🔗 {pr['html_url']}"

                if event["type"] == "PushEvent":
                    commits = "\n".join([f"• {c['message']}" for c in event["payload"]["commits"]])
                    text += f"\n📦 Commits:\n{commits}"

                requests.post(TELEGRAM_API, data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text
                })

        if events:
            last_event_id = events[0]["id"]

    except Exception as e:
        print("Error:", e)

schedule.every(1).minutes.do(fetch_github_events)

print("Bot is running...")
while True:
    schedule.run_pending()
    time.sleep(1)
