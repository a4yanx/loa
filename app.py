import requests
import schedule
import time
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional

# Setup minimal logging
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings and errors
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Validate environment variables (silent check)
required_vars = [GITHUB_USERNAME, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]
if not all(required_vars):
    print("❌ Missing environment variables!")
    exit(1)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Global variable to track last processed event
last_event_id = None

def send_telegram_message(text: str, parse_mode: str = "HTML", buttons: Optional[Dict] = None) -> bool:
    """Send enhanced message to Telegram"""
    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        if buttons:
            payload["reply_markup"] = buttons
        
        response = requests.post(TELEGRAM_API, json=payload, timeout=10)
        response.raise_for_status()
        return True
        
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False

def format_datetime(iso_string: str) -> str:
    """Format datetime to readable format"""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%m/%d %H:%M')
    except:
        return "unknown"

def create_inline_buttons(repo_name: str, additional_url: Optional[str] = None) -> Dict:
    """Create beautiful inline keyboard"""
    repo_url = f"https://github.com/{repo_name}"
    
    keyboard = [[{"text": "🔗 View Repo", "url": repo_url}]]
    
    if additional_url:
        keyboard.append([{"text": "📋 Details", "url": additional_url}])
    
    return {"inline_keyboard": keyboard}

def get_commit_emoji(message: str) -> str:
    """Get emoji based on commit message"""
    msg = message.lower()
    if any(word in msg for word in ['fix', 'bug', 'patch']):
        return '🐛'
    elif any(word in msg for word in ['feat', 'add', 'new']):
        return '✨'
    elif any(word in msg for word in ['update', 'improve', 'enhance']):
        return '⚡'
    elif any(word in msg for word in ['docs', 'readme']):
        return '📚'
    elif any(word in msg for word in ['style', 'format']):
        return '💄'
    elif any(word in msg for word in ['test']):
        return '🧪'
    elif any(word in msg for word in ['refactor', 'clean']):
        return '♻️'
    else:
        return '📝'

def process_push_event(event: Dict) -> None:
    """Process GitHub push event with beautiful formatting"""
    repo = event["repo"]["name"]
    time_formatted = format_datetime(event["created_at"])
    
    commits = event["payload"].get("commits", [])
    branch = event["payload"].get("ref", "").replace("refs/heads/", "")
    
    # Beautiful header
    repo_short = repo.split('/')[-1]  # Just repo name, not username/repo
    
    if commits:
        commit_count = len(commits)
        commits_preview = []
        
        for commit in commits[:3]:
            message = commit["message"].split('\n')[0]
            if len(message) > 45:
                message = message[:45] + "..."
            
            emoji = get_commit_emoji(message)
            commits_preview.append(f"{emoji} {message}")
        
        commits_text = '\n'.join(commits_preview)
        if commit_count > 3:
            commits_text += f"\n<i>... and {commit_count - 3} more</i>"
    else:
        commits_text = "📝 <i>No details available</i>"
        commit_count = 0
    
    # Create beautiful message with blockquote
    text = f"""🚀 <b>{repo_short}</b> • <code>{branch}</code>

<blockquote>
{commits_text}
</blockquote>

<i>🕐 {time_formatted} • {commit_count} commit{'s' if commit_count != 1 else ''}</i>"""
    
    buttons = create_inline_buttons(repo)
    send_telegram_message(text, buttons=buttons)

def process_pull_request_event(event: Dict) -> None:
    """Process GitHub pull request event with beautiful formatting"""
    repo = event["repo"]["name"]
    time_formatted = format_datetime(event["created_at"])
    
    pr = event["payload"]["pull_request"]
    action = event["payload"]["action"]
    
    repo_short = repo.split('/')[-1]
    
    # Action emoji mapping
    action_emojis = {
        'opened': '📤',
        'closed': '🔒',
        'merged': '🎉',
        'reopened': '🔄',
        'edited': '✏️'
    }
    
    action_emoji = action_emojis.get(action, '📋')
    
    # PR title truncation
    title = pr['title']
    if len(title) > 60:
        title = title[:60] + "..."
    
    text = f"""{action_emoji} <b>PR {action.title()}</b> • <b>{repo_short}</b>

<blockquote>
<b>{title}</b>
<i>by @{pr['user']['login']}</i>"""
    
    if pr.get('body') and len(pr['body']) > 0:
        description = pr['body'][:80] + "..." if len(pr['body']) > 80 else pr['body']
        text += f"\n\n💬 {description}"
    
    text += f"""
</blockquote>

<i>🕐 {time_formatted}</i>"""
    
    buttons = create_inline_buttons(repo, pr['html_url'])
    send_telegram_message(text, buttons=buttons)

