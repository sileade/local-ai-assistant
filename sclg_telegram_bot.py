#!/usr/bin/env python3
"""
SCLG-AI Telegram Bot v2.0.0
============================
Personal AI Assistant + DevOps Agent for Mac Mini.

Features:
  - Personal Assistant: Calendar events, iCloud Reminders, Apple Notes, Contacts
  - Context-aware intent detection: "встреча завтра в 10" → creates calendar event
  - DevOps Agent: Execute commands, scan networks, SSH to hosts
  - MoE routing (sysadmin/code/devops/creative/analysis/assistant)
  - Claude API + Ollama local models with fallback
  - Voice message transcription (Whisper)
  - Scheduled tasks (heartbeat)
  - Progress indicators (typing + message editing)
  - Access control, ticket system, cost tracking
  - Anti-AI-isms response post-processing

Inspired by: Paperclip.ing, Claude Cowork, NanoBot, ai-router-moe, avoid-ai-writing
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

VERSION = "2.0.0"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Ollama GPU Balancer
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://172.27.4.1:11434")
OLLAMA_TIMEOUT = 180

# Claude API
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"  # Works with this key
CLAUDE_FALLBACK_MODEL = "claude-sonnet-4-20250514"  # Fallback to same model (haiku not available)

# SSH to Mac Mini (bot runs locally on Mac Mini, so default is localhost)
MAC_HOST = os.environ.get("MAC_HOST", "localhost")
MAC_USER = os.environ.get("MAC_USER", "ilea")
MAC_PORT = int(os.environ.get("MAC_PORT", "22"))

# Access control — empty means auto-add first user as admin
ALLOWED_USERS = set()
ADMIN_USERS = set()
_allowed_env = os.environ.get("TG_ALLOWED_USERS", "")
_admin_env = os.environ.get("TG_ADMIN_USERS", "")
if _allowed_env:
    ALLOWED_USERS = {int(x.strip()) for x in _allowed_env.split(",") if x.strip()}
if _admin_env:
    ADMIN_USERS = {int(x.strip()) for x in _admin_env.split(",") if x.strip()}

# Data directories
DATA_DIR = Path.home() / ".sclg-ai" / "telegram"
TICKETS_DIR = DATA_DIR / "tickets"
CACHE_DIR = DATA_DIR / "cache"
VOICE_DIR = DATA_DIR / "voice"
LOGS_DIR = DATA_DIR / "logs"
MEMORY_DIR = DATA_DIR / "memory"

for d in [DATA_DIR, TICKETS_DIR, CACHE_DIR, VOICE_DIR, LOGS_DIR, MEMORY_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Cost tracking
COST_FILE = DATA_DIR / "costs.json"
COST_LIMITS = {
    "daily": float(os.environ.get("COST_LIMIT_DAILY", "5.0")),
    "monthly": float(os.environ.get("COST_LIMIT_MONTHLY", "50.0")),
}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "bot.log"),
    ]
)
log = logging.getLogger("sclg-tg")


# ═══════════════════════════════════════════════════════════════
# ENUMS & DATA CLASSES
# ═══════════════════════════════════════════════════════════════

class ExpertType(Enum):
    SYSADMIN = "sysadmin"
    CODE = "code"
    DEVOPS = "devops"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    ASSISTANT = "assistant"
    GENERAL = "general"


class IntentType(Enum):
    """Personal assistant intents detected from context."""
    CALENDAR_CREATE = "calendar_create"
    CALENDAR_VIEW = "calendar_view"
    REMINDER_CREATE = "reminder_create"
    REMINDER_LIST = "reminder_list"
    NOTE_CREATE = "note_create"
    NOTE_SEARCH = "note_search"
    CONTACT_SEARCH = "contact_search"
    TIMER_SET = "timer_set"
    SYSTEM_CMD = "system_cmd"
    CHAT = "chat"


@dataclass
class Ticket:
    id: str
    user_id: int
    username: str
    query: str
    expert: ExpertType
    intent: str = ""
    model_used: str = ""
    response: str = ""
    commands_run: List[str] = field(default_factory=list)
    cost_usd: float = 0.0
    created_at: str = ""
    completed_at: str = ""
    duration_s: float = 0.0
    status: str = "open"

    def save(self):
        self.completed_at = datetime.now().isoformat()
        path = TICKETS_DIR / f"{self.id}.json"
        data = {k: (v.value if isinstance(v, Enum) else v) for k, v in self.__dict__.items()}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════════════
# COST TRACKER
# ═══════════════════════════════════════════════════════════════

class CostTracker:
    PRICING = {
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-20250514": {"input": 0.25, "output": 1.25},
    }

    def __init__(self):
        self.entries: List[Dict] = []
        self._load()

    def _load(self):
        if COST_FILE.exists():
            try:
                self.entries = json.loads(COST_FILE.read_text())
            except Exception:
                self.entries = []

    def _save(self):
        COST_FILE.write_text(json.dumps(self.entries, indent=2))

    def add(self, model: str, tokens_in: int, tokens_out: int) -> float:
        pricing = self.PRICING.get(model, {"input": 3.0, "output": 15.0})
        cost = (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000
        self.entries.append({
            "model": model, "tokens_in": tokens_in, "tokens_out": tokens_out,
            "cost_usd": round(cost, 6), "timestamp": datetime.now().isoformat(),
        })
        self._save()
        return cost

    def get_today(self) -> float:
        today = datetime.now().date().isoformat()
        return sum(e["cost_usd"] for e in self.entries if e["timestamp"][:10] == today)

    def get_month(self) -> float:
        month = datetime.now().strftime("%Y-%m")
        return sum(e["cost_usd"] for e in self.entries if e["timestamp"][:7] == month)

    def check_limits(self) -> Tuple[bool, str]:
        daily, monthly = self.get_today(), self.get_month()
        if daily >= COST_LIMITS["daily"]:
            return False, f"Daily limit: ${daily:.2f}/${COST_LIMITS['daily']:.2f}"
        if monthly >= COST_LIMITS["monthly"]:
            return False, f"Monthly limit: ${monthly:.2f}/${COST_LIMITS['monthly']:.2f}"
        return True, ""

    def summary(self) -> str:
        return (
            f"Today:  ${self.get_today():.4f} / ${COST_LIMITS['daily']:.2f}\n"
            f"Month:  ${self.get_month():.4f} / ${COST_LIMITS['monthly']:.2f}\n"
            f"Total:  ${sum(e['cost_usd'] for e in self.entries):.4f} ({len(self.entries)} calls)"
        )


# ═══════════════════════════════════════════════════════════════
# PERSONAL ASSISTANT — macOS Integration via osascript
# ═══════════════════════════════════════════════════════════════

class PersonalAssistant:
    """
    Integrates with macOS Calendar, Reminders, Notes, Contacts via AppleScript.
    Runs osascript commands locally on Mac Mini.
    """

    def __init__(self, executor):
        self.executor = executor

    # ─── Calendar ───────────────────────────────────────────────

    async def create_calendar_event(self, title: str, date_str: str, time_str: str = "",
                                     duration_min: int = 60, calendar_name: str = "",
                                     location: str = "", notes: str = "") -> str:
        """Create a calendar event using AppleScript."""
        # Parse date/time
        dt = self._parse_datetime(date_str, time_str)
        if not dt:
            return f"Could not parse date/time: {date_str} {time_str}"

        end_dt = dt + timedelta(minutes=duration_min)
        start_str = dt.strftime("%B %d, %Y at %I:%M:%S %p")
        end_str = end_dt.strftime("%B %d, %Y at %I:%M:%S %p")

        cal_target = f'calendar "{calendar_name}"' if calendar_name else 'first calendar'

        script = f'''
        tell application "Calendar"
            tell {cal_target}
                set newEvent to make new event with properties {{summary:"{self._escape(title)}", start date:date "{start_str}", end date:date "{end_str}"'''

        if location:
            script += f', location:"{self._escape(location)}"'
        if notes:
            script += f', description:"{self._escape(notes)}"'

        script += '''}}
            end tell
        end tell
        return "OK"
        '''

        output, rc = await self.executor.execute(f"osascript -e '{script}'", timeout=15)
        if rc == 0:
            time_display = dt.strftime("%d.%m.%Y %H:%M")
            return f"Created event: {title}\nDate: {time_display}\nDuration: {duration_min} min"
        return f"Error creating event: {output}"

    async def get_calendar_events(self, days: int = 1, calendar_name: str = "") -> str:
        """Get upcoming calendar events."""
        script = '''
        set output to ""
        set today to current date
        set endDate to today + (''' + str(days) + ''' * days)
        tell application "Calendar"
            repeat with cal in calendars
                set calName to name of cal
                set evts to (every event of cal whose start date >= today and start date <= endDate)
                repeat with evt in evts
                    set evtTitle to summary of evt
                    set evtStart to start date of evt
                    set evtEnd to end date of evt
                    set evtLoc to ""
                    try
                        set evtLoc to location of evt
                    end try
                    set output to output & calName & " | " & evtTitle & " | " & (evtStart as string) & " - " & (evtEnd as string)
                    if evtLoc is not "" then
                        set output to output & " @ " & evtLoc
                    end if
                    set output to output & linefeed
                end repeat
            end repeat
        end tell
        return output
        '''
        output, rc = await self.executor.execute(f"osascript -e '{script}'", timeout=15)
        if rc == 0 and output.strip():
            lines = output.strip().split("\n")
            result = f"Events for next {days} day(s):\n\n"
            for line in lines:
                parts = line.split(" | ")
                if len(parts) >= 3:
                    result += f"  {parts[0]}: {parts[1]}\n    {parts[2]}\n"
                else:
                    result += f"  {line}\n"
            return result
        elif rc == 0:
            return f"No events in the next {days} day(s)."
        return f"Error reading calendar: {output}"

    # ─── Reminders (iCloud) ─────────────────────────────────────

    async def create_reminder(self, title: str, due_date: str = "", due_time: str = "",
                               list_name: str = "", notes: str = "", priority: int = 0) -> str:
        """Create a reminder in Apple Reminders."""
        list_target = f'list "{list_name}"' if list_name else 'default list'

        script = f'''
        tell application "Reminders"
            tell {list_target}
                set newReminder to make new reminder with properties {{name:"{self._escape(title)}"'''

        if notes:
            script += f', body:"{self._escape(notes)}"'
        if priority > 0:
            script += f', priority:{min(priority, 9)}'

        script += '}'

        if due_date:
            dt = self._parse_datetime(due_date, due_time)
            if dt:
                date_str = dt.strftime("%B %d, %Y at %I:%M:%S %p")
                script += f'''
                set due date of newReminder to date "{date_str}"'''

        script += '''
            end tell
        end tell
        return "OK"
        '''

        output, rc = await self.executor.execute(f"osascript -e '{script}'", timeout=15)
        if rc == 0:
            result = f"Reminder created: {title}"
            if due_date:
                result += f"\nDue: {due_date} {due_time}".strip()
            return result
        return f"Error creating reminder: {output}"

    async def list_reminders(self, list_name: str = "", show_completed: bool = False) -> str:
        """List reminders."""
        filter_str = "" if show_completed else "whose completed is false"
        list_filter = f'of list "{list_name}"' if list_name else ""

        script = f'''
        set output to ""
        tell application "Reminders"
            set allReminders to (every reminder {list_filter} {filter_str})
            repeat with r in allReminders
                set rName to name of r
                set rDue to ""
                try
                    set rDue to (due date of r) as string
                end try
                set rPriority to priority of r
                set output to output & rName
                if rDue is not "" then
                    set output to output & " | due: " & rDue
                end if
                if rPriority > 0 then
                    set output to output & " | priority: " & rPriority
                end if
                set output to output & linefeed
            end repeat
        end tell
        return output
        '''
        output, rc = await self.executor.execute(f"osascript -e '{script}'", timeout=15)
        if rc == 0 and output.strip():
            return f"Reminders:\n\n{output.strip()}"
        elif rc == 0:
            return "No pending reminders."
        return f"Error reading reminders: {output}"

    # ─── Notes ──────────────────────────────────────────────────

    async def create_note(self, title: str, body: str, folder: str = "") -> str:
        """Create a note in Apple Notes."""
        html_body = body.replace("\n", "<br>")
        folder_target = f'folder "{folder}"' if folder else 'default account'

        script = f'''
        tell application "Notes"
            tell {folder_target}
                make new note with properties {{name:"{self._escape(title)}", body:"<h1>{self._escape(title)}</h1><br>{self._escape(html_body)}"}}
            end tell
        end tell
        return "OK"
        '''
        output, rc = await self.executor.execute(f"osascript -e '{script}'", timeout=15)
        if rc == 0:
            return f"Note created: {title}"
        return f"Error creating note: {output}"

    async def search_notes(self, query: str) -> str:
        """Search notes by title/content."""
        script = f'''
        set output to ""
        tell application "Notes"
            set matchingNotes to (every note whose name contains "{self._escape(query)}")
            repeat with n in matchingNotes
                set output to output & name of n & " | " & (modification date of n as string) & linefeed
            end repeat
        end tell
        return output
        '''
        output, rc = await self.executor.execute(f"osascript -e '{script}'", timeout=15)
        if rc == 0 and output.strip():
            return f"Notes matching '{query}':\n\n{output.strip()}"
        elif rc == 0:
            return f"No notes found matching '{query}'."
        return f"Error searching notes: {output}"

    # ─── Contacts ───────────────────────────────────────────────

    async def search_contacts(self, query: str) -> str:
        """Search contacts."""
        script = f'''
        set output to ""
        tell application "Contacts"
            set matchingPeople to (every person whose name contains "{self._escape(query)}")
            repeat with p in matchingPeople
                set pName to name of p
                set pPhone to ""
                set pEmail to ""
                try
                    set pPhone to value of first phone of p
                end try
                try
                    set pEmail to value of first email of p
                end try
                set output to output & pName
                if pPhone is not "" then
                    set output to output & " | " & pPhone
                end if
                if pEmail is not "" then
                    set output to output & " | " & pEmail
                end if
                set output to output & linefeed
            end repeat
        end tell
        return output
        '''
        output, rc = await self.executor.execute(f"osascript -e '{script}'", timeout=15)
        if rc == 0 and output.strip():
            return f"Contacts matching '{query}':\n\n{output.strip()}"
        elif rc == 0:
            return f"No contacts found matching '{query}'."
        return f"Error searching contacts: {output}"

    # ─── Helpers ────────────────────────────────────────────────

    def _escape(self, text: str) -> str:
        """Escape text for AppleScript strings."""
        return text.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")

    def _parse_datetime(self, date_str: str, time_str: str = "") -> Optional[datetime]:
        """Parse Russian/English date+time strings into datetime."""
        now = datetime.now()

        # Normalize
        d = date_str.lower().strip()
        t = time_str.strip() if time_str else ""

        # Relative dates
        if d in ("сегодня", "today", ""):
            base = now.date()
        elif d in ("завтра", "tomorrow"):
            base = (now + timedelta(days=1)).date()
        elif d in ("послезавтра", "day after tomorrow"):
            base = (now + timedelta(days=2)).date()
        elif d in ("вчера", "yesterday"):
            base = (now - timedelta(days=1)).date()
        else:
            # Day of week
            days_ru = {"понедельник": 0, "вторник": 1, "среда": 2, "среду": 2,
                       "четверг": 3, "пятница": 4, "пятницу": 4, "суббота": 5,
                       "субботу": 5, "воскресенье": 6, "воскресень": 6}
            days_en = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                       "friday": 4, "saturday": 5, "sunday": 6}

            found_day = None
            for name, dow in {**days_ru, **days_en}.items():
                if name in d:
                    found_day = dow
                    break

            if found_day is not None:
                current_dow = now.weekday()
                diff = (found_day - current_dow) % 7
                if diff == 0:
                    diff = 7  # next week
                base = (now + timedelta(days=diff)).date()
            else:
                # Try parsing various date formats
                for fmt in ("%d.%m.%Y", "%d.%m", "%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%d %B"):
                    try:
                        parsed = datetime.strptime(d, fmt)
                        if parsed.year == 1900:
                            parsed = parsed.replace(year=now.year)
                        base = parsed.date()
                        break
                    except ValueError:
                        continue
                else:
                    return None

        # Parse time
        hour, minute = 9, 0  # default 9:00
        if t:
            # "14:30", "14.30", "2pm", "14 30"
            time_match = re.match(r'(\d{1,2})[:\.\s]?(\d{2})?(?:\s*(am|pm))?', t, re.IGNORECASE)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                ampm = time_match.group(3)
                if ampm:
                    if ampm.lower() == "pm" and hour < 12:
                        hour += 12
                    elif ampm.lower() == "am" and hour == 12:
                        hour = 0
        else:
            # Try to extract time from date_str itself
            time_in_date = re.search(r'(?:в|at|@)\s*(\d{1,2})[:\.]?(\d{2})?', date_str, re.IGNORECASE)
            if time_in_date:
                hour = int(time_in_date.group(1))
                minute = int(time_in_date.group(2) or 0)

        return datetime.combine(base, datetime.min.time().replace(hour=hour, minute=minute))


# ═══════════════════════════════════════════════════════════════
# INTENT DETECTOR — Understands what user wants from context
# ═══════════════════════════════════════════════════════════════

class IntentDetector:
    """
    Detects user intent from natural language.
    "встреча завтра в 10" → CALENDAR_CREATE
    "напомни купить молоко" → REMINDER_CREATE
    "запиши идею: ..." → NOTE_CREATE
    "какие дела на сегодня" → CALENDAR_VIEW + REMINDER_LIST
    """

    CALENDAR_CREATE_PATTERNS = [
        r"(?:создай|добавь|запланируй|поставь|назначь|schedule|create|add)\s*(?:событие|встречу|встреча|event|meeting|звонок|call|совещание)",
        r"(?:встреча|событие|event|meeting|звонок|call|совещание|приём|визит)\s+(?:завтра|сегодня|в\s+\w+|на\s+\w+|\d)",
        r"(?:завтра|сегодня|послезавтра|в\s+понедельник|во?\s+вторник|в\s+среду|в\s+четверг|в\s+пятницу|в\s+субботу|в\s+воскресенье)\s+(?:в\s+\d|at\s+\d).*(?:встреча|событие|звонок|совещание|meeting|event|call)",
        r"(?:запланируй|поставь|назначь)\s+(?:на\s+)?(?:завтра|сегодня|\d)",
    ]

    CALENDAR_VIEW_PATTERNS = [
        r"(?:какие|покажи|что)\s*(?:события|встречи|дела|запланировано|в календаре|events|meetings|planned)",
        r"(?:расписание|schedule|agenda|план)\s*(?:на\s+)?(?:сегодня|завтра|неделю|today|tomorrow|week)?",
        r"(?:что\s+)?(?:у меня|my)\s+(?:сегодня|завтра|на\s+\w+|today|tomorrow)",
        r"(?:calendar|календарь)\s*(?:на|for)?\s*(?:сегодня|завтра|today|tomorrow)?",
    ]

    REMINDER_CREATE_PATTERNS = [
        r"(?:напомни|remind|напоминание|reminder)\s+(?:мне\s+)?(?:о|об|про|about|to)?",
        r"(?:добавь|создай|add|create)\s+(?:напоминание|задачу|reminder|task|todo)",
        r"(?:не забыть|don't forget|нужно|надо|need to)\s+",
        r"(?:купить|позвонить|написать|сделать|отправить|оплатить|забрать|buy|call|write|send|pay|pick up)\s+",
    ]

    REMINDER_LIST_PATTERNS = [
        r"(?:какие|покажи|список|что)\s*(?:напоминани|задач|дел|reminders|tasks|todos)",
        r"(?:мои|my)\s+(?:задачи|дела|напоминания|tasks|todos|reminders)",
        r"(?:что\s+)?(?:нужно|надо)\s+(?:сделать|делать)",
    ]

    NOTE_CREATE_PATTERNS = [
        r"(?:запиши|записать|заметка|заметку|note|создай заметку|save note|write down)\s+",
        r"(?:сохрани|save)\s+(?:это|заметку|мысль|идею|this|note|thought|idea)",
    ]

    NOTE_SEARCH_PATTERNS = [
        r"(?:найди|поиск|search|find)\s+(?:в\s+)?(?:заметк|note)",
        r"(?:покажи|show)\s+(?:заметк|note)",
    ]

    CONTACT_PATTERNS = [
        r"(?:найди|поиск|search|find)\s+(?:контакт|номер|телефон|email|contact|phone|number)",
        r"(?:какой|what)\s+(?:номер|телефон|email|phone|number)\s+(?:у\s+)?",
    ]

    def detect(self, text: str) -> Tuple[IntentType, Dict[str, str]]:
        """Detect intent and extract parameters from natural language."""
        t = text.lower().strip()
        params = {}

        # Calendar create
        for p in self.CALENDAR_CREATE_PATTERNS:
            if re.search(p, t, re.IGNORECASE):
                params = self._extract_event_params(text)
                return IntentType.CALENDAR_CREATE, params

        # Calendar view
        for p in self.CALENDAR_VIEW_PATTERNS:
            if re.search(p, t, re.IGNORECASE):
                params["days"] = "1"
                if any(w in t for w in ("неделю", "week", "7")):
                    params["days"] = "7"
                elif any(w in t for w in ("завтра", "tomorrow")):
                    params["days"] = "2"
                return IntentType.CALENDAR_VIEW, params

        # Reminder create
        for p in self.REMINDER_CREATE_PATTERNS:
            if re.search(p, t, re.IGNORECASE):
                params = self._extract_reminder_params(text)
                return IntentType.REMINDER_CREATE, params

        # Reminder list
        for p in self.REMINDER_LIST_PATTERNS:
            if re.search(p, t, re.IGNORECASE):
                return IntentType.REMINDER_LIST, params

        # Note create
        for p in self.NOTE_CREATE_PATTERNS:
            if re.search(p, t, re.IGNORECASE):
                params = self._extract_note_params(text)
                return IntentType.NOTE_CREATE, params

        # Note search
        for p in self.NOTE_SEARCH_PATTERNS:
            if re.search(p, t, re.IGNORECASE):
                params["query"] = self._extract_search_query(text)
                return IntentType.NOTE_SEARCH, params

        # Contact search
        for p in self.CONTACT_PATTERNS:
            if re.search(p, t, re.IGNORECASE):
                params["query"] = self._extract_search_query(text)
                return IntentType.CONTACT_SEARCH, params

        return IntentType.CHAT, params

    def _extract_event_params(self, text: str) -> Dict[str, str]:
        """Extract event title, date, time from text."""
        params = {"title": "", "date": "", "time": "", "duration": "60", "location": ""}

        # Extract time: "в 10", "в 14:30", "at 3pm"
        time_match = re.search(r'(?:в|at|@)\s*(\d{1,2})[:\.]?(\d{2})?\s*(am|pm)?', text, re.IGNORECASE)
        if time_match:
            h = time_match.group(1)
            m = time_match.group(2) or "00"
            params["time"] = f"{h}:{m}"

        # Extract date
        date_words = {
            "сегодня": "сегодня", "today": "сегодня",
            "завтра": "завтра", "tomorrow": "завтра",
            "послезавтра": "послезавтра",
        }
        for word, val in date_words.items():
            if word in text.lower():
                params["date"] = val
                break

        # Day of week
        if not params["date"]:
            dow_match = re.search(
                r'(?:в\s+)?(понедельник|вторник|среду?|четверг|пятницу?|субботу?|воскресень\w*|'
                r'monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
                text, re.IGNORECASE
            )
            if dow_match:
                params["date"] = dow_match.group(1)

        # Date format: 15.04, 15.04.2026
        date_match = re.search(r'(\d{1,2})[\.\/](\d{1,2})(?:[\.\/](\d{2,4}))?', text)
        if date_match and not params["date"]:
            d, m = date_match.group(1), date_match.group(2)
            y = date_match.group(3) or str(datetime.now().year)
            if len(y) == 2:
                y = "20" + y
            params["date"] = f"{d}.{m}.{y}"

        if not params["date"]:
            params["date"] = "сегодня"

        # Extract duration: "на 2 часа", "30 минут", "1.5h"
        dur_match = re.search(r'(?:на\s+)?(\d+(?:\.\d+)?)\s*(?:час|hour|h|ч)', text, re.IGNORECASE)
        if dur_match:
            params["duration"] = str(int(float(dur_match.group(1)) * 60))
        dur_match2 = re.search(r'(\d+)\s*(?:минут|minute|min|мин)', text, re.IGNORECASE)
        if dur_match2:
            params["duration"] = dur_match2.group(1)

        # Extract location: "в офисе", "at office", "место: ..."
        loc_match = re.search(r'(?:в\s+|at\s+|место:\s*|location:\s*)([^,\.\n]+?)(?:\s+(?:в|at|на|завтра|сегодня|\d)|\s*$)', text, re.IGNORECASE)
        if loc_match:
            loc = loc_match.group(1).strip()
            # Don't use time/date words as location
            skip_words = {"сегодня", "завтра", "послезавтра", "понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"}
            if loc.lower() not in skip_words and len(loc) > 2:
                params["location"] = loc

        # Title: everything that's not date/time/location
        title = text
        # Remove command prefixes
        title = re.sub(r'^(?:создай|добавь|запланируй|поставь|назначь)\s+(?:событие|встречу|meeting|event)\s*:?\s*', '', title, flags=re.IGNORECASE)
        # Remove date/time/duration parts
        for pattern in [r'(?:в|at|@)\s*\d{1,2}[:\.]?\d{0,2}', r'(?:завтра|сегодня|послезавтра|tomorrow|today)',
                        r'(?:на\s+)?\d+\s*(?:час|hour|мин|min)', r'\d{1,2}[\.\/]\d{1,2}(?:[\.\/]\d{2,4})?',
                        r'(?:в\s+)?(?:понедельник|вторник|среду?|четверг|пятницу?|субботу?|воскресень\w*)']:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+', ' ', title).strip(' ,.:;')
        params["title"] = title if title else "Event"

        return params

    def _extract_reminder_params(self, text: str) -> Dict[str, str]:
        """Extract reminder title and due date from text."""
        params = {"title": "", "date": "", "time": ""}

        # Extract time
        time_match = re.search(r'(?:в|at|@|к)\s*(\d{1,2})[:\.]?(\d{2})?', text, re.IGNORECASE)
        if time_match:
            params["time"] = f"{time_match.group(1)}:{time_match.group(2) or '00'}"

        # Extract date
        for word, val in {"сегодня": "сегодня", "завтра": "завтра", "послезавтра": "послезавтра",
                          "today": "сегодня", "tomorrow": "завтра"}.items():
            if word in text.lower():
                params["date"] = val
                break

        # Title: clean up
        title = text
        title = re.sub(r'^(?:напомни|remind|напоминание|добавь задачу|add task|не забыть)\s*(?:мне\s+)?(?:о|об|про|about|to|что)?\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'(?:в|at|@|к)\s*\d{1,2}[:\.]?\d{0,2}', '', title, flags=re.IGNORECASE)
        title = re.sub(r'(?:завтра|сегодня|послезавтра|tomorrow|today)', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+', ' ', title).strip(' ,.:;')
        params["title"] = title if title else "Reminder"

        return params

    def _extract_note_params(self, text: str) -> Dict[str, str]:
        """Extract note title and body."""
        # Remove command prefix
        body = re.sub(r'^(?:запиши|записать|заметка|заметку|note|создай заметку|save note|write down|сохрани)\s*:?\s*', '', text, flags=re.IGNORECASE)

        # Split title and body by first newline or colon
        parts = re.split(r'[\n:]', body, maxsplit=1)
        title = parts[0].strip()[:100]
        note_body = parts[1].strip() if len(parts) > 1 else ""

        return {"title": title or "Note", "body": note_body}

    def _extract_search_query(self, text: str) -> str:
        """Extract search query from text."""
        q = re.sub(r'^(?:найди|поиск|search|find|покажи|show)\s+(?:в\s+)?(?:заметк\w*|контакт\w*|note\w*|contact\w*)\s*:?\s*', '', text, flags=re.IGNORECASE)
        return q.strip() or text.strip()


# ═══════════════════════════════════════════════════════════════
# MOE CLASSIFIER (from ai-router-moe) + ASSISTANT expert
# ═══════════════════════════════════════════════════════════════

class MoEClassifier:
    """Classify queries into expert domains."""

    EXPERT_KEYWORDS = {
        ExpertType.ASSISTANT: [
            "напомни", "remind", "календарь", "calendar", "событие", "event", "встреча", "meeting",
            "заметка", "note", "записать", "запиши", "задача", "task", "todo", "дела",
            "расписание", "schedule", "agenda", "план", "контакт", "contact", "телефон", "phone",
            "будильник", "alarm", "таймер", "timer", "купить", "buy", "позвонить", "call",
            "написать", "оплатить", "pay", "забрать", "pick up", "отправить", "send",
            "не забыть", "don't forget", "нужно", "надо", "need to",
            "icloud", "apple", "siri",
        ],
        ExpertType.SYSADMIN: [
            "сеть", "network", "ip", "dns", "ping", "ssh", "порт", "port", "firewall",
            "роутер", "router", "wifi", "интерфейс", "interface", "ifconfig", "netstat",
            "traceroute", "nmap", "scan", "сканир", "подсеть", "subnet", "vlan",
            "dhcp", "arp", "mac адрес", "bandwidth", "трафик", "vpn", "proxy",
            "nginx", "apache", "сервер", "server", "хост", "host",
            "диск", "disk", "память", "memory", "cpu", "процесс", "process",
            "uptime", "load", "нагрузка", "температур", "temp", "файл", "file",
            "каталог", "directory", "права", "permission", "chmod", "mount",
            "df", "du", "free", "top", "htop", "ps", "kill", "systemctl",
            "service", "daemon", "cron", "лог", "log", "journal",
            "пароль", "password", "пользователь", "user",
        ],
        ExpertType.CODE: [
            "код", "code", "функци", "function", "класс", "class", "python", "javascript",
            "typescript", "rust", "go", "java", "swift", "баг", "bug", "ошибк", "error",
            "debug", "рефактор", "refactor", "тест", "test", "api", "rest", "graphql",
            "база данных", "database", "sql", "postgres", "mysql", "mongo", "redis",
            "git", "commit", "push", "pull", "merge", "branch", "npm", "pip", "cargo",
            "алгоритм", "algorithm",
        ],
        ExpertType.DEVOPS: [
            "docker", "контейнер", "container", "kubernetes", "k8s", "helm",
            "ci/cd", "pipeline", "jenkins", "github actions", "deploy", "деплой",
            "terraform", "ansible", "aws", "gcp", "azure", "cloud", "облак",
            "monitoring", "мониторинг", "prometheus", "grafana", "proxmox", "vm",
            "виртуал", "virtual", "backup", "бэкап", "миграц", "migration",
        ],
        ExpertType.CREATIVE: [
            "напиши текст", "write text", "статья", "article", "блог", "blog",
            "письмо", "letter", "email", "перевод", "translat", "история", "story",
            "сценарий", "script", "маркетинг", "marketing", "презентац", "presentation",
        ],
        ExpertType.ANALYSIS: [
            "анализ", "analysis", "данные", "data", "статистик", "statistic",
            "график", "chart", "визуализ", "visualiz", "отчёт", "report",
            "сравни", "compare", "csv", "excel", "json", "парс", "parse",
        ],
    }

    EXEC_PATTERNS = [
        (r"(?:какой|какая|каков|покажи|выведи|узнай).*(?:ip|адрес|address)", "ip addr show; ifconfig 2>/dev/null || true"),
        (r"(?:сканируй|scan|просканируй|найди.*(?:хост|устройств|device))", "NETWORK_SCAN"),
        (r"(?:какой|покажи|выведи).*(?:dns|днс|nameserver)", "cat /etc/resolv.conf 2>/dev/null; scutil --dns 2>/dev/null | head -20 || true"),
        (r"(?:какой|покажи).*(?:маршрут|route|gateway|шлюз)", "netstat -rn | head -15"),
        (r"(?:сколько|покажи|выведи).*(?:памят|memory|ram|озу)", "free -h 2>/dev/null || vm_stat 2>/dev/null; sysctl hw.memsize 2>/dev/null || true"),
        (r"(?:сколько|покажи|выведи).*(?:диск|disk|место|storage)", "df -h"),
        (r"(?:какой|покажи).*(?:процессор|cpu|проц)", "sysctl -n machdep.cpu.brand_string 2>/dev/null || lscpu 2>/dev/null"),
        (r"(?:покажи|выведи|какие).*(?:процесс|process)", "ps aux | head -20"),
        (r"(?:покажи|выведи|какие).*(?:порт|port).*(?:открыт|listen|слуша)", "lsof -i -P -n | grep LISTEN 2>/dev/null || ss -tlnp 2>/dev/null"),
        (r"(?:docker|контейнер).*(?:покажи|список|list|ps)", "docker ps -a 2>/dev/null || echo 'Docker not available'"),
        (r"(?:uptime|аптайм|сколько.*работает)", "uptime"),
        (r"(?:hostname|имя.*(?:хост|машин|компьютер))", "hostname; uname -a"),
        (r"(?:температур|temp|thermal)", "sudo powermetrics --samplers smc -n 1 2>/dev/null | grep -i temp || echo 'No temp sensors'"),
        (r"(?:в какой.*сети|какая.*сеть|network.*info)", "ifconfig 2>/dev/null; echo '---'; netstat -rn 2>/dev/null | head -10"),
    ]

    def classify(self, query: str) -> Tuple[ExpertType, float, Optional[str]]:
        q = query.lower().strip()

        # Check exec patterns first
        for pattern, cmd in self.EXEC_PATTERNS:
            if re.search(pattern, q, re.IGNORECASE):
                return ExpertType.SYSADMIN, 0.95, cmd

        # Keyword scoring
        scores = {}
        for expert, keywords in self.EXPERT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q)
            if score > 0:
                scores[expert] = score

        if not scores:
            return ExpertType.GENERAL, 0.3, None

        best = max(scores, key=scores.get)
        total = sum(scores.values())
        confidence = scores[best] / max(total, 1)

        return best, min(confidence, 0.95), None


# ═══════════════════════════════════════════════════════════════
# RESPONSE POST-PROCESSOR (from avoid-ai-writing)
# ═══════════════════════════════════════════════════════════════

class ResponseProcessor:
    REPLACEMENTS = {
        "Certainly!": "", "Of course!": "", "Absolutely!": "",
        "Great question!": "", "That's a great question!": "",
        "I'd be happy to": "I'll", "I'd be glad to": "I'll",
        "Let me know if you need anything else": "",
        "Let me know if you have any questions": "",
        "Feel free to ask": "", "Hope this helps!": "",
        "Happy to help!": "", "Is there anything else": "",
        "Don't hesitate to": "",
    }

    REFUSAL_PATTERNS = [
        r"(?:я|i)\s*(?:не могу|cannot|can't|unable)",
        r"(?:у меня нет|i don't have)\s*(?:доступа|access)",
        r"(?:я|i)\s*(?:текстовый|text-based)\s*(?:ии|ai|ассистент|assistant)",
        r"к сожалению.*не могу.*выполнить",
        r"как (?:ии|искусственный интеллект).*не могу",
    ]

    def process(self, text: str) -> str:
        for old, new in self.REPLACEMENTS.items():
            text = text.replace(old, new)
        return re.sub(r'\n{3,}', '\n\n', text).strip()

    def is_refusal(self, text: str) -> bool:
        return any(re.search(p, text.lower(), re.IGNORECASE) for p in self.REFUSAL_PATTERNS)


# ═══════════════════════════════════════════════════════════════
# OLLAMA CLIENT
# ═══════════════════════════════════════════════════════════════

class OllamaClient:
    PREFERRED_MODELS = [
        "qwen3.5-27b-hf", "qwen2.5:14b", "qwen2.5:7b",
        "llama3.1:8b", "gemma2:9b", "mistral:7b",
    ]

    def __init__(self):
        self.available_models: List[str] = []
        self.base_url = OLLAMA_HOST

    async def check(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-m", "5", f"{self.base_url}/api/tags",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0 and stdout.strip():
                data = json.loads(stdout)
                self.available_models = [m["name"] for m in data.get("models", [])]
                return len(self.available_models) > 0
        except Exception as e:
            log.error(f"Ollama check failed: {e}")
        return False

    def pick_model(self, expert: ExpertType) -> Optional[str]:
        for m in self.PREFERRED_MODELS:
            for avail in self.available_models:
                if m in avail or avail.startswith(m.split(":")[0]):
                    return avail
        return self.available_models[0] if self.available_models else None

    async def generate(self, model: str, prompt: str, system: str = "",
                       temperature: float = 0.7) -> Optional[str]:
        payload = {
            "model": model, "prompt": prompt, "system": system,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": 4096},
        }
        try:
            import urllib.request
            req_data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{self.base_url}/api/generate", data=req_data,
                headers={"Content-Type": "application/json"}, method="POST"
            )
            loop = asyncio.get_event_loop()
            response_text = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT).read().decode()),
                timeout=OLLAMA_TIMEOUT + 10
            )
            data = json.loads(response_text)
            return data.get("response", "")
        except asyncio.TimeoutError:
            log.warning(f"Ollama timeout for model {model}")
            return None
        except Exception as e:
            log.error(f"Ollama generate error: {e}")
            return None


# ═══════════════════════════════════════════════════════════════
# CLAUDE CLIENT
# ═══════════════════════════════════════════════════════════════

class ClaudeClient:
    def __init__(self, cost_tracker: CostTracker):
        self.api_key = CLAUDE_API_KEY
        self.cost_tracker = cost_tracker
        self.ok = False

    async def check(self) -> bool:
        if not self.api_key:
            return False
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({
                    "model": CLAUDE_FALLBACK_MODEL, "max_tokens": 10,
                    "messages": [{"role": "user", "content": "hi"}]
                }).encode(),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                }, method="POST"
            )
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=15).read())
            self.ok = True
            return True
        except Exception as e:
            log.error(f"Claude check failed: {e}")
            self.ok = False
            return False

    async def generate(self, prompt: str, system: str = "",
                       model: str = None, max_tokens: int = 4096) -> Optional[str]:
        if not self.api_key:
            return None
        can_spend, msg = self.cost_tracker.check_limits()
        if not can_spend:
            log.warning(f"Cost limit: {msg}")
            return None

        model = model or CLAUDE_MODEL
        try:
            import urllib.request
            payload = {"model": model, "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": prompt}]}
            if system:
                payload["system"] = system

            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                }, method="POST"
            )
            loop = asyncio.get_event_loop()
            resp = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=120).read().decode()),
                timeout=130
            )
            data = json.loads(resp)
            text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
            usage = data.get("usage", {})
            self.cost_tracker.add(model, usage.get("input_tokens", 0), usage.get("output_tokens", 0))
            return text
        except Exception as e:
            log.error(f"Claude generate error: {e}")
            if model != CLAUDE_FALLBACK_MODEL:
                return await self.generate(prompt, system, CLAUDE_FALLBACK_MODEL, max_tokens)
            return None


# ═══════════════════════════════════════════════════════════════
# COMMAND EXECUTOR
# ═══════════════════════════════════════════════════════════════

class CommandExecutor:
    def __init__(self):
        self.is_local = self._check_local()

    def _check_local(self) -> bool:
        try:
            result = subprocess.run(["hostname"], capture_output=True, text=True, timeout=5)
            hostname = result.stdout.strip().lower()
            return "mac" in hostname or "ilea" in hostname
        except Exception:
            return False

    async def execute(self, cmd: str, timeout: int = 30) -> Tuple[str, int]:
        if self.is_local:
            return await self._exec_local(cmd, timeout)
        return await self._exec_ssh(cmd, timeout)

    async def _exec_local(self, cmd: str, timeout: int) -> Tuple[str, int]:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode(errors="replace")
            if stderr:
                output += "\n" + stderr.decode(errors="replace")
            return output.strip()[:4000], proc.returncode or 0
        except asyncio.TimeoutError:
            return f"[TIMEOUT after {timeout}s]", 124
        except Exception as e:
            return f"[ERROR] {e}", 1

    async def _exec_ssh(self, cmd: str, timeout: int) -> Tuple[str, int]:
        ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p {MAC_PORT} {MAC_USER}@{MAC_HOST} '{cmd}'"
        try:
            proc = await asyncio.create_subprocess_shell(
                ssh_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 15)
            output = stdout.decode(errors="replace")
            if stderr:
                err = stderr.decode(errors="replace")
                if err and "Warning" not in err:
                    output += "\n" + err
            return output.strip()[:4000], proc.returncode or 0
        except asyncio.TimeoutError:
            return f"[TIMEOUT after {timeout}s]", 124
        except Exception as e:
            return f"[SSH ERROR] {e}", 1

    async def network_scan(self) -> str:
        commands = [
            ("Network Info", "ifconfig 2>/dev/null | grep -E 'inet |flags' | head -20"),
            ("Default Route", "netstat -rn 2>/dev/null | grep default | head -5"),
            ("DNS", "cat /etc/resolv.conf 2>/dev/null; scutil --dns 2>/dev/null | grep nameserver | sort -u | head -10"),
            ("Ping Scan", "(fping -a -g $(ifconfig 2>/dev/null | grep 'inet ' | grep -v 127 | head -1 | awk '{print $2}' | sed 's/\\.[0-9]*$/.0\\/24/') 2>/dev/null || echo 'fping not available') | head -60"),
            ("ARP Table", "arp -an 2>/dev/null | head -30"),
            ("Listening Ports", "lsof -i -P -n 2>/dev/null | grep LISTEN | head -20"),
        ]
        results = []
        for title, cmd in commands:
            output, rc = await self.execute(cmd, timeout=30)
            results.append(f"=== {title} ===\n{output}")
        return "\n\n".join(results)


# ═══════════════════════════════════════════════════════════════
# SCHEDULER (Heartbeat from Paperclip)
# ═══════════════════════════════════════════════════════════════

class TaskScheduler:
    def __init__(self):
        self.tasks: List[Dict] = []
        self.counter = 0
        self._load()

    def _load(self):
        path = DATA_DIR / "scheduled_tasks.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.tasks = data.get("tasks", [])
                self.counter = data.get("counter", 0)
            except Exception:
                pass

    def _save(self):
        path = DATA_DIR / "scheduled_tasks.json"
        path.write_text(json.dumps({"tasks": self.tasks, "counter": self.counter}, indent=2))

    def add(self, name: str, command: str, interval_min: int, chat_id: int) -> str:
        self.counter += 1
        tid = f"SCH-{self.counter:03d}"
        self.tasks.append({
            "id": tid, "name": name, "command": command,
            "interval_min": interval_min, "chat_id": chat_id,
            "last_run": "", "created": datetime.now().isoformat(),
        })
        self._save()
        return tid

    def remove(self, task_id: str) -> bool:
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        self._save()
        return len(self.tasks) < before

    def get_due_tasks(self) -> List[Dict]:
        now = datetime.now()
        due = []
        for task in self.tasks:
            last = datetime.fromisoformat(task["last_run"]) if task["last_run"] else datetime.min
            if (now - last).total_seconds() >= task["interval_min"] * 60:
                task["last_run"] = now.isoformat()
                due.append(task)
        if due:
            self._save()
        return due

    def list_tasks(self) -> str:
        if not self.tasks:
            return "No scheduled tasks."
        lines = ["Scheduled Tasks:\n"]
        for t in self.tasks:
            lines.append(f"  [{t['id']}] {t['name']} — every {t['interval_min']}m\n    cmd: {t['command'][:60]}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# VOICE TRANSCRIBER
# ═══════════════════════════════════════════════════════════════

class VoiceTranscriber:
    async def transcribe(self, file_path: str) -> Optional[str]:
        # Try whisper CLI
        for cmd in ["whisper", "/opt/homebrew/bin/whisper"]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    cmd, file_path, "--language", "ru", "--model", "base",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
                if proc.returncode == 0:
                    return stdout.decode().strip()
            except Exception:
                continue

        # Try mlx-whisper
        try:
            proc = await asyncio.create_subprocess_shell(
                f'/opt/homebrew/bin/python3 -c "import mlx_whisper; r=mlx_whisper.transcribe(\'{file_path}\', language=\'ru\'); print(r[\'text\'])"',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode == 0:
                return stdout.decode().strip()
        except Exception:
            pass

        return None


# ═══════════════════════════════════════════════════════════════
# CONVERSATION MEMORY (from NanoBot — Two-Stage)
# ═══════════════════════════════════════════════════════════════

class ConversationMemory:
    """Short-term (per session) + Long-term (persistent) memory."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.short_term: List[Dict] = []  # last N messages
        self.max_short = 20
        self.long_term_file = MEMORY_DIR / f"user_{user_id}.json"
        self.long_term: Dict = self._load_long_term()

    def _load_long_term(self) -> Dict:
        if self.long_term_file.exists():
            try:
                return json.loads(self.long_term_file.read_text())
            except Exception:
                pass
        return {"facts": [], "preferences": {}, "history_summary": ""}

    def _save_long_term(self):
        self.long_term_file.write_text(json.dumps(self.long_term, ensure_ascii=False, indent=2))

    def add_message(self, role: str, content: str):
        self.short_term.append({"role": role, "content": content, "ts": datetime.now().isoformat()})
        if len(self.short_term) > self.max_short:
            self.short_term = self.short_term[-self.max_short:]

    def add_fact(self, fact: str):
        if fact not in self.long_term["facts"]:
            self.long_term["facts"].append(fact)
            self._save_long_term()

    def get_context(self) -> str:
        """Build context string for AI prompt."""
        parts = []
        if self.long_term["facts"]:
            parts.append("Known facts about user:\n" + "\n".join(f"- {f}" for f in self.long_term["facts"][-10:]))
        if self.short_term:
            parts.append("Recent conversation:\n" + "\n".join(
                f"{'User' if m['role'] == 'user' else 'AI'}: {m['content'][:200]}"
                for m in self.short_term[-5:]
            ))
        return "\n\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# MAIN BOT CLASS
