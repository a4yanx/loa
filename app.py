import requests
import schedule
import time
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Debug: Print all environment variables
print("=== DEBUG: Environment Variables ===")
for key, value in os.environ.items():
    if 'GITHUB' in key or 'TELEGRAM' in key:
        print(f"{key}: {value}")

print("=== All available env vars ===")
all_vars = list(os.environ.keys())
print(f"Total vars: {len(all_vars)}")
print("Relevant vars:", [k for k in all_vars if any(x in k.upper() for x in ['GITHUB', 'TELEGRAM'])])

# Environment variables
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print(f"GITHUB_USERNAME loaded: {GITHUB_USERNAME}")
print(f"TELEGRAM_BOT_TOKEN loaded: {'[HIDDEN]' if TELEGRAM_BOT_TOKEN else 'None'}")
print(f"TELEGRAM_CHAT_ID loaded: {TELEGRAM_CHAT_ID}")
print("=== END DEBUG ==="))

# Validate environment variables
required_vars = {
    "GITHUB_USERNAME": GITHUB_USERNAME,
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID
}

for var_name, var_value in required_vars.items():
    if not var_value:
        logger.error(f"Missing required environment variable: {var_name}")
        exit(1)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Global variable to track last processed event
last_event_id = None

def send_telegram_message(text: str, parse_mode: str = "Markdown") -> bool:
    """Send message to Telegram with inline keyboard for repository links"""
    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False
        }
        
        response = requests.post(TELEGRAM_API, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info("Message sent successfully")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False

def format_datetime(iso_string: str) -> str:
    """Format ISO datetime to readable format"""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except:
        return iso_string

def create_buttons_markup(repo_name: str, additional_url: Optional[str] = None) -> Dict:
    """Create inline keyboard markup for Telegram"""
    repo_url = f"https://github.com/{repo_name}"
    
    keyboard = [[{"text": "🔗 Repository", "url": repo_url}]]
    
    if additional_url:
        keyboard.append([{"text": "📄 View Details", "url": additional_url}])
    
    return {"inline_keyboard": keyboard}

def send_telegram_with_buttons(text: str, repo_name: str, additional_url: Optional[str] = None) -> bool:
    """Send Telegram message with inline buttons"""
    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": create_buttons_markup(repo_name, additional_url),
            "disable_web_page_preview": True
        }
        
        response = requests.post(TELEGRAM_API, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info("Message with buttons sent successfully")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message with buttons: {e}")
        return False

def process_push_event(event: Dict) -> None:
    """Process GitHub push event"""
    repo = event["repo"]["name"]
    time_formatted = format_datetime(event["created_at"])
    
    commits = event["payload"].get("commits", [])
    branch = event["payload"].get("ref", "").replace("refs/heads/", "")
    
    # Create commit list
    if commits:
        commit_list = []
        for commit in commits[:3]:  # Limit to first 3 commits
            message = commit["message"].split('\n')[0]  # First line only
            if len(message) > 50:
                message = message[:50] + "..."
            commit_list.append(f"• {message}")
        
        commits_text = "\n".join(commit_list)
        if len(commits) > 3:
            commits_text += f"\n• ... and {len(commits) - 3} more commits"
    else:
        commits_text = "• No commit details available"
    
    text = f"""🚀 *Push Event*

📦 **Repository:** `{repo}`
🌿 **Branch:** `{branch}`
🕒 **Time:** `{time_formatted}`

📝 **Commits:**
{commits_text}"""
    
    send_telegram_with_buttons(text, repo)

def process_pull_request_event(event: Dict) -> None:
    """Process GitHub pull request event"""
    repo = event["repo"]["name"]
    time_formatted = format_datetime(event["created_at"])
    
    pr = event["payload"]["pull_request"]
    action = event["payload"]["action"]
    
    text = f"""📋 *Pull Request {action.title()}*

📦 **Repository:** `{repo}`
📄 **Title:** {pr['title']}
👤 **Author:** {pr['user']['login']}
🕒 **Time:** `{time_formatted}`"""
    
    if pr.get('body') and len(pr['body']) > 0:
        description = pr['body'][:100] + "..." if len(pr['body']) > 100 else pr['body']
        text += f"\n💬 **Description:** {description}"
    
    send_telegram_with_buttons(text, repo, pr['html_url'])

def process_fork_event(event: Dict) -> None:
    """Process GitHub fork event"""
    repo = event["repo"]["name"]
    time_formatted = format_datetime(event["created_at"])
    
    forkee = event["payload"]["forkee"]
    
    text = f"""🍴 *Repository Forked*

📦 **Original:** `{repo}`
🔄 **Forked to:** `{forkee['full_name']}`
👤 **By:** {forkee['owner']['login']}
🕒 **Time:** `{time_formatted}`"""
    
    send_telegram_with_buttons(text, repo, forkee['html_url'])

def fetch_github_events() -> None:
    """Fetch and process GitHub events"""
    global last_event_id
    
    url = f"https://api.github.com/users/{GITHUB_USERNAME}/events"
    
    try:
        logger.info("Fetching GitHub events...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        events = response.json()
        
        if not events:
            logger.info("No events found")
            return
        
        # ANTI-SPAM: On first run, just set last_event_id without processing
        if last_event_id is None:
            last_event_id = events[0]["id"]
            logger.info(f"🚀 Bot started! Monitoring from now on... (skipping {len(events)} old events)")
            
            # Send startup message
            startup_msg = f"🤖 *GitHub Monitor Started!*\n\n👤 **Monitoring:** `{GITHUB_USERNAME}`\n⏰ **Started:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}`\n\n🔔 You'll get notified for new activities!"
            send_telegram_message(startup_msg)
            return
        
        # Process new events (in reverse order to maintain chronological order)
        new_events = []
        for event in events:
            if event["id"] == last_event_id:
                break
            new_events.append(event)
        
        if not new_events:
            logger.info("No new events to process")
            return
            
        logger.info(f"Processing {len(new_events)} new events")
        
        # ANTI-SPAM: Limit to max 5 events per check
        if len(new_events) > 5:
            logger.warning(f"Too many events ({len(new_events)})! Processing only the latest 5")
            new_events = new_events[:5]
        
        # Process events in chronological order
        for event in reversed(new_events):
            event_type = event["type"]
            
            logger.info(f"Processing {event_type} for {event['repo']['name']}")
            
            if event_type == "PushEvent":
                process_push_event(event)
            elif event_type == "PullRequestEvent":
                process_pull_request_event(event)
            elif event_type == "ForkEvent":
                process_fork_event(event)
            else:
                logger.info(f"Ignoring event type: {event_type}")
            
            # Delay between messages to avoid spam
            time.sleep(2)
        
        # Update last processed event ID
        last_event_id = events[0]["id"]
        logger.info(f"Updated last_event_id to: {last_event_id}")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching GitHub events: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

def main():
    """Main function to run the bot"""
    logger.info(f"GitHub to Telegram Bot started for user: {GITHUB_USERNAME}")
    logger.info("Bot is running... Press Ctrl+C to stop")
    
    # Schedule the job
    schedule.every(2).minutes.do(fetch_github_events)
    
    # Run initial fetch
    fetch_github_events()
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")

if __name__ == "__main__":
    main()
