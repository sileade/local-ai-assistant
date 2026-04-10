#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║  Scoliologic AI Console (sclg-ai) v4.2.0                 ║
║  Autonomous DevOps/SysAdmin Agent                        ║
║  Execute first, explain later — like Claude Code          ║
║                                                           ║
║  Integrated ideas from:                                   ║
║  - ai-unified-platform (parallel inference, caching)      ║
║  - ai-router-moe (MoE expert routing, YAML config)       ║
║  - local-ai-assistant (monitoring, roles)                 ║
║  - nanobot (Dream memory, skills, lifecycle hooks)        ║
║  - avoid-ai-writing (anti-AI-isms post-processor)         ║
╚═══════════════════════════════════════════════════════════╝
"""

import sys
import os
import json
import time
import signal
import re
import subprocess
import urllib.request
import urllib.error
import readline
import socket
import ipaddress
import threading
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ── ANSI Color Codes ────────────────────────────────────────────────

class C:
    RESET    = "\033[0m"
    BOLD     = "\033[1m"
    DIM      = "\033[2m"
    ITALIC   = "\033[3m"
    UNDER    = "\033[4m"
    RED      = "\033[31m"
    GREEN    = "\033[32m"
    YELLOW   = "\033[33m"
    BLUE     = "\033[34m"
    MAGENTA  = "\033[35m"
    CYAN     = "\033[36m"
    WHITE    = "\033[37m"
    BRED     = "\033[91m"
    BGREEN   = "\033[92m"
    BYELLOW  = "\033[93m"
    BBLUE    = "\033[94m"
    BMAGENTA = "\033[95m"
    BCYAN    = "\033[96m"
    BWHITE   = "\033[97m"

    @staticmethod
    def rgb(r, g, b):
        return f"\033[38;2;{r};{g};{b}m"

# ── Theme ───────────────────────────────────────────────────────────

ACCENT      = C.rgb(230, 100, 100)
ACCENT2     = C.rgb(255, 180, 80)
USER_COLOR  = C.rgb(255, 200, 80)
AI_COLOR    = C.rgb(200, 200, 210)
SYSTEM_CLR  = C.rgb(120, 200, 120)
DIM_COLOR   = C.rgb(100, 100, 110)
BORDER_CLR  = C.rgb(80, 80, 90)
PROMPT_CLR  = C.rgb(180, 140, 255)
ERROR_CLR   = C.rgb(255, 80, 80)
LOGO_CLR    = C.rgb(230, 120, 80)
TOOL_CLR    = C.rgb(100, 180, 255)
WARN_CLR    = C.rgb(255, 200, 60)
NET_CLR     = C.rgb(80, 220, 180)
CLAUDE_CLR  = C.rgb(180, 130, 255)
MEMORY_CLR  = C.rgb(200, 160, 255)
SKILL_CLR   = C.rgb(120, 220, 200)

# ── Configuration ───────────────────────────────────────────────────

VERSION = "4.2.0"
APP_NAME = "Scoliologic AI"

GPU_BALANCER_URL = "http://10.0.0.229:11440"

CLUSTER_NODES = {
    "ai-server": "http://10.0.0.229:11434",
    "ai002":     "http://172.27.5.114:11434",
    "ai012":     "http://172.27.5.150:11434",
    "ai003":     "http://172.27.4.242:11434",
}

# ── File Paths ──────────────────────────────────────────────────────

DATA_DIR         = os.path.expanduser("~/.sclg_ai")
HISTORY_FILE     = os.path.join(DATA_DIR, "history")
CONFIG_FILE      = os.path.join(DATA_DIR, "config.json")
LOG_DIR          = os.path.join(DATA_DIR, "logs")
HOSTS_FILE       = os.path.join(DATA_DIR, "hosts.json")
CLAUDE_USAGE_FILE = os.path.join(DATA_DIR, "claude_usage.json")
TRAINING_FILE    = os.path.join(DATA_DIR, "training.jsonl")
MEMORY_FILE      = os.path.join(DATA_DIR, "memory.json")
CACHE_FILE       = os.path.join(DATA_DIR, "cache.json")
SKILLS_DIR       = os.path.join(DATA_DIR, "skills")
STATS_FILE       = os.path.join(DATA_DIR, "stats.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SKILLS_DIR, exist_ok=True)

# ── Claude API Configuration ───────────────────────────────────────

CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", os.environ.get("CLAUDE_API_KEY", ""))
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL   = "claude-sonnet-4-20250514"
CLAUDE_DAILY_LIMIT = 20
CLAUDE_MAX_TOKENS  = 4096
CLAUDE_MONTHLY_LIMIT = 200

# ── Known Infrastructure ────────────────────────────────────────────

# Passwords loaded from SCLG_SSH_PASS env var or ~/.sclg_ai/hosts.json
_SSH_PASS = os.environ.get("SCLG_SSH_PASS", "")

def _load_hosts():
    """Load hosts from file or use defaults with env password."""
    hosts_path = os.path.join(DATA_DIR, "hosts.json")
    if os.path.exists(hosts_path):
        try:
            with open(hosts_path) as f:
                return json.load(f)
        except:
            pass
    return {
        "ai-server":    {"ip": "10.0.0.229",     "user": "ilea", "pass": _SSH_PASS, "type": "linux", "desc": "Main AI node (GPU Balancer)"},
        "ai002":        {"ip": "172.27.5.114",    "user": "ilea", "pass": _SSH_PASS, "type": "linux", "desc": "AI node (2x RTX 5070 Ti)"},
        "ai012":        {"ip": "172.27.5.150",    "user": "ilea", "pass": _SSH_PASS, "type": "linux", "desc": "AI node (RTX 2000 Ada)"},
        "ai003":        {"ip": "172.27.4.242",    "user": "ilea", "pass": _SSH_PASS, "type": "linux", "desc": "AI node (RTX 5070 Ti)"},
        "mac-mini":     {"ip": "172.27.4.255",    "user": "ilea", "pass": _SSH_PASS, "type": "macos", "desc": "Mac Mini M4 Pro"},
        "grafana":      {"ip": "172.27.5.111",    "user": "root", "pass": _SSH_PASS, "type": "linux", "desc": "Monitoring"},
        "bastion":      {"ip": "45.144.43.100",   "user": "ilea", "pass": _SSH_PASS, "type": "linux", "desc": "Bastion/VPN gateway", "port": 2222},
    }

KNOWN_HOSTS = _load_hosts()

# ══════════════════════════════════════════════════════════════════════
# MODEL PROFILES — MoE Expert Routing (from ai-router-moe)
# Each expert has preferred models, keywords, temperature, and system prompt
# ══════════════════════════════════════════════════════════════════════

MODEL_PROFILES = {
    "code": {
        "models": ["qwen2.5-coder-tools:32b", "qwen2.5-coder:14b", "qwen2.5-coder:7b"],
        "keywords": ["код", "code", "python", "bash", "script", "скрипт", "debug",
            "ошибка", "error", "bug", "функция", "function", "class", "def ",
            "import", "docker", "yaml", "json", "api", "http", "sql", "git",
            "npm", "pip", "nginx", "systemd", "ansible", "terraform"],
        "temperature": 0.2,
        "system_hint": "Ты опытный программист. Пиши чистый, рабочий код. Объясняй кратко.",
    },
    "sysadmin": {
        "models": ["qwen3.5-27b-hf:latest", "mistral:7b", "qwen2.5:14b"],
        "keywords": ["сервер", "server", "ssh", "network", "сеть", "firewall",
            "iptables", "dns", "ip", "ping", "traceroute", "диск", "disk",
            "memory", "cpu", "gpu", "nvidia", "процесс", "process",
            "kill", "systemctl", "service", "лог", "log", "порт", "port",
            "proxmox", "vm", "vpn", "ssl", "tls", "cert", "сканир", "scan",
            "почини", "исправь", "fix", "проверь", "status", "мониторинг",
            "ollama", "роутер", "router", "mikrotik", "dhcp", "nat"],
        "temperature": 0.3,
        "system_hint": "Ты DevOps/SysAdmin эксперт. Выполняй команды и анализируй результаты.",
    },
    "analysis": {
        "models": ["gemma4-26b-hf:latest", "phi4:14b", "qwen3.5-27b-hf:latest"],
        "keywords": ["анализ", "analys", "data", "данные", "статистик",
            "медицин", "medical", "сколиоз", "исследован", "research"],
        "temperature": 0.3,
        "system_hint": "Ты аналитик данных. Давай структурированный анализ с выводами.",
    },
    "creative": {
        "models": ["glm-4.7-flash-hf:latest", "gemma4-26b-hf:latest", "llama3.1:8b"],
        "keywords": ["напиши", "write", "текст", "статья", "перевод",
            "резюме", "summary", "письмо", "email", "отчёт", "report"],
        "temperature": 0.7,
        "system_hint": "Ты писатель. Создавай грамотный, структурированный контент.",
    },
    "general": {
        "models": ["qwen3.5-27b-hf:latest", "qwen2.5:14b", "llama3.1:8b"],
        "keywords": [],
        "temperature": 0.5,
        "system_hint": "Ты универсальный AI-ассистент. Отвечай точно и полезно.",
    },
}

# ══════════════════════════════════════════════════════════════════════
# SMART PATTERNS v4.1: Execute-first approach
# Format: (keywords_list, shell_commands, category)
# These commands run LOCALLY on Mac Mini BEFORE sending to AI
# ══════════════════════════════════════════════════════════════════════

SMART_PATTERNS = [
    # ── Network / IP / DNS ──
    (["мой ip", "свой ip", "мои ip", "твой ip", "у тебя ip", "тебя ip",
      "ip адрес", "ip-адрес", "ip address", "покажи ip", "узнай ip",
      "определи ip", "какой ip", "в какой сети", "какая сеть",
      "сетевая информация", "сетевые настройки", "network info",
      "какой адрес", "адрес и днс", "адрес и dns", "ip и dns",
      "ip dns", "сеть и dns", "покажи сеть", "ip б dns",
      "просканируй сеть", "сканируй сеть", "scan network",
      "активные адреса", "активных адресов", "список адресов",
      "хосты в сети", "устройства в сети", "devices in network"],
     ["ifconfig 2>/dev/null || ip addr show 2>/dev/null",
      "cat /etc/resolv.conf 2>/dev/null; scutil --dns 2>/dev/null | grep 'nameserver' | sort -u | head -5",
      "netstat -rn 2>/dev/null | grep default | head -5 || ip route show default 2>/dev/null"],
     "sysadmin"),

    (["внешний ip", "публичный ip", "external ip", "public ip", "белый ip"],
     ["curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null",
      "curl -s ipinfo.io 2>/dev/null || echo ''"],
     "sysadmin"),

    (["мой dns", "свой dns", "твой dns", "dns серв", "dns-серв", "покажи dns",
      "узнай dns", "какой dns", "resolv", "днс", "мой днс", "покажи днс"],
     ["cat /etc/resolv.conf 2>/dev/null",
      "scutil --dns 2>/dev/null | head -30 || resolvectl status 2>/dev/null | head -30"],
     "sysadmin"),

    (["шлюз", "gateway", "маршрут", "route", "роут"],
     ["netstat -rn 2>/dev/null | head -15 || ip route show 2>/dev/null",
      "arp -a 2>/dev/null | head -10"],
     "sysadmin"),

    (["hostname", "имя хоста", "имя машины", "кто я", "whoami",
      "какая ос", "какая система", "uname", "о системе", "system info"],
     ["hostname 2>/dev/null", "uname -a 2>/dev/null", "whoami 2>/dev/null",
      "sw_vers 2>/dev/null || cat /etc/os-release 2>/dev/null",
      "sysctl -n hw.memsize 2>/dev/null || free -h 2>/dev/null"],
     "sysadmin"),

    # ── Disk / Storage ──
    (["диск", "disk", "место на диск", "свободное место", "df",
      "storage", "хранилище", "заполнен"],
     ["df -h 2>/dev/null"],
     "sysadmin"),

    # ── Memory ──
    (["память", "memory", "ram", "оперативн", "free", "свободная память", "swap"],
     ["free -h 2>/dev/null || vm_stat 2>/dev/null",
      "swapon --show 2>/dev/null || sysctl vm.swapusage 2>/dev/null"],
     "sysadmin"),

    # ── CPU / Load ──
    (["нагрузк", "load", "cpu", "процессор", "uptime", "аптайм"],
     ["uptime 2>/dev/null",
      "nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null",
      "top -bn1 2>/dev/null | head -5 || top -l 1 2>/dev/null | head -10"],
     "sysadmin"),

    # ── Processes ──
    (["процесс", "process", "что запущен", "что работает"],
     ["ps aux --sort=-%mem 2>/dev/null | head -20 || ps aux 2>/dev/null | head -20"],
     "sysadmin"),

    # ── Ports / Services ──
    (["порт", "port", "слушает", "listening", "netstat", "открытые порт"],
     ["ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null || lsof -i -P -n 2>/dev/null | head -30"],
     "sysadmin"),

    # ── Docker ──
    (["docker", "контейнер", "container", "compose"],
     ["docker ps -a 2>/dev/null || echo 'Docker не установлен'",
      "docker images 2>/dev/null | head -15"],
     "code"),

    # ── GPU / AI ──
    (["gpu", "nvidia", "видеокарт", "cuda", "vram"],
     ["nvidia-smi 2>/dev/null || echo 'nvidia-smi не найден (Mac Mini не имеет NVIDIA GPU)'"],
     "sysadmin"),

    (["ollama", "модел", "model", "какие модели"],
     ["curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(m['name']) for m in d.get('models',[])]\" 2>/dev/null || echo 'Ollama не доступен локально'",
      "curl -s http://10.0.0.229:11440/api/tags 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print(f'{len(d.get(\\\"models\\\", []))} models on GPU Balancer'); [print(f'  {m[\\\"name\\\"]}') for m in d.get('models',[])]\" 2>/dev/null || echo 'GPU Balancer не доступен'"],
     "sysadmin"),

    # ── Logs ──
    (["лог", "log", "журнал", "journal", "ошибки в лог"],
     ["journalctl -p err --no-pager -n 20 2>/dev/null || log show --last 5m --predicate 'eventType == logEvent and messageType == error' 2>/dev/null | tail -20 || tail -20 /var/log/syslog 2>/dev/null"],
     "sysadmin"),

    # ── Services ──
    (["сервис", "service", "systemctl", "что упало", "failed"],
     ["systemctl list-units --state=failed --no-pager 2>/dev/null || echo 'systemctl не доступен'",
      "launchctl list 2>/dev/null | head -25"],
     "sysadmin"),

    # ── SSL ──
    (["ssl", "tls", "сертификат", "cert", "https"],
     ["openssl version 2>/dev/null"],
     "sysadmin"),

    # ── Git ──
    (["git stat", "git log", "git diff", "коммит", "commit", "репозитор"],
     ["git status 2>/dev/null || echo 'Не git-репозиторий'",
      "git log --oneline -10 2>/dev/null || echo ''"],
     "code"),

    # ── Firewall ──
    (["firewall", "фаервол", "iptables", "ufw", "pf"],
     ["sudo pfctl -sr 2>/dev/null || sudo iptables -L -n 2>/dev/null || echo 'Firewall не настроен'"],
     "sysadmin"),

    # ── Cron ──
    (["cron", "крон", "расписание", "schedule"],
     ["crontab -l 2>/dev/null || echo 'Нет crontab'"],
     "sysadmin"),

    # ── Users ──
    (["пользовател", "user", "кто залогинен", "who"],
     ["who 2>/dev/null || w 2>/dev/null", "last -10 2>/dev/null"],
     "sysadmin"),
]

# ── Scan Keywords ──────────────────────────────────────────────────

SCAN_KEYWORDS = [
    "просканируй сеть", "сканируй сеть", "scan network", "scan the network",
    "активные адреса", "активных адресов", "список адресов", "список хостов",
    "хосты в сети", "устройства в сети", "devices in network", "найди устройства",
    "что в сети", "кто в сети", "who is on network", "arp scan", "fping",
    "nmap scan", "сканирование сети", "network scan",
]


# ══════════════════════════════════════════════════════════════════════
# ANTI-AI-ISMS POST-PROCESSOR (from avoid-ai-writing)
# Cleans AI responses to sound more natural
# ══════════════════════════════════════════════════════════════════════

class ResponseCleaner:
    """Post-processor that removes common AI writing patterns from responses."""

    # Tier 1: Always replace (obvious AI-isms)
    TIER1_REPLACEMENTS = {
        "leverage": "use", "utilize": "use", "utilise": "use",
        "commence": "start", "facilitate": "help", "endeavor": "try",
        "subsequently": "then", "aforementioned": "this",
        "paramount": "important", "plethora": "many",
        "myriad": "many", "delve": "look into", "delving": "looking into",
        "tapestry": "", "landscape": "area", "ecosystem": "system",
        "synergy": "teamwork", "paradigm": "model",
        "cutting-edge": "new", "state-of-the-art": "modern",
        "game-changer": "improvement", "groundbreaking": "new",
        "revolutionize": "change", "revolutionise": "change",
        "spearhead": "lead", "streamline": "simplify",
        "bolster": "support", "augment": "add to",
        "pivotal": "important", "crucial": "important",
        "robust": "reliable", "seamless": "smooth",
        "comprehensive": "full", "holistic": "complete",
    }

    # Chatbot openers to strip
    CHATBOT_OPENERS = [
        r"^(Certainly|Of course|Absolutely|Great question|Sure thing|Happy to help)[!.]?\s*",
        r"^(Конечно|Безусловно|Разумеется|Отличный вопрос|С удовольствием)[!.]?\s*",
        r"^(Хороший вопрос|Давайте разберёмся|Давайте посмотрим)[!.]?\s*",
    ]

    # Chatbot closers to strip
    CHATBOT_CLOSERS = [
        r"\s*(Let me know if you (need|have|want) anything else[!.]?)\s*$",
        r"\s*(Если (нужно|есть|хотите) что-то ещё[, —]* (обращайтесь|спрашивайте|пишите)[!.]?)\s*$",
        r"\s*(Надеюсь,? это (помогло|было полезно)[!.]?)\s*$",
        r"\s*(Не стесняйтесь (спрашивать|обращаться)[!.]?)\s*$",
        r"\s*(Буду рад помочь ещё[!.]?)\s*$",
    ]

    # Filler transitions to simplify
    FILLER_TRANSITIONS = {
        "Moreover, ": "", "Furthermore, ": "", "Additionally, ": "",
        "In conclusion, ": "", "To summarize, ": "", "In summary, ": "",
        "It's worth noting that ": "", "It is worth noting that ": "",
        "It should be noted that ": "", "It's important to note that ": "",
        "Более того, ": "", "Кроме того, ": "", "Помимо этого, ": "",
        "В заключение, ": "", "Подводя итог, ": "",
        "Стоит отметить, что ": "", "Важно отметить, что ": "",
        "Следует отметить, что ": "",
    }

    def clean(self, text):
        """Apply all cleaning passes to response text."""
        if not text or len(text) < 20:
            return text

        result = text

        # Pass 1: Strip chatbot openers
        for pat in self.CHATBOT_OPENERS:
            result = re.sub(pat, "", result, count=1, flags=re.MULTILINE)

        # Pass 2: Strip chatbot closers
        for pat in self.CHATBOT_CLOSERS:
            result = re.sub(pat, "", result, flags=re.IGNORECASE)

        # Pass 3: Replace filler transitions
        for filler, replacement in self.FILLER_TRANSITIONS.items():
            result = result.replace(filler, replacement)

        # Pass 4: Tier 1 word replacements (case-insensitive, whole words)
        for ai_word, plain_word in self.TIER1_REPLACEMENTS.items():
            result = re.sub(
                rf'\b{re.escape(ai_word)}\b',
                plain_word, result, flags=re.IGNORECASE
            )

        return result.strip()


# ══════════════════════════════════════════════════════════════════════
# DREAM MEMORY — Two-Stage Persistent Memory (from nanobot)
# Short-term: recent conversation facts
# Long-term: important facts persisted across sessions
# ══════════════════════════════════════════════════════════════════════

class DreamMemory:
    """Two-stage memory system inspired by nanobot's Dream memory."""

    def __init__(self, memory_file=MEMORY_FILE):
        self.memory_file = memory_file
        self.short_term = []  # Recent facts (cleared on session end)
        self.long_term = self._load()  # Persistent facts

    def _load(self):
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file) as f:
                    data = json.load(f)
                    return data.get("facts", [])
        except:
            pass
        return []

    def _save(self):
        try:
            with open(self.memory_file, "w") as f:
                json.dump({
                    "facts": self.long_term[-100:],  # Keep last 100 facts
                    "updated": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        except:
            pass

    def remember(self, fact, importance="normal"):
        """Add a fact to memory. High importance goes to long-term."""
        entry = {
            "fact": fact,
            "time": datetime.now().isoformat(),
            "importance": importance
        }
        self.short_term.append(entry)
        if importance in ("high", "critical"):
            self.long_term.append(entry)
            self._save()

    def recall(self, query="", limit=10):
        """Recall relevant facts. Simple keyword matching for now."""
        all_facts = self.long_term + self.short_term
        if not query:
            return all_facts[-limit:]

        query_low = query.lower()
        scored = []
        for fact in all_facts:
            text = fact["fact"].lower()
            score = sum(1 for word in query_low.split() if word in text)
            if score > 0:
                scored.append((score, fact))
        scored.sort(key=lambda x: -x[0])
        return [f for _, f in scored[:limit]]

    def consolidate(self):
        """Move important short-term facts to long-term (Dream consolidation)."""
        for fact in self.short_term:
            # Auto-promote facts about infrastructure
            text = fact["fact"].lower()
            infra_keywords = ["ip", "server", "пароль", "password", "port", "host",
                            "service", "error", "fix", "config", "dns", "gateway"]
            if any(kw in text for kw in infra_keywords):
                if fact not in self.long_term:
                    self.long_term.append(fact)
        self._save()
        self.short_term = []

    def get_context(self, limit=5):
        """Get memory context string for AI prompt."""
        recent = self.recall(limit=limit)
        if not recent:
            return ""
        lines = [f"- {f['fact']}" for f in recent]
        return "Из памяти:\n" + "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
# REQUEST CACHE (from ai-unified-platform)
# Cache similar queries to avoid redundant API calls
# ══════════════════════════════════════════════════════════════════════

class RequestCache:
    """Simple request cache with TTL."""

    def __init__(self, cache_file=CACHE_FILE, ttl=3600, max_entries=200):
        self.cache_file = cache_file
        self.ttl = ttl
        self.max_entries = max_entries
        self.cache = self._load()

    def _load(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file) as f:
                    return json.load(f)
        except:
            pass
        return {}

    def _save(self):
        try:
            # Prune old entries
            now = time.time()
            self.cache = {
                k: v for k, v in self.cache.items()
                if now - v.get("time", 0) < self.ttl
            }
            # Keep only max_entries
            if len(self.cache) > self.max_entries:
                sorted_keys = sorted(self.cache, key=lambda k: self.cache[k].get("time", 0))
                for k in sorted_keys[:len(self.cache) - self.max_entries]:
                    del self.cache[k]
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f)
        except:
            pass

    def _hash(self, query):
        """Create a normalized hash of the query."""
        normalized = re.sub(r'\s+', ' ', query.lower().strip())
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def get(self, query):
        """Get cached response for a query."""
        key = self._hash(query)
        entry = self.cache.get(key)
        if entry and (time.time() - entry.get("time", 0)) < self.ttl:
            return entry.get("response")
        return None

    def put(self, query, response, category="general"):
        """Cache a response."""
        key = self._hash(query)
        self.cache[key] = {
            "query": query[:200],
            "response": response[:5000],
            "category": category,
            "time": time.time()
        }
        self._save()

    def stats(self):
        """Return cache statistics."""
        now = time.time()
        active = sum(1 for v in self.cache.values() if now - v.get("time", 0) < self.ttl)
        return {"total": len(self.cache), "active": active}


# ══════════════════════════════════════════════════════════════════════
# STATS TRACKER (from ai-router-moe)
# Track queries per expert, response times, model usage
# ══════════════════════════════════════════════════════════════════════

class StatsTracker:
    """Track usage statistics per expert/model."""

    def __init__(self, stats_file=STATS_FILE):
        self.stats_file = stats_file
        self.data = self._load()

    def _load(self):
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file) as f:
                    return json.load(f)
        except:
            pass
        return {
            "queries_by_expert": {},
            "queries_by_model": {},
            "claude_fallbacks": 0,
            "cache_hits": 0,
            "total_queries": 0,
            "session_start": datetime.now().isoformat(),
        }

    def _save(self):
        try:
            with open(self.stats_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except:
            pass

    def record(self, expert, model, used_claude=False, cache_hit=False):
        """Record a query."""
        self.data["total_queries"] = self.data.get("total_queries", 0) + 1
        exp = self.data.setdefault("queries_by_expert", {})
        exp[expert] = exp.get(expert, 0) + 1
        mod = self.data.setdefault("queries_by_model", {})
        mod[model] = mod.get(model, 0) + 1
        if used_claude:
            self.data["claude_fallbacks"] = self.data.get("claude_fallbacks", 0) + 1
        if cache_hit:
            self.data["cache_hits"] = self.data.get("cache_hits", 0) + 1
        self._save()

    def summary(self):
        """Return formatted stats summary."""
        d = self.data
        lines = [
            f"Total queries: {d.get('total_queries', 0)}",
            f"Claude fallbacks: {d.get('claude_fallbacks', 0)}",
            f"Cache hits: {d.get('cache_hits', 0)}",
        ]
        exp = d.get("queries_by_expert", {})
        if exp:
            lines.append("By expert: " + ", ".join(f"{k}={v}" for k, v in sorted(exp.items(), key=lambda x: -x[1])))
        mod = d.get("queries_by_model", {})
        if mod:
            top3 = sorted(mod.items(), key=lambda x: -x[1])[:3]
            lines.append("Top models: " + ", ".join(f"{k.split(':')[0]}={v}" for k, v in top3))
        return "\n".join(lines)


# ── Utilities ───────────────────────────────────────────────────────

def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except:
        return 80

def clear_screen():
    print("\033[2J\033[H", end="")

def draw_hline(char="─", color=BORDER_CLR):
    print(f"{color}{char * get_terminal_width()}{C.RESET}")

def draw_dashed():
    print(f"{BORDER_CLR}{'┄' * get_terminal_width()}{C.RESET}")

CLAW_MINI = """  ╱▔╲ ╱▔╲
 ( ◉   ◉ )
  ╲▁▁▁▁▁╱
   ╱╲ ╱╲"""


# ══════════════════════════════════════════════════════════════════════
# ANIMATED SPINNER — Visual feedback while AI is thinking
# Shows braille animation + elapsed time + current action
# ══════════════════════════════════════════════════════════════════════

class Spinner:
    """Animated spinner with timer for long-running operations."""

    BRAILLE = ["⣾", "⣽", "⣻", "⢿", "⣿", "⣟", "⣯", "⣷"]
    DOTS    = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message="Thinking", color=ACCENT2, style="braille"):
        self.message = message
        self.color = color
        self.frames = self.BRAILLE if style == "braille" else self.DOTS
        self._running = False
        self._thread = None
        self._start_time = 0
        self._substatus = ""
        self._lock = threading.Lock()

    def _animate(self):
        """Animation loop running in background thread."""
        idx = 0
        while self._running:
            elapsed = time.time() - self._start_time
            frame = self.frames[idx % len(self.frames)]
            with self._lock:
                sub = self._substatus

            # Build status line
            status = f"\r  {self.color}{frame} {self.message}... {elapsed:.0f}s{C.RESET}"
            if sub:
                status += f"  {DIM_COLOR}{sub}{C.RESET}"

            # Pad to clear previous line
            status += " " * 20

            sys.stdout.write(status)
            sys.stdout.flush()
            idx += 1
            time.sleep(0.12)

    def update(self, substatus):
        """Update substatus text (e.g., model name, step)."""
        with self._lock:
            self._substatus = substatus

    def start(self):
        """Start the spinner."""
        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()
        return self

    def stop(self, final_message=""):
        """Stop the spinner and clear the line."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        elapsed = time.time() - self._start_time
        # Clear spinner line
        sys.stdout.write(f"\r{' ' * (get_terminal_width())}\r")
        sys.stdout.flush()
        if final_message:
            print(f"  {SYSTEM_CLR}{final_message} ({elapsed:.1f}s){C.RESET}")

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


class ProgressBar:
    """Simple progress indicator for multi-step operations."""

    def __init__(self, total, label="Progress", color=TOOL_CLR):
        self.total = total
        self.current = 0
        self.label = label
        self.color = color

    def update(self, step_name=""):
        """Update progress."""
        self.current += 1
        pct = int(self.current / self.total * 100) if self.total > 0 else 0
        bar_width = 20
        filled = int(bar_width * self.current / self.total) if self.total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)
        status = f"\r  {self.color}{self.label} [{bar}] {pct}%{C.RESET}"
        if step_name:
            status += f"  {DIM_COLOR}{step_name}{C.RESET}"
        status += " " * 10
        sys.stdout.write(status)
        sys.stdout.flush()

    def finish(self, message=""):
        """Complete the progress bar."""
        sys.stdout.write(f"\r{' ' * get_terminal_width()}\r")
        sys.stdout.flush()
        if message:
            print(f"  {SYSTEM_CLR}✓ {message}{C.RESET}")


# ══════════════════════════════════════════════════════════════════════
# OLLAMA CLIENT — Connects to GPU Balancer or direct nodes
# ══════════════════════════════════════════════════════════════════════

class OllamaClient:
    """Client for Ollama API with GPU Balancer support."""

    def __init__(self, base_url=GPU_BALANCER_URL, timeout=180):
        self.base_url = base_url
        self.timeout = timeout
        self.available_models = []
        self.last_model_check = 0

    def check_connection(self):
        """Check if Ollama is reachable."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                self.available_models = [m["name"] for m in data.get("models", [])]
                self.last_model_check = time.time()
                return True
        except:
            return False

    def get_models(self, force=False):
        """Get available models list."""
        if force or time.time() - self.last_model_check > 300:
            self.check_connection()
        return self.available_models

    def find_best_model(self, preferred_models):
        """Find best available model from preferred list."""
        available = self.get_models()
        if not available:
            return None

        # Try exact match first
        for pref in preferred_models:
            if pref in available:
                return pref

        # Try partial match
        for pref in preferred_models:
            base = pref.split(":")[0]
            for avail in available:
                if base in avail:
                    return avail

        # Return first available
        return available[0] if available else None

    def generate(self, model, prompt, system="", temperature=0.5, max_tokens=4096, stream=False, retries=2):
        """Generate response from Ollama with retry logic."""
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        data = json.dumps(payload).encode()
        last_error = None

        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/api/generate",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    result = json.loads(resp.read().decode())
                    return result.get("response", "")
            except urllib.error.URLError as e:
                last_error = e
                if attempt < retries - 1:
                    time.sleep(2)
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    time.sleep(2)

        return f"[ERROR] Ollama failed after {retries} attempts: {last_error}"

    def chat(self, model, messages, system="", temperature=0.5, max_tokens=4096, stream=False, retries=2):
        """Chat completion from Ollama with retry logic."""
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        payload = {
            "model": model,
            "messages": msgs,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        data = json.dumps(payload).encode()
        last_error = None

        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/api/chat",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    result = json.loads(resp.read().decode())
                    return result.get("message", {}).get("content", "")
            except urllib.error.URLError as e:
                last_error = e
                if attempt < retries - 1:
                    time.sleep(2)
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    time.sleep(2)

        return f"[ERROR] Ollama chat failed after {retries} attempts: {last_error}"


# ══════════════════════════════════════════════════════════════════════
# CLAUDE API CLIENT — Anthropic Claude as premium fallback
# ══════════════════════════════════════════════════════════════════════

class ClaudeClient:
    """Client for Anthropic Claude API with budget tracking."""

    def __init__(self, api_key=CLAUDE_API_KEY, model=CLAUDE_MODEL):
        self.api_key = api_key
        self.model = model
        self.usage = self._load_usage()

    def _load_usage(self):
        try:
            if os.path.exists(CLAUDE_USAGE_FILE):
                with open(CLAUDE_USAGE_FILE) as f:
                    data = json.load(f)
                    # Reset daily counter if new day
                    if data.get("date") != datetime.now().strftime("%Y-%m-%d"):
                        data["daily_count"] = 0
                        data["date"] = datetime.now().strftime("%Y-%m-%d")
                    # Reset monthly counter if new month
                    if data.get("month") != datetime.now().strftime("%Y-%m"):
                        data["monthly_count"] = 0
                        data["month"] = datetime.now().strftime("%Y-%m")
                    return data
        except:
            pass
        return {
            "daily_count": 0,
            "monthly_count": 0,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "month": datetime.now().strftime("%Y-%m"),
            "total_tokens": 0,
        }

    def _save_usage(self):
        try:
            with open(CLAUDE_USAGE_FILE, "w") as f:
                json.dump(self.usage, f, indent=2)
        except:
            pass

    def can_use(self):
        """Check if Claude can be used (within budget)."""
        if not self.api_key:
            return False
        if self.usage.get("daily_count", 0) >= CLAUDE_DAILY_LIMIT:
            return False
        if self.usage.get("monthly_count", 0) >= CLAUDE_MONTHLY_LIMIT:
            return False
        return True

    def remaining_today(self):
        return max(0, CLAUDE_DAILY_LIMIT - self.usage.get("daily_count", 0))

    def remaining_month(self):
        return max(0, CLAUDE_MONTHLY_LIMIT - self.usage.get("monthly_count", 0))

    def chat(self, messages, system="", max_tokens=CLAUDE_MAX_TOKENS, temperature=0.3):
        """Send request to Claude API."""
        if not self.can_use():
            return "[BUDGET] Claude daily/monthly limit reached"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            CLAUDE_API_URL,
            data=data,
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
                content = ""
                for block in result.get("content", []):
                    if block.get("type") == "text":
                        content += block.get("text", "")

                # Track usage
                usage = result.get("usage", {})
                self.usage["daily_count"] = self.usage.get("daily_count", 0) + 1
                self.usage["monthly_count"] = self.usage.get("monthly_count", 0) + 1
                self.usage["total_tokens"] = self.usage.get("total_tokens", 0) + \
                    usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                self._save_usage()

                return content

        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if hasattr(e, 'read') else str(e)
            return f"[ERROR] Claude API {e.code}: {error_body[:200]}"
        except Exception as e:
            return f"[ERROR] Claude: {e}"

    def test_connection(self):
        """Quick test if Claude API is reachable."""
        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            }
            payload = {
                "model": self.model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "ping"}],
            }
            data = json.dumps(payload).encode()
            req = urllib.request.Request(CLAUDE_API_URL, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except:
            return False


# ══════════════════════════════════════════════════════════════════════
# MoE EXPERT ROUTER (from ai-router-moe)
# Classifies queries and routes to the best expert/model
# ══════════════════════════════════════════════════════════════════════

class ExpertRouter:
    """MoE-style router that classifies queries to experts."""

    def __init__(self, profiles=MODEL_PROFILES):
        self.profiles = profiles

    def classify(self, query):
        """Classify query into an expert category."""
        query_low = query.lower()
        scores = {}

        for expert, profile in self.profiles.items():
            score = 0
            for kw in profile.get("keywords", []):
                if kw in query_low:
                    score += 2
                    # Bonus for exact word match
                    if re.search(rf'\b{re.escape(kw)}\b', query_low):
                        score += 1
            scores[expert] = score

        # Get best expert
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            best = "general"

        return best, scores[best]

    def get_model_and_config(self, expert, ollama_client):
        """Get the best available model for an expert."""
        profile = self.profiles.get(expert, self.profiles["general"])
        model = ollama_client.find_best_model(profile["models"])
        return {
            "model": model,
            "temperature": profile["temperature"],
            "system_hint": profile["system_hint"],
            "expert": expert,
        }


# ══════════════════════════════════════════════════════════════════════
# QUALITY CHECKER v2 — Detects bad responses and triggers Claude fallback
# Enhanced with avoid-ai-writing patterns
# ══════════════════════════════════════════════════════════════════════

class QualityChecker:
    """Checks response quality and detects refusals/garbage."""

    # Patterns that indicate the model REFUSED to execute
    REFUSAL_PATTERNS = [
        r"я не могу (выполн|запуст|подключ|сканир|получить доступ)",
        r"у меня нет (доступа|возможности|прав)",
        r"я (не имею|не обладаю) (доступ|возможност)",
        r"я (являюсь|работаю как) (текстов|языков|ИИ|AI)",
        r"я.*искусственн.*интеллект",
        r"i (can't|cannot|don't have) (access|execute|run|connect)",
        r"i('m| am) (just |only )?(a |an )?(text|language|ai|artificial)",
        r"as an ai",
        r"i don't have (the ability|access|capability)",
        r"не могу напрямую",
        r"не имею прямого доступа",
        r"нет физического доступа",
        r"не могу непосредственно",
        r"однако я могу подсказать",
        r"однако я могу помочь вам",
        r"вот как вы можете сделать это сами",
        r"вы можете сделать это самостоятельно",
        r"я могу предложить.*инструкции",
    ]

    # Patterns that indicate generic/useless response
    GARBAGE_PATTERNS = [
        r"^(привет|hello|hi)[\s!.]*$",
        r"чем (я )?могу (вам )?помочь",
        r"как я могу вам помочь",
        r"what can i help",
    ]

    def check(self, response, query=""):
        """Check response quality. Returns (is_good, reason)."""
        if not response or len(response.strip()) < 5:
            return False, "empty_response"

        resp_low = response.lower()

        # Check for refusals
        for pat in self.REFUSAL_PATTERNS:
            if re.search(pat, resp_low):
                return False, "refusal"

        # Check for garbage
        for pat in self.GARBAGE_PATTERNS:
            if re.search(pat, resp_low):
                return False, "garbage"

        # Check for error responses
        if response.startswith("[ERROR]") or response.startswith("[BUDGET]"):
            return False, "error"

        # If query was about system/network but response doesn't contain data
        sys_keywords = ["ip", "dns", "сеть", "network", "диск", "disk", "память",
                       "memory", "процесс", "process", "порт", "port", "сервис",
                       "service", "gpu", "cpu", "сканир", "scan"]
        query_is_sys = any(kw in query.lower() for kw in sys_keywords)
        if query_is_sys:
            # Response should contain actual data (numbers, IPs, paths)
            has_data = bool(re.search(r'\d+\.\d+\.\d+\.\d+|\d+[KMGT]?[Bb]|\d+%|/\w+/', response))
            if not has_data and len(response) > 100:
                # Long response without data = probably generic advice
                return False, "no_data_for_sys_query"

        return True, "ok"


# ══════════════════════════════════════════════════════════════════════
# TRAINING DATA COLLECTOR — Self-Learning (from ai-unified-platform)
# Saves good query-response pairs for future fine-tuning
# ══════════════════════════════════════════════════════════════════════

class TrainingCollector:
    """Collects good responses for self-learning."""

    def __init__(self, training_file=TRAINING_FILE):
        self.training_file = training_file

    def save(self, query, response, expert, model, quality_score=1.0):
        """Save a good response as training data."""
        try:
            entry = {
                "query": query,
                "response": response[:3000],
                "expert": expert,
                "model": model,
                "quality": quality_score,
                "timestamp": datetime.now().isoformat(),
            }
            with open(self.training_file, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except:
            pass

    def count(self):
        """Count training entries."""
        try:
            if os.path.exists(self.training_file):
                with open(self.training_file) as f:
                    return sum(1 for _ in f)
        except:
            pass
        return 0


# ══════════════════════════════════════════════════════════════════════
# SMART EXECUTOR — Execute-first approach (core of v4.x)
# Runs commands LOCALLY before sending to AI for analysis
# ══════════════════════════════════════════════════════════════════════

class SmartExecutor:
    """Execute system commands based on query patterns."""

    def __init__(self, patterns=SMART_PATTERNS, scan_keywords=SCAN_KEYWORDS):
        self.patterns = patterns
        self.scan_keywords = scan_keywords

    def match(self, query):
        """Find matching pattern for a query."""
        query_low = query.lower()

        # Check scan keywords first (special handling)
        for kw in self.scan_keywords:
            if kw in query_low:
                return self._get_scan_commands(), "sysadmin"

        # Check smart patterns
        for keywords, commands, category in self.patterns:
            for kw in keywords:
                if kw in query_low:
                    return commands, category

        return None, None

    def _get_scan_commands(self):
        """Get network scan commands."""
        return [
            "echo '=== ARP Table ===' && arp -an 2>/dev/null | grep -v incomplete | head -50",
            "echo '=== Network Interfaces ===' && ifconfig 2>/dev/null | grep -E 'inet |flags' || ip addr show 2>/dev/null | grep -E 'inet |state'",
            "echo '=== Default Route ===' && netstat -rn 2>/dev/null | grep default | head -3 || ip route show default 2>/dev/null",
            "echo '=== Ping Scan ===' && (fping -a -g $(ifconfig 2>/dev/null | grep 'inet ' | grep -v 127.0.0.1 | head -1 | awk '{print $2}' | sed 's/\\.[0-9]*$/.0\\/24/') 2>/dev/null || echo 'fping not available, using arp') | head -60",
        ]

    def execute(self, commands, timeout=30):
        """Execute commands and collect results with progress indication."""
        results = []
        total = len(commands)
        progress = ProgressBar(total, label="Collecting data", color=TOOL_CLR)

        for i, cmd in enumerate(commands):
            cmd_short = cmd.split('|')[0].strip()[:50]
            progress.update(cmd_short)

            try:
                t0 = time.time()
                proc = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True,
                    timeout=timeout
                )
                dt = time.time() - t0
                output = proc.stdout.strip()
                if proc.stderr.strip() and not output:
                    output = proc.stderr.strip()
                if output:
                    results.append(f"$ {cmd_short}...\n{output}")
            except subprocess.TimeoutExpired:
                results.append(f"$ {cmd[:40]}... [TIMEOUT after {timeout}s]")
            except Exception as e:
                results.append(f"$ {cmd[:40]}... [ERROR: {e}]")

        progress.finish(f"Collected {len(results)}/{total} data sources")
        return "\n\n".join(results) if results else ""

    def is_sysadmin_query(self, query):
        """Check if query is system/network related (should execute first)."""
        query_low = query.lower()

        # Direct command requests
        if any(query_low.startswith(prefix) for prefix in
               ["sudo ", "ls ", "cat ", "grep ", "find ", "ps ", "df ", "du ",
                "top ", "free ", "ping ", "curl ", "wget ", "ssh ", "scp ",
                "docker ", "systemctl ", "journalctl ", "iptables ", "ufw ",
                "nmap ", "netstat ", "ss ", "lsof ", "kill ", "apt ", "brew ",
                "pip ", "npm ", "git ", "cd ", "mkdir ", "rm ", "cp ", "mv ",
                "chmod ", "chown ", "tar ", "zip ", "unzip "]):
            return True

        # Sysadmin keywords
        sysadmin_kw = [
            "сервер", "server", "сеть", "network", "порт", "port",
            "процесс", "process", "диск", "disk", "память", "memory",
            "cpu", "gpu", "лог", "log", "сервис", "service",
            "docker", "контейнер", "firewall", "dns", "ip",
            "ssh", "ping", "traceroute", "nmap", "scan",
            "мониторинг", "monitoring", "статус", "status",
            "перезапусти", "restart", "останови", "stop",
            "запусти", "start", "установи", "install",
            "обнови", "update", "upgrade", "почини", "fix",
            "проверь", "check", "покажи", "show", "найди", "find",
            "сканируй", "просканируй", "ollama", "модел",
            "роутер", "router", "mikrotik", "proxmox",
            "vpn", "wireguard", "tailscale",
        ]
        return any(kw in query_low for kw in sysadmin_kw)


# ══════════════════════════════════════════════════════════════════════
# NETWORK SCANNER — Built-in network scanning (doesn't depend on AI)
# ══════════════════════════════════════════════════════════════════════

class NetworkScanner:
    """Built-in network scanner for local network discovery."""

    @staticmethod
    def get_local_networks():
        """Get local network interfaces and subnets."""
        networks = []
        try:
            result = subprocess.run(
                "ifconfig 2>/dev/null || ip addr show 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                match = re.search(r'inet (\d+\.\d+\.\d+\.\d+).*?(?:netmask |/(\d+))', line)
                if match:
                    ip = match.group(1)
                    if not ip.startswith("127."):
                        networks.append(ip)
        except:
            pass
        return networks

    @staticmethod
    def scan_subnet(subnet, timeout=10):
        """Scan a subnet for active hosts."""
        active = []
        try:
            # Try fping first (fastest)
            result = subprocess.run(
                f"fping -a -g {subnet} 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=timeout
            )
            if result.stdout.strip():
                active = result.stdout.strip().split("\n")
                return active
        except:
            pass

        # Fallback to ARP table
        try:
            result = subprocess.run(
                "arp -an 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                if match and "incomplete" not in line:
                    active.append(match.group(1))
        except:
            pass

        return active

    @staticmethod
    def format_scan_results(networks, hosts):
        """Format scan results as a nice table."""
        lines = ["=== Network Scan Results ===\n"]
        lines.append(f"Local IPs: {', '.join(networks)}")
        lines.append(f"Active hosts found: {len(hosts)}\n")

        if hosts:
            lines.append("Active hosts:")
            for i, host in enumerate(sorted(hosts, key=lambda x: [int(p) for p in x.split(".")]), 1):
                lines.append(f"  {i:3d}. {host}")

        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
# SSH MANAGER — Execute commands on remote hosts
# ══════════════════════════════════════════════════════════════════════

class SSHManager:
    """Execute commands on remote hosts via SSH."""

    @staticmethod
    def execute(host_info, command, timeout=30):
        """Execute command on remote host."""
        ip = host_info.get("ip")
        user = host_info.get("user", "root")
        password = host_info.get("pass", "")
        port = host_info.get("port", 22)

        ssh_cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p {port} {user}@{ip} '{command}'"

        try:
            result = subprocess.run(
                ssh_cmd, shell=True, capture_output=True, text=True,
                timeout=timeout
            )
            output = result.stdout.strip()
            if result.stderr.strip() and not output:
                output = result.stderr.strip()
            return output
        except subprocess.TimeoutExpired:
            return f"[TIMEOUT after {timeout}s]"
        except Exception as e:
            return f"[ERROR: {e}]"

    @staticmethod
    def check_host(host_info, timeout=5):
        """Quick check if host is reachable."""
        ip = host_info.get("ip")
        port = host_info.get("port", 22)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False


# ══════════════════════════════════════════════════════════════════════
# SCLG-AI MAIN CLASS — The Agent
# ══════════════════════════════════════════════════════════════════════

class SclgAI:
    """Scoliologic AI Console — Autonomous DevOps Agent."""

    def __init__(self):
        # Core components
        self.ollama = OllamaClient()
        self.claude = ClaudeClient()
        self.router = ExpertRouter()
        self.executor = SmartExecutor()
        self.scanner = NetworkScanner()
        self.ssh = SSHManager()
        self.quality = QualityChecker()
        self.cleaner = ResponseCleaner()
        self.memory = DreamMemory()
        self.cache = RequestCache()
        self.stats = StatsTracker()
        self.training = TrainingCollector()

        # State
        self.conversation = []
        self.current_model = None
        self.current_expert = None
        self.auto_route = True
        self.agent_mode = True
        self.claude_ok = False
        self.ollama_ok = False
        self.model_count = 0
        self.host_count = len(KNOWN_HOSTS)

        # Initialize
        self._init_readline()

    def _init_readline(self):
        """Initialize readline with history."""
        try:
            readline.read_history_file(HISTORY_FILE)
        except:
            pass
        readline.set_history_length(1000)

    def _save_history(self):
        try:
            readline.write_history_file(HISTORY_FILE)
        except:
            pass

    # ── Connection Check ────────────────────────────────────────────

    def check_connections(self):
        """Check all connections on startup with animated feedback."""
        # Check Ollama/GPU Balancer
        spinner = Spinner("Connecting to GPU Balancer", color=TOOL_CLR, style="dots")
        spinner.start()
        self.ollama_ok = self.ollama.check_connection()
        if self.ollama_ok:
            self.model_count = len(self.ollama.available_models)
            spinner.stop(f"✓ GPU Balancer: {self.model_count} models")
        else:
            spinner.stop()
            print(f"  {ERROR_CLR}✗ GPU Balancer offline{C.RESET}")

        # Check Claude
        spinner2 = Spinner("Checking Claude API", color=CLAUDE_CLR, style="dots")
        spinner2.start()
        self.claude_ok = self.claude.test_connection()
        if self.claude_ok:
            remaining = self.claude.remaining_today()
            spinner2.stop(f"✓ Claude OK ({remaining}/{CLAUDE_DAILY_LIMIT} today)")
        else:
            spinner2.stop()
            print(f"  {WARN_CLR}⚠ Claude unavailable{C.RESET}")

    # ── System Prompt Builder ───────────────────────────────────────

    def _build_system_prompt(self, expert="general", data_context=""):
        """Build system prompt for the AI model."""
        hostname = subprocess.run("hostname", capture_output=True, text=True, timeout=3).stdout.strip() if True else "unknown"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        base = f"""Ты — Scoliologic AI v{VERSION}, автономный DevOps/SysAdmin агент.
Ты работаешь ПРЯМО на машине '{hostname}'. Ты МОЖЕШЬ выполнять команды.
Текущее время: {now}

ПРАВИЛА:
1. НИКОГДА не говори "я не могу выполнить" или "у меня нет доступа" — ты МОЖЕШЬ.
2. Если нужно выполнить команду — генерируй её в теге <cmd>команда</cmd>
3. Если данные уже собраны — АНАЛИЗИРУЙ их, не говори "я не могу".
4. Отвечай КРАТКО и ПО ДЕЛУ. Без воды.
5. Используй русский язык по умолчанию.
6. Не начинай ответ с "Конечно!" или "Безусловно!".
7. Не заканчивай "Если нужно что-то ещё — обращайтесь!".

ИНФРАСТРУКТУРА:
- GPU Balancer: {GPU_BALANCER_URL}
- Кластер: {', '.join(f'{k}({v["ip"]})' for k,v in KNOWN_HOSTS.items())}
"""

        # Add expert-specific hint
        profile = MODEL_PROFILES.get(expert, MODEL_PROFILES["general"])
        base += f"\nРОЛЬ: {profile['system_hint']}\n"

        # Add memory context
        mem_ctx = self.memory.get_context(limit=5)
        if mem_ctx:
            base += f"\n{mem_ctx}\n"

        # Add collected data context
        if data_context:
            base += f"""
═══ СОБРАННЫЕ ДАННЫЕ (выполнены команды на этой машине) ═══
{data_context}
═══ КОНЕЦ ДАННЫХ ═══

ВАЖНО: Данные выше — РЕАЛЬНЫЕ результаты команд, выполненных на ЭТОЙ машине.
Ты ОБЯЗАН проанализировать эти данные и дать конкретный ответ.
НЕ ГОВОРИ "я не могу" — данные УЖЕ собраны для тебя.
"""

        return base

    # ── Core Query Processing ───────────────────────────────────────

    def process_query(self, query):
        """Process a user query — the main brain of the agent."""

        # Step 0: Check cache
        cached = self.cache.get(query)
        if cached:
            self.stats.record("cache", "cache", cache_hit=True)
            print(f"  {DIM_COLOR}(cached){C.RESET}")
            return cached

        # Step 1: Classify query (MoE routing)
        expert, confidence = self.router.classify(query)
        self.current_expert = expert

        # Step 2: Check if this is a direct command to execute
        if self._is_direct_command(query):
            return self._execute_direct_command(query)

        # Step 3: Smart Execute — run commands FIRST if pattern matches
        data_context = ""
        commands, category = self.executor.match(query)
        if commands:
            print(f"  {TOOL_CLR}⚡ Collecting system data...{C.RESET}")
            data_context = self.executor.execute(commands)
            if category:
                expert = category

        # Step 4: If sysadmin query but no pattern matched, try generic commands
        if not data_context and self.executor.is_sysadmin_query(query):
            print(f"  {TOOL_CLR}⚡ Running system check...{C.RESET}")
            generic_cmds = [
                "hostname && uname -a",
                "ifconfig 2>/dev/null | grep 'inet ' || ip addr show 2>/dev/null | grep 'inet '",
            ]
            data_context = self.executor.execute(generic_cmds)

        # Step 5: Get AI response (with spinner)
        spinner = Spinner("Analyzing", color=ACCENT2)
        spinner.start()
        try:
            response = self._get_ai_response(query, expert, data_context, spinner=spinner)
        finally:
            spinner.stop()

        # Step 6: Quality check
        is_good, reason = self.quality.check(response, query)

        if not is_good and reason in ("refusal", "no_data_for_sys_query"):
            # Model refused or gave generic advice — try Claude
            if self.claude_ok and self.claude.can_use():
                claude_spinner = Spinner("Claude re-analyzing", color=CLAUDE_CLR)
                claude_spinner.start()
                try:
                    response = self._claude_fallback(query, data_context, expert)
                finally:
                    claude_spinner.stop(f"Claude responded")
                self.stats.record(expert, "claude", used_claude=True)
            else:
                # No Claude available — try to give data directly
                if data_context:
                    response = f"Вот собранные данные:\n\n{data_context}"
        else:
            model_name = self.current_model or "unknown"
            self.stats.record(expert, model_name)

        # Step 7: Clean response (anti-AI-isms)
        response = self.cleaner.clean(response)

        # Step 8: Process agent commands in response
        response = self._process_agent_commands(response)

        # Step 9: Cache good responses
        if is_good or (not response.startswith("[ERROR]")):
            self.cache.put(query, response, expert)

        # Step 10: Save for training if good
        if is_good:
            self.training.save(query, response, expert, self.current_model or "claude")

        # Step 11: Remember important facts
        self._auto_remember(query, response)

        return response

    def _is_direct_command(self, query):
        """Check if query is a direct shell command."""
        cmd_prefixes = ["sudo ", "ls ", "cat ", "grep ", "find ", "ps ", "df ",
                       "du ", "top ", "free ", "ping ", "curl ", "wget ",
                       "docker ", "systemctl ", "journalctl ", "iptables ",
                       "nmap ", "netstat ", "ss ", "lsof ", "kill ", "apt ",
                       "brew ", "pip ", "npm ", "git ", "cd ", "mkdir ",
                       "rm ", "cp ", "mv ", "chmod ", "chown ", "tar ",
                       "zip ", "unzip ", "head ", "tail ", "wc ", "sort ",
                       "awk ", "sed ", "cut ", "echo ", "which ", "whereis ",
                       "hostname", "uname ", "whoami", "uptime", "date",
                       "ifconfig", "ip addr", "ip route", "route ",
                       "fping ", "traceroute ", "dig ", "nslookup ",
                       "ollama ", "launchctl "]
        return any(query.strip().startswith(p) for p in cmd_prefixes)

    def _execute_direct_command(self, query):
        """Execute a direct shell command with visual feedback."""
        cmd = query.strip()
        cmd_display = cmd[:60] + ('...' if len(cmd) > 60 else '')
        print(f"  {TOOL_CLR}● Bash({cmd_display}){C.RESET}", end="", flush=True)

        try:
            t0 = time.time()
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            dt = time.time() - t0
            output = result.stdout
            if result.stderr:
                output += f"\n{result.stderr}" if output else result.stderr
            if result.returncode != 0:
                print(f"  {ERROR_CLR}✗ {dt:.1f}s{C.RESET}")
                output = f"Exit code {result.returncode}\n{output}"
            else:
                print(f"  {SYSTEM_CLR}✓ {dt:.1f}s{C.RESET}")
            return output.strip() if output.strip() else "(no output)"
        except subprocess.TimeoutExpired:
            print(f"  {ERROR_CLR}✗ timeout{C.RESET}")
            return "[TIMEOUT after 30s]"
        except Exception as e:
            print(f"  {ERROR_CLR}✗ error{C.RESET}")
            return f"[ERROR: {e}]"

    def _get_ai_response(self, query, expert, data_context="", spinner=None):
        """Get response from AI model (local or Claude) with spinner updates."""
        system_prompt = self._build_system_prompt(expert, data_context)

        # Build messages
        messages = []
        # Add last 6 conversation turns for context
        for msg in self.conversation[-6:]:
            messages.append(msg)
        messages.append({"role": "user", "content": query})

        # Try local model first
        if self.ollama_ok:
            config = self.router.get_model_and_config(expert, self.ollama)
            model = config["model"]

            if model:
                self.current_model = model
                model_short = model.split(":")[0] if ":" in model else model
                if spinner:
                    spinner.update(f"{expert} → {model_short}")

                response = self.ollama.chat(
                    model=model,
                    messages=messages,
                    system=system_prompt,
                    temperature=config["temperature"],
                )

                if response and not response.startswith("[ERROR]"):
                    return response
                else:
                    # First model failed — try a smaller/faster model
                    if spinner:
                        spinner.update(f"{model_short} failed, trying fallback...")
                    fallback_models = ["qwen2.5:7b", "gemma2:9b", "llama3.1:8b", "phi3:mini"]
                    fallback_model = self.ollama.find_best_model(fallback_models)
                    if fallback_model and fallback_model != model:
                        fb_short = fallback_model.split(":")[0] if ":" in fallback_model else fallback_model
                        if spinner:
                            spinner.update(f"retry → {fb_short}")
                        self.current_model = fallback_model
                        response = self.ollama.chat(
                            model=fallback_model,
                            messages=messages,
                            system=system_prompt,
                            temperature=config["temperature"],
                            retries=1,
                        )
                        if response and not response.startswith("[ERROR]"):
                            return response

        # Fallback to Claude
        if self.claude_ok and self.claude.can_use():
            if spinner:
                spinner.update("Claude fallback")
            return self._claude_fallback(query, data_context, expert)

        # Last resort: if we have data_context, return it raw
        if data_context:
            return f"Вот собранные данные:\n\n{data_context}"

        return "[ERROR] No AI models available. Check GPU Balancer and Claude API."

    def _claude_fallback(self, query, data_context="", expert="general"):
        """Use Claude as fallback."""
        system_prompt = self._build_system_prompt(expert, data_context)

        messages = []
        for msg in self.conversation[-4:]:
            messages.append(msg)
        messages.append({"role": "user", "content": query})

        self.current_model = "claude"
        response = self.claude.chat(
            messages=messages,
            system=system_prompt,
        )
        return response

    def _process_agent_commands(self, response):
        """Process <cmd>...</cmd> tags in AI response — execute commands."""
        cmd_pattern = re.compile(r'<cmd>(.*?)</cmd>', re.DOTALL)
        matches = cmd_pattern.findall(response)

        if not matches:
            return response

        # Execute each command and append results
        result_text = response
        for cmd in matches:
            cmd = cmd.strip()
            if not cmd:
                continue

            cmd_display = cmd[:60] + ('...' if len(cmd) > 60 else '')
            print(f"  {TOOL_CLR}● Bash({cmd_display}){C.RESET}", end="", flush=True)

            try:
                t0 = time.time()
                proc = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30
                )
                dt = time.time() - t0
                output = proc.stdout.strip()
                if proc.stderr.strip():
                    output += f"\n{proc.stderr.strip()}" if output else proc.stderr.strip()

                if proc.returncode == 0:
                    print(f"  {SYSTEM_CLR}✓ {dt:.1f}s{C.RESET}")
                else:
                    print(f"  {WARN_CLR}⚠ exit {proc.returncode} {dt:.1f}s{C.RESET}")

                # Replace the <cmd> tag with the output
                tag = f"<cmd>{cmd}</cmd>"
                replacement = f"```\n$ {cmd}\n{output}\n```"
                result_text = result_text.replace(tag, replacement, 1)

            except subprocess.TimeoutExpired:
                print(f"  {ERROR_CLR}✗ timeout{C.RESET}")
                tag = f"<cmd>{cmd}</cmd>"
                result_text = result_text.replace(tag, f"```\n$ {cmd}\n[TIMEOUT]\n```", 1)
            except Exception as e:
                print(f"  {ERROR_CLR}✗ error{C.RESET}")
                tag = f"<cmd>{cmd}</cmd>"
                result_text = result_text.replace(tag, f"```\n$ {cmd}\n[ERROR: {e}]\n```", 1)

        return result_text

    def _auto_remember(self, query, response):
        """Auto-remember important facts from conversation."""
        # Remember IP addresses, hostnames, errors
        ip_pattern = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b')
        ips = ip_pattern.findall(response)
        if ips and len(ips) <= 5:
            for ip in ips:
                if not ip.startswith("127.") and not ip.startswith("0."):
                    self.memory.remember(f"IP found: {ip} (query: {query[:50]})")

        # Remember errors
        if "error" in response.lower() or "failed" in response.lower():
            self.memory.remember(f"Error detected: {query[:80]}", importance="high")

    # ── Slash Commands ──────────────────────────────────────────────

    def handle_slash_command(self, cmd):
        """Handle /command inputs."""
        parts = cmd.strip().split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command in ("/help", "/h", "/?"):
            self._show_help()
        elif command in ("/models", "/m"):
            self._show_models()
        elif command in ("/hosts", "/nodes"):
            self._show_hosts()
        elif command in ("/stats", "/stat"):
            self._show_stats()
        elif command in ("/memory", "/mem"):
            self._show_memory()
        elif command in ("/clear", "/c"):
            self.conversation = []
            print(f"  {SYSTEM_CLR}Conversation cleared{C.RESET}")
        elif command in ("/new", "/n"):
            self.conversation = []
            self.memory.consolidate()
            print(f"  {SYSTEM_CLR}New session started, memory consolidated{C.RESET}")
        elif command in ("/scan", "/s"):
            self._do_scan(args)
        elif command in ("/ssh",):
            self._do_ssh(args)
        elif command in ("/claude",):
            self._force_claude(args)
        elif command in ("/version", "/v"):
            print(f"  sclg-ai v{VERSION}")
        elif command in ("/quit", "/q", "/exit"):
            return "QUIT"
        else:
            print(f"  {WARN_CLR}Unknown command: {command}. Type /help{C.RESET}")

        return None

    def _show_help(self):
        print(f"""
{ACCENT}━━━ Commands ━━━{C.RESET}
  {TOOL_CLR}/models{C.RESET}    — Show available AI models
  {TOOL_CLR}/hosts{C.RESET}     — Show known infrastructure hosts
  {TOOL_CLR}/stats{C.RESET}     — Show usage statistics
  {TOOL_CLR}/memory{C.RESET}    — Show agent memory
  {TOOL_CLR}/scan{C.RESET} [net] — Scan network
  {TOOL_CLR}/ssh{C.RESET} host cmd — Execute command on remote host
  {TOOL_CLR}/claude{C.RESET} q  — Force Claude for this query
  {TOOL_CLR}/clear{C.RESET}     — Clear conversation
  {TOOL_CLR}/new{C.RESET}       — New session (consolidate memory)
  {TOOL_CLR}/version{C.RESET}   — Show version
  {TOOL_CLR}/quit{C.RESET}      — Exit
""")

    def _show_models(self):
        models = self.ollama.get_models(force=True)
        if models:
            print(f"\n  {TOOL_CLR}Available models ({len(models)}):{C.RESET}")
            for m in sorted(models):
                print(f"    • {m}")
        else:
            print(f"  {WARN_CLR}No models available{C.RESET}")

        if self.claude_ok:
            r = self.claude.remaining_today()
            print(f"\n  {CLAUDE_CLR}Claude: {r}/{CLAUDE_DAILY_LIMIT} remaining today{C.RESET}")

    def _show_hosts(self):
        host_spinner = Spinner("Checking hosts", color=TOOL_CLR, style="dots")
        host_spinner.start()
        host_statuses = {}
        for name, info in KNOWN_HOSTS.items():
            host_spinner.update(f"{name} ({info['ip']})")
            host_statuses[name] = SSHManager.check_host(info, timeout=2)
        host_spinner.stop(f"Checked {len(KNOWN_HOSTS)} hosts")

        print(f"\n  {TOOL_CLR}Known hosts ({len(KNOWN_HOSTS)}):{C.RESET}")
        for name, info in KNOWN_HOSTS.items():
            status = "●" if host_statuses.get(name) else "○"
            color = SYSTEM_CLR if status == "●" else DIM_COLOR
            print(f"    {color}{status} {name:15s} {info['ip']:18s} {info.get('desc', '')}{C.RESET}")

    def _show_stats(self):
        print(f"\n  {TOOL_CLR}Statistics:{C.RESET}")
        print(f"  {self.stats.summary()}")
        print(f"  Training data: {self.training.count()} entries")
        cs = self.cache.stats()
        print(f"  Cache: {cs['active']} active / {cs['total']} total")

    def _show_memory(self):
        facts = self.memory.recall(limit=15)
        if facts:
            print(f"\n  {MEMORY_CLR}Memory ({len(facts)} facts):{C.RESET}")
            for f in facts:
                imp = f.get("importance", "normal")
                icon = "★" if imp in ("high", "critical") else "·"
                print(f"    {icon} {f['fact'][:80]}")
        else:
            print(f"  {DIM_COLOR}Memory is empty{C.RESET}")

    def _do_scan(self, args):
        """Execute network scan with spinner."""
        networks = self.scanner.get_local_networks()
        if not networks:
            print(f"  {WARN_CLR}No network interfaces found{C.RESET}")
            return

        target = args.strip() if args else None
        if not target:
            # Auto-detect subnet
            target = networks[0].rsplit(".", 1)[0] + ".0/24"

        scan_spinner = Spinner(f"Scanning {target}", color=NET_CLR)
        scan_spinner.start()
        hosts = self.scanner.scan_subnet(target, timeout=15)
        scan_spinner.stop(f"Found {len(hosts)} active hosts in {target}")
        result = self.scanner.format_scan_results(networks, hosts)
        print(f"\n{result}")

        # Remember scan results
        self.memory.remember(f"Network scan {target}: {len(hosts)} hosts found", importance="high")

    def _do_ssh(self, args):
        """Execute SSH command on remote host."""
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            print(f"  Usage: /ssh <host> <command>")
            print(f"  Hosts: {', '.join(KNOWN_HOSTS.keys())}")
            return

        host_name, command = parts
        host_info = KNOWN_HOSTS.get(host_name)
        if not host_info:
            print(f"  {ERROR_CLR}Unknown host: {host_name}{C.RESET}")
            return

        ssh_spinner = Spinner(f"SSH {host_name}", color=TOOL_CLR)
        ssh_spinner.start()
        ssh_spinner.update(f"{host_info['ip']}: {command[:40]}")
        result = self.ssh.execute(host_info, command)
        ssh_spinner.stop(f"SSH {host_name} complete")
        print(f"\n{result}")

    def _force_claude(self, query):
        """Force Claude for a specific query."""
        if not query:
            print(f"  Usage: /claude <your question>")
            return
        if not self.claude_ok:
            print(f"  {ERROR_CLR}Claude is not available{C.RESET}")
            return

        claude_sp = Spinner("Claude thinking", color=CLAUDE_CLR)
        claude_sp.start()
        response = self._claude_fallback(query)
        claude_sp.stop("Claude responded")
        response = self.cleaner.clean(response)
        print(f"\n{AI_COLOR}{response}{C.RESET}")

    # ── Banner ──────────────────────────────────────────────────────

    def show_banner(self):
        """Show startup banner."""
        w = get_terminal_width()
        clear_screen()

        # Title
        title = f"Scoliologic AI v{VERSION}"
        title_line = f"┤ {title} ├"
        pad = (w - len(title_line)) // 2
        print(f"{ACCENT}{'─' * pad}{title_line}{'─' * (w - pad - len(title_line))}{C.RESET}")

        # Logo + info
        print(f"""
{LOGO_CLR}{CLAW_MINI}{C.RESET}
  {C.BOLD}Welcome back ilea{C.RESET}         {ACCENT}DevOps Agent{C.RESET}
                              {SYSTEM_CLR}⚡ Execute & fix systems{C.RESET}
                              {NET_CLR}● Scan networks & ports{C.RESET}
                              {TOOL_CLR}✎ SSH to any host/router{C.RESET}
                              {CLAUDE_CLR}🧠 MoE expert routing{C.RESET}
                              {MEMORY_CLR}💭 Dream memory{C.RESET}
""")

    def show_status(self):
        """Show connection status line."""
        networks = self.scanner.get_local_networks()
        net_str = ", ".join(f"{ip}/24" for ip in networks[:2]) if networks else "unknown"

        parts = []
        if self.ollama_ok:
            parts.append(f"{SYSTEM_CLR}Connected{C.RESET}")
        else:
            parts.append(f"{ERROR_CLR}Offline{C.RESET}")

        if self.claude_ok:
            parts.append(f"{CLAUDE_CLR}Claude OK{C.RESET}")
        else:
            parts.append(f"{WARN_CLR}Claude ✗{C.RESET}")

        if self.auto_route:
            parts.append(f"{ACCENT2}Auto-Route{C.RESET}")
        if self.agent_mode:
            parts.append(f"{SYSTEM_CLR}Agent ON{C.RESET}")

        print(f"  {NET_CLR}Networks: {net_str}{C.RESET}")
        print(f"  {' • '.join(parts)}")
        print(f"  {DIM_COLOR}{self.model_count} models · {self.host_count} hosts · Claude: {self.claude.remaining_today()}/{CLAUDE_DAILY_LIMIT} today, {self.claude.remaining_month()}/{CLAUDE_MONTHLY_LIMIT} this month{C.RESET}")
        print()

    # ── Main Loop ───────────────────────────────────────────────────

    def run(self):
        """Main interactive loop."""
        self.show_banner()
        self.check_connections()
        self.show_status()
        draw_hline()

        while True:
            try:
                # Prompt
                expert_icon = {"code": "⚙", "sysadmin": "🔧", "analysis": "📊",
                              "creative": "✏", "general": "●"}.get(self.current_expert or "general", "●")
                mode = "auto" if self.auto_route else (self.current_model or "?")

                prompt = f"\n{PROMPT_CLR}❯ {mode} {expert_icon}{C.RESET} "
                user_input = input(prompt).strip()

                if not user_input:
                    continue

                # Slash commands
                if user_input.startswith("/"):
                    result = self.handle_slash_command(user_input)
                    if result == "QUIT":
                        break
                    continue

                # Process query
                draw_dashed()
                start_time = time.time()

                response = self.process_query(user_input)

                elapsed = time.time() - start_time

                # Display response
                print(f"\n{AI_COLOR}{response}{C.RESET}")

                # Show metadata
                model_str = self.current_model or "?"
                if ":" in model_str:
                    model_str = model_str.split(":")[0]
                expert_str = self.current_expert or "general"
                print(f"\n  {DIM_COLOR}⟨{expert_str} → {model_str} · {elapsed:.1f}s⟩{C.RESET}")

                # Update conversation
                self.conversation.append({"role": "user", "content": user_input})
                self.conversation.append({"role": "assistant", "content": response[:2000]})

                # Keep conversation manageable
                if len(self.conversation) > 20:
                    self.conversation = self.conversation[-12:]

            except KeyboardInterrupt:
                print(f"\n  {DIM_COLOR}(Ctrl+C to exit, /quit to quit){C.RESET}")
                continue
            except EOFError:
                break

        # Cleanup
        self._save_history()
        self.memory.consolidate()
        print(f"\n{DIM_COLOR}Session saved. Goodbye.{C.RESET}")


# ══════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

def main():
    """Main entry point."""
    # Handle --version
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-v", "version"):
        print(f"sclg-ai v{VERSION}")
        sys.exit(0)

    # Handle --help
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h", "help"):
        print(f"""sclg-ai v{VERSION} — Scoliologic AI Console

Usage:
  sclg-ai              Start interactive console
  sclg-ai --version    Show version
  sclg-ai --help       Show this help
  sclg-ai -e "query"   Execute single query and exit
  sclg-ai --scan       Quick network scan
  sclg-ai --hosts      Show known hosts
  sclg-ai --stats      Show usage statistics
""")
        sys.exit(0)

    # Handle -e "query" (single execution)
    if len(sys.argv) > 2 and sys.argv[1] in ("-e", "--exec"):
        query = " ".join(sys.argv[2:])
        agent = SclgAI()
        agent.ollama_ok = agent.ollama.check_connection()
        agent.claude_ok = agent.claude.test_connection()
        response = agent.process_query(query)
        print(response)
        sys.exit(0)

    # Handle --scan
    if len(sys.argv) > 1 and sys.argv[1] == "--scan":
        agent = SclgAI()
        agent._do_scan("")
        sys.exit(0)

    # Handle --hosts
    if len(sys.argv) > 1 and sys.argv[1] == "--hosts":
        agent = SclgAI()
        agent._show_hosts()
        sys.exit(0)

    # Handle --stats
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        agent = SclgAI()
        agent._show_stats()
        sys.exit(0)

    # Interactive mode
    agent = SclgAI()

    # Handle signals
    def sigint_handler(sig, frame):
        pass  # Handled in main loop
    signal.signal(signal.SIGINT, sigint_handler)

    agent.run()


if __name__ == "__main__":
    main()