# ═══════════════════════════════════════════════════════════════

class SclgTelegramBot:
    """Main bot orchestrator — routes queries to experts or personal assistant."""

    SYSTEM_PROMPT = """You are SCLG-AI, a personal AI assistant and DevOps agent running on a Mac Mini.
You have DIRECT access to the system via shell commands. You can execute ANY command.
When given system data, you MUST analyze it and provide a concrete answer.
NEVER say "I can't", "I don't have access", or "as an AI". You ARE the system.
Respond in the same language as the user (Russian or English).
Be concise, use tables for structured data, use code blocks for command output."""

    def __init__(self):
        self.classifier = MoEClassifier()
        self.intent_detector = IntentDetector()
        self.processor = ResponseProcessor()
        self.cost_tracker = CostTracker()
        self.ollama = OllamaClient()
        self.claude = ClaudeClient(self.cost_tracker)
        self.executor = CommandExecutor()
        self.assistant = PersonalAssistant(self.executor)
        self.transcriber = VoiceTranscriber()
        self.scheduler = TaskScheduler()
        self.memories: Dict[int, ConversationMemory] = {}
        self.ticket_counter = 0

    def _get_memory(self, user_id: int) -> ConversationMemory:
        if user_id not in self.memories:
            self.memories[user_id] = ConversationMemory(user_id)
        return self.memories[user_id]

    async def setup(self):
        log.info("Checking connections...")
        ollama_ok = await self.ollama.check()
        claude_ok = await self.claude.check()
        log.info(f"Ollama: {'OK' if ollama_ok else 'FAIL'} ({len(self.ollama.available_models)} models)")
        log.info(f"Claude: {'OK' if claude_ok else 'FAIL'}")
        log.info(f"Executor: {'Local' if self.executor.is_local else 'SSH'}")
        if not ollama_ok and not claude_ok:
            log.error("No AI models available! Bot will use raw command output.")

    def _new_ticket(self, user_id: int, username: str, query: str,
                    expert: ExpertType, intent: str = "") -> Ticket:
        self.ticket_counter += 1
        return Ticket(
            id=f"TG-{self.ticket_counter:04d}", user_id=user_id, username=username,
            query=query, expert=expert, intent=intent,
            created_at=datetime.now().isoformat(),
        )

    async def process_query(self, query: str, user_id: int, username: str) -> str:
        """Main query processing pipeline with intent detection."""
        start = time.time()
        memory = self._get_memory(user_id)
        memory.add_message("user", query)

        # 1. Detect personal assistant intent FIRST
        intent, params = self.intent_detector.detect(query)

        # 2. If it's a personal assistant intent, handle directly
        if intent != IntentType.CHAT and intent != IntentType.SYSTEM_CMD:
            result = await self._handle_assistant_intent(intent, params, query, user_id, username)
            if result:
                memory.add_message("assistant", result)
                return result

        # 3. Classify for system/DevOps queries
        expert, confidence, direct_cmd = self.classifier.classify(query)
        ticket = self._new_ticket(user_id, username, query, expert, intent.value)

        # 4. Execute commands if needed (Execute-First)
        exec_data = ""
        if direct_cmd:
            if direct_cmd == "NETWORK_SCAN":
                exec_data = await self.executor.network_scan()
            else:
                output, rc = await self.executor.execute(direct_cmd)
                exec_data = output
            ticket.commands_run.append(direct_cmd)

        # 5. Build prompt with context
        context = memory.get_context()
        if exec_data:
            prompt = (
                f"User asked: {query}\n\n"
                f"System data collected:\n```\n{exec_data}\n```\n\n"
                f"{context}\n\n"
                f"Analyze the data above and give a concrete answer. Use tables for IP/MAC/ports."
            )
        else:
            prompt = f"{context}\n\nUser: {query}" if context else query

        # 6. Get AI response
        response = await self._get_ai_response(prompt, expert, ticket)

        # 7. Post-process
        response = self.processor.process(response)

        # 8. Refusal fallback
        if self.processor.is_refusal(response) and exec_data:
            response = f"Command output:\n\n```\n{exec_data}\n```"

        # 9. Save
        ticket.response = response[:500]
        ticket.duration_s = round(time.time() - start, 1)
        ticket.status = "completed"
        ticket.save()
        memory.add_message("assistant", response[:500])

        return response

    async def _handle_assistant_intent(self, intent: IntentType, params: Dict,
                                        query: str, user_id: int, username: str) -> Optional[str]:
        """Handle personal assistant intents."""
        try:
            if intent == IntentType.CALENDAR_CREATE:
                return await self.assistant.create_calendar_event(
                    title=params.get("title", "Event"),
                    date_str=params.get("date", "сегодня"),
                    time_str=params.get("time", ""),
                    duration_min=int(params.get("duration", "60")),
                    location=params.get("location", ""),
                )

            elif intent == IntentType.CALENDAR_VIEW:
                days = int(params.get("days", "1"))
                return await self.assistant.get_calendar_events(days=days)

            elif intent == IntentType.REMINDER_CREATE:
                return await self.assistant.create_reminder(
                    title=params.get("title", "Reminder"),
                    due_date=params.get("date", ""),
                    due_time=params.get("time", ""),
                )

            elif intent == IntentType.REMINDER_LIST:
                return await self.assistant.list_reminders()

            elif intent == IntentType.NOTE_CREATE:
                return await self.assistant.create_note(
                    title=params.get("title", "Note"),
                    body=params.get("body", ""),
                )

            elif intent == IntentType.NOTE_SEARCH:
                return await self.assistant.search_notes(params.get("query", ""))

            elif intent == IntentType.CONTACT_SEARCH:
                return await self.assistant.search_contacts(params.get("query", ""))

        except Exception as e:
            log.error(f"Assistant intent error: {e}", exc_info=True)
            return f"Error: {e}"

        return None

    async def _get_ai_response(self, prompt: str, expert: ExpertType, ticket: Ticket) -> str:
        """Try Ollama first, then Claude fallback."""
        # Try Ollama
        if self.ollama.available_models:
            model = self.ollama.pick_model(expert)
            if model:
                ticket.model_used = model
                response = await self.ollama.generate(model, prompt, self.SYSTEM_PROMPT)
                if response and not self.processor.is_refusal(response):
                    return response
                log.warning(f"Ollama {model} failed/refused, trying Claude")

        # Claude fallback
        if self.claude.ok or self.claude.api_key:
            ticket.model_used = CLAUDE_MODEL
            response = await self.claude.generate(prompt, self.SYSTEM_PROMPT)
            if response:
                return response

        return "AI models unavailable. Raw data:\n\n" + prompt

    async def handle_message(self, update: dict, bot) -> None:
        """Handle incoming Telegram message."""
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        username = message.get("from", {}).get("username", "unknown")
        text = message.get("text", "")
        voice = message.get("voice")

        if not chat_id:
            return

        # Access control — auto-add first user as admin
        if ALLOWED_USERS and user_id not in ALLOWED_USERS and user_id not in ADMIN_USERS:
            if not ADMIN_USERS:
                ADMIN_USERS.add(user_id)
                ALLOWED_USERS.add(user_id)
                log.info(f"Auto-added first user as admin: {user_id} ({username})")
            else:
                await bot.send_message(chat_id, "Access denied. Contact admin.")
                return

        # Auto-add first user
        if not ADMIN_USERS:
            ADMIN_USERS.add(user_id)
            ALLOWED_USERS.add(user_id)

        # Typing indicator
        await bot.send_chat_action(chat_id, "typing")

        # Voice messages
        if voice:
            status_msg = await bot.send_message(chat_id, "Transcribing voice...")
            try:
                file_info = await bot.get_file(voice["file_id"])
                file_path = VOICE_DIR / f"{voice['file_id']}.ogg"
                await bot.download_file(file_info["file_path"], str(file_path))
                text = await self.transcriber.transcribe(str(file_path))
                if text:
                    await bot.edit_message(chat_id, status_msg["message_id"],
                                           f"Heard: _{text}_\n\nProcessing...")
                else:
                    await bot.edit_message(chat_id, status_msg["message_id"],
                                           "Could not transcribe voice message.")
                    return
            except Exception as e:
                await bot.edit_message(chat_id, status_msg["message_id"], f"Voice error: {e}")
                return

        if not text:
            return

        # Slash commands
        if text.startswith("/"):
            response = await self._handle_command(text, chat_id, user_id, username, bot)
            if response:
                await self._send_long_message(bot, chat_id, response)
            return

        # Status message with intent/expert info
        intent, _ = self.intent_detector.detect(text)
        expert, conf, _ = self.classifier.classify(text)

        # Choose display based on intent
        if intent not in (IntentType.CHAT, IntentType.SYSTEM_CMD):
            intent_display = intent.value.replace("_", " ").title()
            status_text = f"Working: {intent_display}..."
        else:
            status_text = f"Working: `{expert.value}` expert ({conf:.0%})"

        status_msg = await bot.send_message(chat_id, status_text)

        # Keep sending typing action during processing
        typing_task = asyncio.create_task(self._keep_typing(bot, chat_id))

        try:
            response = await self.process_query(text, user_id, username)
            typing_task.cancel()
            await bot.delete_message(chat_id, status_msg["message_id"])
            await self._send_long_message(bot, chat_id, response)
        except Exception as e:
            typing_task.cancel()
            log.error(f"Error processing query: {e}", exc_info=True)
            await bot.edit_message(chat_id, status_msg["message_id"], f"Error: {e}")

    async def _keep_typing(self, bot, chat_id: int):
        """Keep sending typing indicator while processing."""
        try:
            while True:
                await bot.send_chat_action(chat_id, "typing")
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass

    async def _handle_command(self, text: str, chat_id: int, user_id: int,
                              username: str, bot) -> Optional[str]:
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/start":
            return (
                f"SCLG-AI Bot v{VERSION} — Personal Assistant + DevOps Agent\n\n"
                f"I run on your Mac Mini. I can:\n"
                f"  Create calendar events, reminders, notes\n"
                f"  Execute system commands, scan networks\n"
                f"  Answer questions using AI (Ollama/Claude)\n\n"
                f"Just type naturally:\n"
                f"  'встреча завтра в 10 с Петром'\n"
                f"  'напомни купить молоко'\n"
                f"  'какие события на сегодня'\n"
                f"  'просканируй сеть'\n\n"
                f"Commands: /help /status /scan /exec /calendar /reminders /notes"
            )

        elif cmd == "/help":
            return (
                f"SCLG-AI Bot v{VERSION}\n\n"
                f"Personal Assistant:\n"
                f"  /calendar [days] — View events (default: today)\n"
                f"  /reminders — List pending reminders\n"
                f"  /notes search <query> — Search notes\n"
                f"  /contacts <name> — Search contacts\n\n"
                f"System:\n"
                f"  /status — Bot & system status\n"
                f"  /scan — Full network scan\n"
                f"  /exec <cmd> — Execute shell command\n"
                f"  /models — List AI models\n"
                f"  /costs — API cost summary\n\n"
                f"Scheduling:\n"
                f"  /schedule add <name> <interval_min> <command>\n"
                f"  /schedule list | remove <id>\n\n"
                f"Or just type naturally — AI understands context!"
            )

        elif cmd == "/status":
            ollama_ok = await self.ollama.check()
            return (
                f"SCLG-AI Bot v{VERSION}\n"
                f"Ollama: {'OK' if ollama_ok else 'FAIL'} ({len(self.ollama.available_models)} models)\n"
                f"Claude: {'OK' if self.claude.ok else 'FAIL'}\n"
                f"Executor: {'Local' if self.executor.is_local else 'SSH'}\n"
                f"Tickets: {self.ticket_counter}\n"
                f"Scheduled: {len(self.scheduler.tasks)}\n\n"
                f"{self.cost_tracker.summary()}"
            )

        elif cmd == "/scan":
            await bot.send_message(chat_id, "Scanning network...")
            await bot.send_chat_action(chat_id, "typing")
            result = await self.executor.network_scan()
            return f"Network Scan:\n\n```\n{result[:3500]}\n```"

        elif cmd == "/exec":
            if not args:
                return "Usage: /exec <command>"
            if user_id not in ADMIN_USERS and ADMIN_USERS:
                return "Admin only."
            await bot.send_chat_action(chat_id, "typing")
            output, rc = await self.executor.execute(args, timeout=30)
            return f"```\n$ {args}\n{output}\n\nExit: {rc}\n```"

        elif cmd == "/calendar":
            days = int(args) if args and args.isdigit() else 1
            return await self.assistant.get_calendar_events(days=days)

        elif cmd == "/reminders":
            return await self.assistant.list_reminders()

        elif cmd == "/notes":
            if args:
                sub = args.split(maxsplit=1)
                if sub[0] == "search" and len(sub) > 1:
                    return await self.assistant.search_notes(sub[1])
                return await self.assistant.search_notes(args)
            return "Usage: /notes search <query>"

        elif cmd == "/contacts":
            if args:
                return await self.assistant.search_contacts(args)
            return "Usage: /contacts <name>"

        elif cmd == "/models":
            await self.ollama.check()
            lines = ["Available Models:\n"]
            for m in self.ollama.available_models:
                lines.append(f"  - {m}")
            if self.claude.ok:
                lines.append(f"\nClaude: {CLAUDE_MODEL}")
            return "\n".join(lines) if len(lines) > 1 else "No models available."

        elif cmd == "/costs":
            return self.cost_tracker.summary()

        elif cmd == "/schedule":
            sub_parts = args.split(maxsplit=3) if args else []
            if not sub_parts or sub_parts[0] == "list":
                return self.scheduler.list_tasks()
            elif sub_parts[0] == "add" and len(sub_parts) >= 4:
                try:
                    interval = int(sub_parts[2])
                except ValueError:
                    return "Interval must be a number (minutes)."
                tid = self.scheduler.add(sub_parts[1], sub_parts[3], interval, chat_id)
                return f"Scheduled [{tid}]: {sub_parts[1]} every {interval}m"
            elif sub_parts[0] == "remove" and len(sub_parts) >= 2:
                return "Removed." if self.scheduler.remove(sub_parts[1]) else "Not found."
            return "Usage: /schedule [add|list|remove]"

        elif cmd == "/allow":
            if user_id not in ADMIN_USERS and ADMIN_USERS:
                return "Admin only."
            if args:
                try:
                    ALLOWED_USERS.add(int(args.strip()))
                    return f"User {args} added."
                except ValueError:
                    return "Invalid user ID."
            return "Usage: /allow <user_id>"

        elif cmd == "/id":
            return f"Your ID: `{user_id}`\nChat: `{chat_id}`"

        return None

    async def _send_long_message(self, bot, chat_id: int, text: str):
        """Send message, splitting if too long."""
        if not text:
            text = "(empty response)"
        if len(text) <= 4000:
            await bot.send_message(chat_id, text, parse_mode="Markdown")
        else:
            for i in range(0, len(text), 4000):
                chunk = text[i:i+4000]
                await bot.send_message(chat_id, chunk)
                await asyncio.sleep(0.3)

    async def run_scheduler_loop(self, bot):
        """Background loop for scheduled tasks."""
        while True:
            try:
                due_tasks = self.scheduler.get_due_tasks()
                for task in due_tasks:
                    log.info(f"Running scheduled: {task['name']}")
                    output, rc = await self.executor.execute(task["command"], timeout=30)
                    result = f"Scheduled: {task['name']}\n```\n{output[:3000]}\n```"
                    await bot.send_message(task["chat_id"], result, parse_mode="Markdown")
            except Exception as e:
                log.error(f"Scheduler error: {e}")
            await asyncio.sleep(30)