def process_fork_event(event: Dict) -> None:
    """Process GitHub fork event with beautiful formatting"""
    repo = event["repo"]["name"]
    time_formatted = format_datetime(event["created_at"])
    
    forkee = event["payload"]["forkee"]
    
    repo_short = repo.split('/')[-1]
    fork_name = forkee['full_name'].split('/')[-1]
    
    text = f"""🍴 <b>Fork Created</b>

<blockquote>
<b>{repo_short}</b> → <b>{fork_name}</b>
<i>by @{forkee['owner']['login']}</i>
</blockquote>

<i>🕐 {time_formatted}</i>"""
    
    buttons = create_inline_buttons(repo, forkee['html_url'])
    send_telegram_message(text, buttons=buttons)

def process_star_event(event: Dict) -> None:
    """Process GitHub star event"""
    repo = event["repo"]["name"]
    time_formatted = format_datetime(event["created_at"])
    
    repo_short = repo.split('/')[-1]
    
    text = f"""⭐ <b>New Star!</b>

<blockquote>
<b>{repo_short}</b>
<i>starred by @{event['actor']['login']}</i>
</blockquote>

<i>🕐 {time_formatted}</i>"""
    
    buttons = create_inline_buttons(repo)
    send_telegram_message(text, buttons=buttons)

def process_release_event(event: Dict) -> None:
    """Process GitHub release event"""
    repo = event["repo"]["name"]
    time_formatted = format_datetime(event["created_at"])
    
    release = event["payload"]["release"]
    repo_short = repo.split('/')[-1]
    
    text = f"""🎉 <b>New Release!</b>

<blockquote>
<b>{repo_short}</b> <code>{release['tag_name']}</code>
<b>{release['name']}</b>
</blockquote>

<i>🕐 {time_formatted}</i>"""
    
    buttons = create_inline_buttons(repo, release['html_url'])
    send_telegram_message(text, buttons=buttons)

def fetch_github_events() -> None:
    """Fetch and process GitHub events"""
    global last_event_id
    
    url = f"https://api.github.com/users/{GITHUB_USERNAME}/events"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        events = response.json()
        
        if not events:
            return
        
        # ANTI-SPAM: On first run, just set last_event_id without processing
        if last_event_id is None:
            last_event_id = events[0]["id"]
            print("🤖 Bot started - monitoring GitHub activity...")
            
            # Send beautiful startup message
            startup_msg = f"""🚀 <b>GitHub Monitor Active!</b>

<blockquote>
👤 <b>Watching:</b> <code>{GITHUB_USERNAME}</code>
🕐 <b>Started:</b> <code>{datetime.now().strftime('%m/%d %H:%M')}</code>
</blockquote>

<i>🔔 Ready to notify you about new activities!</i>"""
            
            send_telegram_message(startup_msg)
            return
        
        # Process new events
        new_events = []
        for event in events:
            if event["id"] == last_event_id:
                break
            new_events.append(event)
        
        if not new_events:
            return
            
        # ANTI-SPAM: Limit to max 3 events per check
        if len(new_events) > 3:
            new_events = new_events[:3]
            print(f"⚠️ Limited to 3 events (had {len(events)} new)")
        
        # Process events in chronological order
        for event in reversed(new_events):
            event_type = event["type"]
            
            if event_type == "PushEvent":
                process_push_event(event)
            elif event_type == "PullRequestEvent":
                process_pull_request_event(event)
            elif event_type == "ForkEvent":
                process_fork_event(event)
            elif event_type == "WatchEvent":
                process_star_event(event)
            elif event_type == "ReleaseEvent":
                process_release_event(event)
            # Skip other event types silently
            
            # Delay between messages
            time.sleep(1.5)
        
        # Update last processed event ID
        last_event_id = events[0]["id"]
        print(f"✅ Processed {len(new_events)} events")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"GitHub API error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

def main():
    """Main function to run the bot"""
    print(f"🚀 GitHub → Telegram Bot")
    print(f"👤 Monitoring: {GITHUB_USERNAME}")
    print("🔄 Checking every 2 minutes...")
    
    # Schedule the job
    schedule.every(2).minutes.do(fetch_github_events)
    
    # Run initial fetch
    fetch_github_events()
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")

if __name__ == "__main__":
    main()