# ═══════════════════════════════════════════════════════════════
# TELEGRAM API WRAPPER
# ═══════════════════════════════════════════════════════════════

class TelegramAPI:
    """Lightweight Telegram Bot API wrapper using urllib."""

    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0

    def _request(self, method: str, data: dict = None) -> dict:
        import urllib.request
        url = f"{self.base_url}/{method}"
        if data:
            req = urllib.request.Request(
                url, data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"}, method="POST"
            )
        else:
            req = urllib.request.Request(url)
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            return json.loads(resp.read().decode())
        except Exception as e:
            log.error(f"TG API error {method}: {e}")
            return {"ok": False, "error": str(e)}

    async def _async_request(self, method: str, data: dict = None) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._request(method, data))

    async def get_updates(self, timeout: int = 30) -> List[dict]:
        result = await self._async_request("getUpdates", {
            "offset": self.offset, "timeout": timeout, "allowed_updates": ["message"]
        })
        updates = result.get("result", [])
        if updates:
            self.offset = updates[-1]["update_id"] + 1
        return updates

    async def send_message(self, chat_id: int, text: str, parse_mode: str = None) -> dict:
        data = {"chat_id": chat_id, "text": text}
        if parse_mode:
            data["parse_mode"] = parse_mode
        result = await self._async_request("sendMessage", data)
        if not result.get("ok") and parse_mode:
            # Retry without parse_mode if Markdown fails
            data.pop("parse_mode", None)
            result = await self._async_request("sendMessage", data)
        return result.get("result", {})

    async def edit_message(self, chat_id: int, message_id: int, text: str,
                           parse_mode: str = None) -> dict:
        data = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if parse_mode:
            data["parse_mode"] = parse_mode
        result = await self._async_request("editMessageText", data)
        return result.get("result", {})

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        result = await self._async_request("deleteMessage", {
            "chat_id": chat_id, "message_id": message_id
        })
        return result.get("ok", False)

    async def send_chat_action(self, chat_id: int, action: str = "typing") -> bool:
        result = await self._async_request("sendChatAction", {
            "chat_id": chat_id, "action": action
        })
        return result.get("ok", False)

    async def get_file(self, file_id: str) -> dict:
        result = await self._async_request("getFile", {"file_id": file_id})
        return result.get("result", {})

    async def download_file(self, file_path: str, save_to: str):
        import urllib.request
        url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: urllib.request.urlretrieve(url, save_to))

    async def get_me(self) -> dict:
        result = await self._async_request("getMe")
        return result.get("result", {})


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

async def main():
    """Main bot loop."""
    print(f"\n{'='*60}")
    print(f"  SCLG-AI Telegram Bot v{VERSION}")
    print(f"  Personal Assistant + DevOps Agent")
    print(f"{'='*60}\n")

    if not TELEGRAM_TOKEN:
        print("[FATAL] TELEGRAM_BOT_TOKEN not set!")
        print("Set: export TELEGRAM_BOT_TOKEN='your_token'")
        sys.exit(1)

    bot_api = TelegramAPI(TELEGRAM_TOKEN)
    me = await bot_api.get_me()
    if me:
        print(f"  Bot: @{me.get('username', '?')} ({me.get('first_name', '?')})")
    else:
        print("[FATAL] Cannot connect to Telegram API!")
        sys.exit(1)

    sclg_bot = SclgTelegramBot()
    await sclg_bot.setup()

    # Start scheduler in background
    scheduler_task = asyncio.create_task(sclg_bot.run_scheduler_loop(bot_api))

    print(f"\n  Bot is running. Waiting for messages...\n")

    consecutive_errors = 0
    while True:
        try:
            updates = await bot_api.get_updates(timeout=30)
            consecutive_errors = 0

            for update in updates:
                try:
                    await sclg_bot.handle_message(update, bot_api)
                except Exception as e:
                    log.error(f"Message handler error: {e}", exc_info=True)
                    chat_id = update.get("message", {}).get("chat", {}).get("id")
                    if chat_id:
                        await bot_api.send_message(chat_id, f"Internal error: {e}")

        except KeyboardInterrupt:
            print("\nShutting down...")
            scheduler_task.cancel()
            break
        except Exception as e:
            consecutive_errors += 1
            log.error(f"Polling error #{consecutive_errors}: {e}")
            if consecutive_errors > 10:
                print("[FATAL] Too many consecutive errors, exiting.")
                break
            await asyncio.sleep(min(consecutive_errors * 2, 30))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        print(f"sclg-telegram-bot v{VERSION}")
        sys.exit(0)
    asyncio.run(main())
