#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║  Scoliologic AI Console (sclg-ai) v5.0.0                 ║
║  Autonomous DevOps/SysAdmin Agent                        ║
║  Execute first, explain later — like Claude Code          ║
║                                                           ║
║  Integrated ideas from:                                   ║
║  - ai-unified-platform (parallel inference, caching)      ║
║  - ai-router-moe (MoE expert routing, YAML config)       ║
║  - local-ai-assistant (monitoring, roles)                 ║
║  - nanobot (Dream memory, skills, lifecycle hooks)        ║
║  - avoid-ai-writing (anti-AI-isms post-processor)         ║
║  - InfraLearner (background self-learning from Grafana)    ║
║  - nearai/ironclaw (streaming, tool calling, agent loop)  ║
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
import ssl
import threading
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import defaultdict

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

VERSION = "5.2.0"
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
KNOWLEDGE_DIR    = os.path.join(DATA_DIR, "knowledge")
BASELINES_FILE   = os.path.join(KNOWLEDGE_DIR, "baselines", "baselines.json")
INSIGHTS_FILE    = os.path.join(KNOWLEDGE_DIR, "insights", "insights.json")
ANOMALIES_FILE   = os.path.join(KNOWLEDGE_DIR, "anomalies", "recent.json")
LEARNER_STATS_FILE = os.path.join(KNOWLEDGE_DIR, "stats.json")
PRIORITY_LOCK    = os.path.join(KNOWLEDGE_DIR, "priority.lock")

# ── Grafana / Monitoring ───────────────────────────────────────────

GRAFANA_URL   = os.environ.get("GRAFANA_URL", "https://grafana.sclg.io")
GRAFANA_TOKEN = os.environ.get("GRAFANA_TOKEN", "")
PROMETHEUS_DS_UID = "efdhopzhssvswb"  # Grafana datasource UID for Prometheus
LOKI_DS_UID       = "P8E80F9AEF21F6940"

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SKILLS_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
os.makedirs(os.path.join(KNOWLEDGE_DIR, "baselines"), exist_ok=True)
os.makedirs(os.path.join(KNOWLEDGE_DIR, "insights"), exist_ok=True)
os.makedirs(os.path.join(KNOWLEDGE_DIR, "anomalies"), exist_ok=True)
os.makedirs(os.path.join(KNOWLEDGE_DIR, "metrics"), exist_ok=True)

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
        "models": ["sclg-coder:32b", "qwen2.5-coder-tools:32b", "qwen2.5-coder:14b", "qwen2.5-coder:7b"],
        "keywords": ["код", "code", "python", "bash", "script", "скрипт", "debug",
            "ошибка", "error", "bug", "функция", "function", "class", "def ",
            "import", "docker", "yaml", "json", "api", "http", "sql", "git",
            "npm", "pip", "nginx", "systemd", "ansible", "terraform"],
        "temperature": 0.2,
        "system_hint": "Ты опытный программист. Пиши чистый, рабочий код. Объясняй кратко.",
    },
    "sysadmin": {
        "models": ["sclg-devops:27b", "qwen3.5-27b-hf:latest", "gemma4-26b-hf:latest", "phi4:14b", "qwen2.5:14b", "sclg-fast:7b", "mistral:7b"],
        "keywords": ["сервер", "server", "ssh", "network", "сеть", "firewall",
            "iptables", "dns", "ip", "ping", "traceroute", "диск", "disk",
            "memory", "cpu", "gpu", "nvidia", "процесс", "process",
            "kill", "systemctl", "service", "лог", "log", "порт", "port",
            "proxmox", "vm", "vpn", "ssl", "tls", "cert", "сканир", "scan",
            "почини", "исправь", "fix", "проверь", "status", "мониторинг",
            "ollama", "роутер", "router", "mikrotik", "dhcp", "nat",
            "мис", "mis", "медицинская информационная"],
        "temperature": 0.3,
        "system_hint": "Ты DevOps/SysAdmin эксперт. Выполняй команды и анализируй результаты.",
    },
    "analysis": {
        "models": ["gemma4-26b-hf:latest", "glm-4.7-flash-hf:latest", "phi4:14b", "qwen3.5-27b-hf:latest", "sclg-general:14b"],
        "keywords": ["анализ", "analys", "data", "данные", "статистик",
            "медицин", "medical", "сколиоз", "исследован", "research"],
        "temperature": 0.3,
        "system_hint": "Ты аналитик данных. Давай структурированный анализ с выводами.",
    },
    "creative": {
        "models": ["glm-4.7-flash-hf:latest", "gemma4-26b-hf:latest", "qwen3.5-27b-hf:latest", "llama3.1:8b"],
        "keywords": ["напиши", "write", "текст", "статья", "перевод",
            "резюме", "summary", "письмо", "email", "отчёт", "report"],
        "temperature": 0.7,
        "system_hint": "Ты писатель. Создавай грамотный, структурированный контент.",
    },
    "general": {
        "models": ["sclg-general:14b", "gemma4-26b-hf:latest", "glm-4.7-flash-hf:latest", "qwen3.5-27b-hf:latest", "phi4:14b", "qwen2.5:14b", "sclg-fast:7b", "llama3.1:8b"],
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

    # ── Speed Test / Bandwidth ──
    (["скорость сети", "скорость интернет", "speed test", "speedtest", "bandwidth",
      "пропускная способность", "скорость соединения", "скорость подключения",
      "проверь скорость", "тест скорости", "internet speed", "download speed",
      "upload speed", "скорость загрузки", "скорость скачивания", "пинг до",
      "latency", "задержка сети"],
     ["echo '=== Speed Test ===' && (speedtest-cli --simple 2>/dev/null || speedtest --simple 2>/dev/null || (echo 'speedtest-cli не установлен, используем curl...' && echo -n 'Download: ' && curl -s -o /dev/null -w '%{speed_download}' http://speedtest.tele2.net/10MB.zip 2>/dev/null | python3 -c \"import sys; b=float(sys.stdin.read()); print(f'{b/1024/1024:.2f} MB/s')\" && echo -n 'Upload: ' && dd if=/dev/zero bs=1M count=5 2>/dev/null | curl -s -o /dev/null -w '%{speed_upload}' -X POST -d @- http://speedtest.tele2.net/upload.php 2>/dev/null | python3 -c \"import sys; b=float(sys.stdin.read()); print(f'{b/1024/1024:.2f} MB/s')\"))",
      "echo '=== Ping Test ===' && ping -c 5 8.8.8.8 2>/dev/null | tail -3",
      "echo '=== DNS Speed ===' && (time nslookup google.com 2>&1 | grep -E 'real|Address') 2>&1 | head -5",
      "echo '=== Route ===' && traceroute -m 5 8.8.8.8 2>/dev/null || tracepath -m 5 8.8.8.8 2>/dev/null || echo 'traceroute not available'"],
     "sysadmin"),

    # ── Ping / Connectivity ──
    (["пингани", "пинг ", "ping ", "пропингуй", "достучаться до", "доступен ли",
      "проверь связь", "проверь доступность", "check connectivity"],
     ["ping -c 4 8.8.8.8 2>/dev/null",
      "ping -c 4 1.1.1.1 2>/dev/null",
      "curl -s -o /dev/null -w 'HTTP %{http_code} in %{time_total}s' https://google.com 2>/dev/null"],
     "sysadmin"),

    # ── Temperature / Hardware Health ──
    (["температур", "temperature", "нагрев", "перегрев", "thermal", "fan", "вентилятор"],
     ["echo '=== CPU Temperature ===' && (cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | while read t; do echo $((t/1000))°C; done || sudo powermetrics --samplers smc -i1 -n1 2>/dev/null | grep -i temp || echo 'Нет данных о температуре')",
      "echo '=== GPU Temperature ===' && (nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo 'Нет NVIDIA GPU')"],
     "sysadmin"),

    # ── WiFi ──
    (["wifi", "wi-fi", "вайфай", "wireless", "беспроводн"],
     ["echo '=== WiFi Info ===' && (/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I 2>/dev/null || iwconfig 2>/dev/null || nmcli dev wifi list 2>/dev/null || echo 'Нет WiFi данных')"],
     "sysadmin"),

    # ── Grafana / Dashboards ──
    (["grafana", "графана", "дашборд", "dashboard", "панель мониторинга", "панель grafana"],
     ["echo '=== Grafana Dashboards ===' && curl -s -H \"Authorization: Bearer $GRAFANA_TOKEN\" \"$GRAFANA_URL/api/search?type=dash-db\" 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(f'- {m[\\\"title\\\"]} (uid: {m[\\\"uid\\\"]})') for m in d]\" || echo 'Grafana API недоступен'",
      "echo '=== Recent Alerts ===' && curl -s -H \"Authorization: Bearer $GRAFANA_TOKEN\" \"$GRAFANA_URL/api/alerts\" 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(f'- {a[\\\"name\\\"]} [{a[\\\"state\\\"]}]') for a in d[:10]]\" || echo 'Alerts API недоступен'"],
     "sysadmin"),

    # ── Alerts / Monitoring ──
    (["алерт", "alert", "проверь алерт", "покажи алерт", "тревог",
      "мониторинг", "monitoring", "проверь мониторинг",
      "что с серверами", "статус серверов", "статус кластера",
      "что случилось", "есть проблемы", "всё ли ок", "все ли ок",
      "check alerts", "show alerts", "any problems", "cluster status"],
     ["echo '=== Grafana Alerts ===' && curl -s -H \"Authorization: Bearer $GRAFANA_TOKEN\" \"$GRAFANA_URL/api/alertmanager/grafana/api/v2/alerts\" 2>/dev/null | python3 -c \"import sys,json; alerts=json.load(sys.stdin); print(f'Active alerts: {len(alerts)}'); [print(f'  [{a.get(\\\"status\\\",{}).get(\\\"state\\\",\\\"?\\\")]}: {a.get(\\\"labels\\\",{}).get(\\\"alertname\\\",\\\"?\\\")} - {a.get(\\\"annotations\\\",{}).get(\\\"summary\\\",\\\"\\\")}') for a in alerts[:15]]\" 2>/dev/null || echo 'Grafana Alertmanager недоступен'",
      "echo '=== Prometheus Alerts ===' && curl -s 'http://10.0.0.229:9090/api/v1/alerts' 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); alerts=d.get('data',{}).get('alerts',[]); print(f'Prometheus alerts: {len(alerts)}'); [print(f'  [{a[\\\"state\\\"]}] {a[\\\"labels\\\"].get(\\\"alertname\\\",\\\"?\\\")} - {a.get(\\\"annotations\\\",{}).get(\\\"summary\\\",\\\"\\\")}') for a in alerts[:15]]\" 2>/dev/null || echo 'Prometheus недоступен'",
      "echo '=== Node Health ===' && curl -s 'http://10.0.0.229:9090/api/v1/query?query=up' 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); results=d.get('data',{}).get('result',[]); [print(f'  {r[\\\"metric\\\"].get(\\\"instance\\\",\\\"?\\\")}: {\\\"UP\\\" if r[\\\"value\\\"][1]==\\\"1\\\" else \\\"DOWN\\\"}') for r in results[:20]]\" 2>/dev/null || echo 'Prometheus недоступен'",
      "echo '=== System Logs (errors last 1h) ===' && log show --last 1h --predicate 'eventMessage contains \\\"error\\\" or eventMessage contains \\\"fail\\\"' --style compact 2>/dev/null | tail -15 || journalctl -p err --since '1 hour ago' --no-pager -n 15 2>/dev/null || echo 'Нет логов'"],
     "sysadmin"),

    # ── Prometheus metrics ──
    (["prometheus", "прометеус", "метрики", "metrics", "нагрузка кластер",
      "статус нод", "node status", "здоровье кластер", "cluster health"],
     ["echo '=== GPU Metrics ===' && curl -s 'http://10.0.0.229:9090/api/v1/query?query=nvidia_smi_gpu_temp' 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(f'  {r[\\\"metric\\\"].get(\\\"instance\\\",\\\"?\\\")}: {r[\\\"value\\\"][1]}C') for r in d.get('data',{}).get('result',[])]\" 2>/dev/null || echo 'GPU metrics недоступны'",
      "echo '=== VRAM Usage ===' && curl -s 'http://10.0.0.229:9090/api/v1/query?query=nvidia_smi_memory_used_bytes/(1024*1024*1024)' 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(f'  {r[\\\"metric\\\"].get(\\\"instance\\\",\\\"?\\\")}: {float(r[\\\"value\\\"][1]):.1f} GB') for r in d.get('data',{}).get('result',[])]\" 2>/dev/null || echo 'VRAM metrics недоступны'",
      "echo '=== CPU Usage ===' && curl -s 'http://10.0.0.229:9090/api/v1/query?query=100-(avg(rate(node_cpu_seconds_total{mode=\\\"idle\\\"}[5m]))by(instance)*100)' 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(f'  {r[\\\"metric\\\"].get(\\\"instance\\\",\\\"?\\\")}: {float(r[\\\"value\\\"][1]):.1f}%') for r in d.get('data',{}).get('result',[])]\" 2>/dev/null || echo 'CPU metrics недоступны'"],
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

    # LLM control tokens that must NEVER appear in output
    TOXIC_TOKENS = [
        "<|endoftext|>", "<|im_start|>", "<|im_end|>",
        "<|assistant|>", "<|user|>", "<|system|>",
        "<|end|>", "<|pad|>", "<s>", "</s>",
        "[INST]", "[/INST]", "<<SYS>>", "<</SYS>>",
    ]

    # Regex for <think>...</think> blocks (DeepSeek, Qwen thinking tokens)
    THINK_PATTERN = re.compile(r'<think>.*?</think>', re.DOTALL)
    # Regex for leftover role markers from chat template leaks
    ROLE_LEAK_PATTERN = re.compile(
        r'(^|\n)(user|assistant|system)\s*\n',
        re.IGNORECASE | re.MULTILINE
    )
    # Regex for repeated conversation fragments (model continues chat)
    CONV_REPEAT_PATTERN = re.compile(
        r'(\n|^)(Human|User|Assistant|Человек|Пользователь|Ассистент)\s*[:：]\s*',
        re.IGNORECASE | re.MULTILINE
    )

    def clean(self, text):
        """Apply all cleaning passes to response text."""
        if not text or len(text) < 5:
            return text

        result = text

        # Pass 0-pre: Detect and cut off repetition loops (e.g. up/up/up/up...)
        result = self._cut_repetition_loops(result)

        # Pass 0a: Remove <think>...</think> blocks (DeepSeek/Qwen reasoning)
        result = self.THINK_PATTERN.sub('', result)

        # Pass 0b: Strip toxic LLM control tokens
        for token in self.TOXIC_TOKENS:
            result = result.replace(token, '')

        # Pass 0c: Cut off response at conversation repeat
        # If model starts generating "user: ..." it's hallucinating a conversation
        match = self.CONV_REPEAT_PATTERN.search(result)
        if match and match.start() > 50:  # Only if there's real content before it
            result = result[:match.start()]

        # Pass 0d: Remove role leak markers
        result = self.ROLE_LEAK_PATTERN.sub('\n', result)

        # Pass 0e: Collapse excessive newlines from removals
        result = re.sub(r'\n{4,}', '\n\n\n', result)

        if len(result.strip()) < 5:
            return result.strip()

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

    @staticmethod
    def _cut_repetition_loops(text):
        """Detect and truncate repetition loops like 'up/up/up/up...' or garbage."""
        if len(text) < 200:
            return text

        # Method 1: Find any substring of 2-30 chars that repeats 5+ times consecutively
        loop_pat = re.compile(r'(.{2,30?}){4,}', re.DOTALL)
        match = loop_pat.search(text)
        if match:
            cut_pos = match.start()
            if cut_pos > 50:
                return text[:cut_pos].rstrip() + '\n\n[... повторяющийся вывод обрезан ...]'
            else:
                return '[Ответ содержал только повторяющиеся данные и был обрезан]'

        # Method 2: Check if response is >30% single trigram = garbage
        if len(text) > 500:
            from collections import Counter
            trigrams = [text[i:i+3] for i in range(0, min(len(text), 2000) - 2)]
            if trigrams:
                most_common, count = Counter(trigrams).most_common(1)[0]
                ratio = count / len(trigrams)
                if ratio > 0.3:
                    first_occ = text.find(most_common * 3)
                    if first_occ > 50:
                        return text[:first_occ].rstrip() + '\n\n[... повторяющийся вывод обрезан ...]'
                    return '[Ответ содержал только повторяющиеся данные и был обрезан]'

        # Method 3: Detect repeated lines (same line appears 4+ times)
        lines = text.split('\n')
        if len(lines) > 10:
            from collections import Counter
            line_counts = Counter(line.strip() for line in lines if line.strip())
            for line_text, count in line_counts.most_common(3):
                if count >= 4 and len(line_text) > 3:
                    # Find first occurrence and keep text up to 2nd occurrence
                    first_idx = next(i for i, l in enumerate(lines) if l.strip() == line_text)
                    second_idx = next(i for i, l in enumerate(lines) if l.strip() == line_text and i > first_idx)
                    if second_idx > 3:
                        return '\n'.join(lines[:second_idx]).rstrip() + '\n\n[... повторяющийся вывод обрезан ...]'

        return text


# ══════════════════════════════════════════════════════════════════════
# OUTPUT FORMATTER — Claude Code style response rendering
# Highlights IPs, draws tables, formats sections, colorizes output
# ══════════════════════════════════════════════════════════════════════

class OutputFormatter:
    """Format AI responses in Claude Code style with colors, tables, sections."""

    # Colors for different elements
    IP_CLR      = C.rgb(100, 200, 255)   # Bright cyan for IPs
    HEADER_CLR  = C.rgb(230, 100, 100)   # Red/accent for section headers
    TABLE_CLR   = C.rgb(80, 80, 90)      # Dim for table borders
    CODE_CLR    = C.rgb(180, 220, 140)   # Green for code/commands
    KEY_CLR     = C.rgb(255, 180, 80)    # Orange for key names
    VAL_CLR     = C.rgb(200, 200, 210)   # Light for values
    OK_CLR      = C.rgb(120, 200, 120)   # Green for OK/success
    ERR_CLR     = C.rgb(255, 80, 80)     # Red for errors
    WARN_C      = C.rgb(255, 200, 60)    # Yellow for warnings
    DIM_C       = C.rgb(100, 100, 110)   # Dim for less important
    BOLD        = C.BOLD
    RST         = C.RESET

    # Regex patterns
    IP_RE       = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?:/(\d{1,2}))?\b')
    MAC_RE      = re.compile(r'\b([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b')
    SECTION_RE  = re.compile(r'^(={3,}|\u2550{3,})\s*(.+?)\s*(={3,}|\u2550{3,})\s*$', re.MULTILINE)
    HEADER_RE   = re.compile(r'^(#{1,3})\s+(.+)$', re.MULTILINE)
    BOLD_RE     = re.compile(r'\*\*(.+?)\*\*')
    CODE_BLK_RE = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
    INLINE_CODE = re.compile(r'`([^`]+)`')
    TABLE_RE    = re.compile(r'^\|(.+)\|\s*$', re.MULTILINE)
    BULLET_RE   = re.compile(r'^(\s*)([-*•])\s+', re.MULTILINE)
    STATUS_OK   = re.compile(r'\b(OK|UP|active|running|работает|активен|успешно)\b', re.IGNORECASE)
    STATUS_ERR  = re.compile(r'\b(ERROR|FAIL|DOWN|CRITICAL|offline|ошибка|недоступен|упал)\b', re.IGNORECASE)
    STATUS_WARN = re.compile(r'\b(WARNING|WARN|degraded|предупреждение|внимание)\b', re.IGNORECASE)

    def format(self, text):
        """Format response text with colors and structure."""
        if not text or len(text) < 3:
            return text

        result = text

        # Step 1: Process code blocks FIRST (protect from further formatting)
        code_blocks = {}
        counter = [0]
        def save_code(m):
            key = f"\x00CODE{counter[0]}\x00"
            counter[0] += 1
            lang = m.group(1) or ""
            code = m.group(2)
            # Format code block with border
            lines = code.rstrip().split('\n')
            formatted = []
            hline = '\u2500' * max(0, 40 - len(lang))
            formatted.append(f"{self.TABLE_CLR}\u250c\u2500 {lang} \u2500{hline}{self.RST}")
            for line in lines:
                # Highlight $ commands inside code blocks
                if line.strip().startswith('$ '):
                    formatted.append(f"{self.TABLE_CLR}│{self.RST} {self.CODE_CLR}{line}{self.RST}")
                else:
                    formatted.append(f"{self.TABLE_CLR}│{self.RST} {line}")
            bline = '\u2500' * 44
            formatted.append(f"{self.TABLE_CLR}\u2514{bline}{self.RST}")
            code_blocks[key] = '\n'.join(formatted)
            return key
        result = self.CODE_BLK_RE.sub(save_code, result)

        # Step 2: Format section headers (═══ Title ═══)
        def fmt_section(m):
            title = m.group(2).strip()
            w = get_terminal_width() - 4
            pad = max(0, w - len(title) - 6)
            eline = '\u2550' * pad
            return f"\n{self.HEADER_CLR}{self.BOLD}\u2550\u2550\u2550 {title} {eline}{self.RST}\n"
        result = self.SECTION_RE.sub(fmt_section, result)

        # Step 3: Format markdown headers (# Title)
        def fmt_header(m):
            level = len(m.group(1))
            title = m.group(2).strip()
            if level == 1:
                return f"{self.HEADER_CLR}{self.BOLD}{title}{self.RST}"
            elif level == 2:
                return f"{self.KEY_CLR}{self.BOLD}{title}{self.RST}"
            else:
                return f"{self.KEY_CLR}{title}{self.RST}"
        result = self.HEADER_RE.sub(fmt_header, result)

        # Step 4: Format markdown tables
        lines = result.split('\n')
        formatted_lines = []
        in_table = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('|') and stripped.endswith('|'):
                if not in_table:
                    in_table = True
                # Check if separator row
                if re.match(r'^\|[\s:|-]+\|$', stripped):
                    cells = [c.strip() for c in stripped.strip('|').split('|')]
                    sep = f"{self.TABLE_CLR}├" + '┼'.join('─' * (len(c) + 2) for c in cells) + f"┤{self.RST}"
                    formatted_lines.append(sep)
                else:
                    cells = [c.strip() for c in stripped.strip('|').split('|')]
                    row_parts = []
                    for cell in cells:
                        # Colorize cell content
                        cell = self._colorize_inline(cell)
                        row_parts.append(f" {cell} ")
                    formatted_lines.append(f"{self.TABLE_CLR}│{self.RST}" + f"{self.TABLE_CLR}│{self.RST}".join(row_parts) + f"{self.TABLE_CLR}│{self.RST}")
            else:
                if in_table:
                    in_table = False
                formatted_lines.append(line)
        result = '\n'.join(formatted_lines)

        # Step 5: Colorize IPs
        def fmt_ip(m):
            ip = m.group(1)
            cidr = m.group(2)
            if cidr:
                return f"{self.IP_CLR}{ip}/{cidr}{self.RST}"
            return f"{self.IP_CLR}{ip}{self.RST}"
        result = self.IP_RE.sub(fmt_ip, result)

        # Step 6: Colorize MAC addresses
        def fmt_mac(m):
            return f"{self.DIM_C}{m.group(1)}{self.RST}"
        result = self.MAC_RE.sub(fmt_mac, result)

        # Step 7: Bold text
        def fmt_bold(m):
            return f"{self.BOLD}{m.group(1)}{self.RST}"
        result = self.BOLD_RE.sub(fmt_bold, result)

        # Step 8: Inline code
        def fmt_inline(m):
            return f"{self.CODE_CLR}{m.group(1)}{self.RST}"
        result = self.INLINE_CODE.sub(fmt_inline, result)

        # Step 9: Bullet points
        def fmt_bullet(m):
            indent = m.group(1)
            return f"{indent}{self.KEY_CLR}•{self.RST} "
        result = self.BULLET_RE.sub(fmt_bullet, result)

        # Step 10: Status words
        result = self.STATUS_OK.sub(lambda m: f"{self.OK_CLR}{m.group()}{self.RST}", result)
        result = self.STATUS_ERR.sub(lambda m: f"{self.ERR_CLR}{m.group()}{self.RST}", result)
        result = self.STATUS_WARN.sub(lambda m: f"{self.WARN_C}{m.group()}{self.RST}", result)

        # Step 11: Restore code blocks
        for key, block in code_blocks.items():
            result = result.replace(key, block)

        return result

    def _colorize_inline(self, text):
        """Colorize inline content (IPs, status words) within table cells."""
        text = self.IP_RE.sub(lambda m: f"{self.IP_CLR}{m.group()}{self.RST}", text)
        text = self.STATUS_OK.sub(lambda m: f"{self.OK_CLR}{m.group()}{self.RST}", text)
        text = self.STATUS_ERR.sub(lambda m: f"{self.ERR_CLR}{m.group()}{self.RST}", text)
        text = self.STATUS_WARN.sub(lambda m: f"{self.WARN_C}{m.group()}{self.RST}", text)
        return text


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
    """Get terminal width using multiple fallback methods."""
    import struct

    # Method 1: fcntl.ioctl on /dev/tty (most reliable on macOS)
    try:
        import fcntl, termios
        fd = os.open('/dev/tty', os.O_RDONLY)
        try:
            result = fcntl.ioctl(fd, termios.TIOCGWINSZ, b'\x00' * 8)
            rows, cols = struct.unpack('HHHH', result)[:2]
            if cols > 40:
                return cols
        finally:
            os.close(fd)
    except Exception:
        pass

    # Method 2: fcntl.ioctl on stdout/stderr/stdin
    try:
        import fcntl, termios
        for fd_num in (1, 2, 0):  # stdout, stderr, stdin
            try:
                result = fcntl.ioctl(fd_num, termios.TIOCGWINSZ, b'\x00' * 8)
                rows, cols = struct.unpack('HHHH', result)[:2]
                if cols > 40:
                    return cols
            except Exception:
                continue
    except Exception:
        pass

    # Method 3: os.get_terminal_size
    try:
        cols = os.get_terminal_size().columns
        if cols > 40:
            return cols
    except (OSError, ValueError):
        pass

    # Method 4: COLUMNS env var
    try:
        cols = int(os.environ.get('COLUMNS', 0))
        if cols > 40:
            return cols
    except (ValueError, TypeError):
        pass

    # Method 5: stty size via /dev/tty
    try:
        with open('/dev/tty') as tty:
            r = subprocess.run(['stty', 'size'], capture_output=True, text=True,
                               timeout=2, stdin=tty)
            if r.returncode == 0 and r.stdout.strip():
                parts = r.stdout.strip().split()
                if len(parts) >= 2:
                    cols = int(parts[1])
                    if cols > 40:
                        return cols
    except Exception:
        pass

    # Method 6: tput cols
    try:
        r = subprocess.run(['tput', 'cols'], capture_output=True, text=True, timeout=2,
                           env={**os.environ, 'TERM': os.environ.get('TERM', 'xterm-256color')})
        if r.returncode == 0 and r.stdout.strip():
            cols = int(r.stdout.strip())
            if cols > 40:
                return cols
    except Exception:
        pass

    # Method 7: shutil fallback
    try:
        import shutil
        cols = shutil.get_terminal_size().columns
        if cols > 40:
            return cols
    except Exception:
        pass

    return 120  # Reasonable default for modern terminals

def clear_screen():
    print("\033[2J\033[H", end="")

def draw_hline(char="─", color=BORDER_CLR):
    print(f"{color}{char * get_terminal_width()}{C.RESET}")

def draw_dashed():
    print(f"{BORDER_CLR}{'┄' * get_terminal_width()}{C.RESET}")

# All lines exactly 14 chars for uniform block centering
CLAW_MINI = [
    " .---.  .---. ",   # ears
    " |   '--'   | ",   # top
    " | [ o  o ] | ",   # eyes
    " |          | ",   # body
    " '----------' ",   # jaw
    "   '------'   ",   # chin
]


# ══════════════════════════════════════════════════════════════════════
# ANIMATED SPINNER — Claude Code style visual feedback
# Braille dots spinner + elapsed time + substatus
# ══════════════════════════════════════════════════════════════════════

class Spinner:
    """Claude Code style animated spinner with Braille dots."""

    # Claude Code uses these exact Braille frames
    DOTS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message="Thinking", color=ACCENT2, style="dots"):
        self.message = message
        self.color = color
        self.frames = self.DOTS
        self._running = False
        self._thread = None
        self._start_time = 0
        self._substatus = ""
        self._lock = threading.Lock()

    def _animate(self):
        """Animation loop — Claude Code style: ⠋ Message... 5s  substatus"""
        idx = 0
        while self._running:
            elapsed = time.time() - self._start_time
            frame = self.frames[idx % len(self.frames)]
            with self._lock:
                sub = self._substatus

            # Claude Code style: spinner char + message + elapsed
            status = f"\r  {self.color}{frame}{C.RESET} {C.BOLD}{self.message}{C.RESET}"
            if elapsed >= 1:
                status += f" {DIM_COLOR}{elapsed:.0f}s{C.RESET}"
            if sub:
                status += f"  {DIM_COLOR}{sub}{C.RESET}"

            # Pad to clear previous line
            status += " " * 30

            sys.stdout.write(status)
            sys.stdout.flush()
            idx += 1
            time.sleep(0.08)  # Slightly faster for smoother animation

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
        """Stop the spinner and show final status like Claude Code."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        elapsed = time.time() - self._start_time
        # Clear spinner line
        sys.stdout.write(f"\r{' ' * (get_terminal_width())}\r")
        sys.stdout.flush()
        if final_message:
            print(f"  {SYSTEM_CLR}✓ {final_message}{C.RESET} {DIM_COLOR}({elapsed:.1f}s){C.RESET}")

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


class CommandRenderer:
    """Claude Code style command execution renderer.

    Shows commands as they execute:
      ● Bash(nmap -sn 172.27.4.0/24)
        ✓ Done (2.3s)
      ● Bash(ping -c 1 172.27.4.1)
        ✓ Done (0.1s)
    """

    # Sensitive patterns to mask in command display
    _MASK_PATTERNS = [
        re.compile(r'(Authorization:\s*Bearer\s+)([A-Za-z0-9_.\-]{6})[A-Za-z0-9_.\-]+', re.IGNORECASE),
        re.compile(r'(-H\s+["\']Authorization:\s*Bearer\s+)([A-Za-z0-9_.\-]{6})[A-Za-z0-9_.\-]+', re.IGNORECASE),
        re.compile(r'(token[=:\s]+)([A-Za-z0-9_.\-]{4})[A-Za-z0-9_.\-]{8,}', re.IGNORECASE),
        re.compile(r'(password[=:\s]+)([^\s]{2})[^\s]{4,}', re.IGNORECASE),
        re.compile(r'(api[_-]?key[=:\s]+)([A-Za-z0-9]{4})[A-Za-z0-9]{8,}', re.IGNORECASE),
        re.compile(r'(sshpass\s+-p\s+)([^\s]{2})[^\s]+', re.IGNORECASE),
    ]

    @classmethod
    def _mask_sensitive(cls, text):
        """Mask sensitive data (API keys, tokens, passwords) in display text."""
        result = text
        for pattern in cls._MASK_PATTERNS:
            result = pattern.sub(r'\1\2***', result)
        return result

    @classmethod
    def show_start(cls, cmd, max_len=70):
        """Show command start: ● Bash(cmd...) with sensitive data masked."""
        cmd_display = cmd.split('|')[0].strip()
        if len(cmd_display) > max_len:
            cmd_display = cmd_display[:max_len-3] + '...'
        cmd_display = cls._mask_sensitive(cmd_display)
        print(f"  {TOOL_CLR}●{C.RESET} {C.BOLD}Bash{C.RESET}({DIM_COLOR}{cmd_display}{C.RESET})")

    @staticmethod
    def show_done(elapsed, success=True):
        """Show command result: ✓ Done (0.1s) or ✗ Failed (0.1s)"""
        if success:
            print(f"    {SYSTEM_CLR}✓{C.RESET} {DIM_COLOR}Done ({elapsed:.1f}s){C.RESET}")
        else:
            print(f"    {ERROR_CLR}✗{C.RESET} {DIM_COLOR}Failed ({elapsed:.1f}s){C.RESET}")

    @staticmethod
    def show_timeout(timeout_sec):
        """Show timeout: ✗ Timeout (30s)"""
        print(f"    {ERROR_CLR}✗{C.RESET} {DIM_COLOR}Timeout ({timeout_sec}s){C.RESET}")

    @staticmethod
    def show_output_preview(output, max_lines=3):
        """Show collapsed output preview if output is long."""
        if not output or not output.strip():
            return
        lines = output.strip().split('\n')
        if len(lines) <= max_lines:
            return  # Short output — will be sent to AI, no need to preview
        # Show first few lines + count
        for line in lines[:max_lines]:
            trimmed = line[:100] + ('...' if len(line) > 100 else '')
            print(f"    {DIM_COLOR}│ {trimmed}{C.RESET}")
        remaining = len(lines) - max_lines
        print(f"    {DIM_COLOR}└ ... {remaining} more lines{C.RESET}")


class ProgressTracker:
    """Claude Code style progress for multi-command execution.

    Shows: ⚡ Collecting data [2/5]
    Then each command as ● Bash(cmd) → ✓ Done
    """

    def __init__(self, total, label="Collecting data"):
        self.total = total
        self.current = 0
        self.label = label
        self.cmd_renderer = CommandRenderer()

    def next_command(self, cmd):
        """Start next command — show header + command."""
        self.current += 1
        # Show progress header on first command only
        if self.current == 1:
            print(f"  {TOOL_CLR}⚡{C.RESET} {C.BOLD}{self.label}{C.RESET} {DIM_COLOR}[0/{self.total}]{C.RESET}")
        self.cmd_renderer.show_start(cmd)

    def command_done(self, elapsed, success=True, output=""):
        """Mark command as done."""
        self.cmd_renderer.show_done(elapsed, success)
        # Show output preview for long outputs
        if output and len(output.strip().split('\n')) > 5:
            self.cmd_renderer.show_output_preview(output)

    def command_timeout(self, timeout_sec):
        """Mark command as timed out."""
        self.cmd_renderer.show_timeout(timeout_sec)

    def finish(self, collected, total):
        """Show final collection summary."""
        print(f"  {SYSTEM_CLR}✓{C.RESET} {DIM_COLOR}Collected {collected}/{total} data sources{C.RESET}")


class TypewriterEffect:
    """Smooth text appearance effect for AI responses.

    Outputs text line-by-line with a small delay for visual polish.
    Code blocks and tables are printed instantly.
    """

    # Delay between lines (seconds)
    LINE_DELAY = 0.015
    # Delay between chars for short important lines
    CHAR_DELAY = 0.008
    # Max chars for char-by-char mode
    CHAR_MODE_MAX = 80

    @classmethod
    def print(cls, text, instant_threshold=200):
        """Print text with typewriter effect.

        Args:
            text: Formatted text to display
            instant_threshold: If text > this many lines, print instantly
        """
        if not text:
            return

        lines = text.split('\n')

        # Very long output — print instantly
        if len(lines) > instant_threshold:
            print(text)
            return

        in_code_block = False
        for i, line in enumerate(lines):
            # Detect code block boundaries (already formatted with box chars)
            if '\u250c' in line or '```' in line:
                in_code_block = True
            if '\u2514' in line or (in_code_block and '```' in line and i > 0):
                # Print code block line and exit code mode
                print(line)
                in_code_block = False
                continue

            if in_code_block:
                # Code blocks print instantly
                print(line)
                continue

            # Table rows (contain │) — print with minimal delay
            if '│' in line or '┌' in line or '└' in line or '├' in line:
                print(line)
                time.sleep(cls.LINE_DELAY * 0.3)
                continue

            # Empty lines — instant
            if not line.strip():
                print(line)
                continue

            # Section headers — slight pause before for emphasis
            if '═══' in line or '━━━' in line:
                time.sleep(cls.LINE_DELAY * 2)
                print(line)
                time.sleep(cls.LINE_DELAY)
                continue

            # Regular lines — line-by-line with delay
            print(line)
            time.sleep(cls.LINE_DELAY)


# Legacy compatibility alias
class ProgressBar(ProgressTracker):
    """Backward-compatible wrapper around ProgressTracker."""

    def __init__(self, total, label="Progress", color=TOOL_CLR):
        super().__init__(total, label)

    def update(self, step_name=""):
        """Legacy update method — maps to next_command."""
        self.next_command(step_name or "...")

    def finish(self, message=""):
        """Legacy finish method."""
        sys.stdout.write(f"\r{' ' * get_terminal_width()}\r")
        sys.stdout.flush()
        if message:
            print(f"  {SYSTEM_CLR}✓ {message}{C.RESET}")


# ══════════════════════════════════════════════════════════════════════
# TOOL REGISTRY — Structured Tool Calling (inspired by nearai/ironclaw)
# Replaces <cmd> tag parsing with proper tool definitions
# ══════════════════════════════════════════════════════════════════════

@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool: str
    success: bool
    output: str
    elapsed: float = 0.0


class ToolRegistry:
    """Registry of available tools with JSON-schema definitions.

    Inspired by IronClaw's skill catalog. Each tool has:
    - name: unique identifier
    - description: what the tool does
    - parameters: JSON schema for input
    - execute: callable that runs the tool
    """

    def __init__(self):
        self.tools = {}
        self._register_builtins()

    def register(self, name, description, parameters, execute_fn):
        """Register a tool."""
        self.tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "execute": execute_fn,
        }

    def _register_builtins(self):
        """Register built-in tools (bash, file ops)."""

        # ── bash: Execute shell commands ──
        self.register(
            name="bash",
            description="Execute a shell command on the local machine. Use for system administration, monitoring, diagnostics.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)", "default": 30},
                },
                "required": ["command"],
            },
            execute_fn=self._exec_bash,
        )

        # ── read_file: Read file contents ──
        self.register(
            name="read_file",
            description="Read the contents of a file. Use to inspect configs, logs, scripts.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                    "offset": {"type": "integer", "description": "Start line (0-indexed, default 0)", "default": 0},
                    "limit": {"type": "integer", "description": "Max lines to read (default 200)", "default": 200},
                },
                "required": ["path"],
            },
            execute_fn=self._exec_read_file,
        )

        # ── write_file: Create or overwrite a file ──
        self.register(
            name="write_file",
            description="Create a new file or overwrite an existing file with the given content.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Full file content"},
                },
                "required": ["path", "content"],
            },
            execute_fn=self._exec_write_file,
        )

        # ── apply_patch: Edit specific parts of a file ──
        self.register(
            name="apply_patch",
            description="Apply a targeted edit to a file. Finds exact text and replaces it. Preferred over write_file for modifications.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to edit"},
                    "find": {"type": "string", "description": "Exact text to find in the file"},
                    "replace": {"type": "string", "description": "Replacement text"},
                },
                "required": ["path", "find", "replace"],
            },
            execute_fn=self._exec_apply_patch,
        )

        # ── glob: Find files by pattern ──
        self.register(
            name="glob",
            description="Find files matching a glob pattern. Returns list of matching file paths.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. /etc/*.conf, **/*.py)"},
                    "path": {"type": "string", "description": "Base directory (default: current dir)", "default": "."},
                },
                "required": ["pattern"],
            },
            execute_fn=self._exec_glob,
        )

        # ── grep: Search file contents ──
        self.register(
            name="grep",
            description="Search for a regex pattern in files. Returns matching lines with context.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "File or directory to search in"},
                    "include": {"type": "string", "description": "File glob to include (e.g. *.py)", "default": ""},
                },
                "required": ["pattern", "path"],
            },
            execute_fn=self._exec_grep,
        )

        # ── list_dir: List directory contents ──
        self.register(
            name="list_dir",
            description="List contents of a directory with file sizes and types.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                },
                "required": ["path"],
            },
            execute_fn=self._exec_list_dir,
        )

    # ── Tool Implementations ──

    def _exec_bash(self, command, timeout=30, **_):
        """Execute a shell command."""
        renderer = CommandRenderer()
        renderer.show_start(command)
        try:
            t0 = time.time()
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            dt = time.time() - t0
            output = proc.stdout.strip()
            if proc.stderr.strip():
                output += ("\n" + proc.stderr.strip()) if output else proc.stderr.strip()
            success = proc.returncode == 0
            renderer.show_done(dt, success=success)
            if output and len(output.split('\n')) > 5:
                renderer.show_output_preview(output)
            return ToolResult("bash", success, output or "(no output)", dt)
        except subprocess.TimeoutExpired:
            renderer.show_timeout(timeout)
            return ToolResult("bash", False, f"[TIMEOUT after {timeout}s]", timeout)
        except Exception as e:
            renderer.show_done(0, success=False)
            return ToolResult("bash", False, f"[ERROR: {e}]", 0)

    def _exec_read_file(self, path, offset=0, limit=200, **_):
        """Read file contents."""
        renderer = CommandRenderer()
        renderer.show_start(f"read_file {path}")
        t0 = time.time()
        try:
            path = os.path.expanduser(path)
            if not os.path.exists(path):
                renderer.show_done(time.time() - t0, success=False)
                return ToolResult("read_file", False, f"File not found: {path}", time.time() - t0)
            if os.path.getsize(path) > 2 * 1024 * 1024:  # 2MB limit
                renderer.show_done(time.time() - t0, success=False)
                return ToolResult("read_file", False, f"File too large: {os.path.getsize(path)} bytes (max 2MB)", time.time() - t0)
            with open(path, 'r', errors='replace') as f:
                lines = f.readlines()
            total = len(lines)
            selected = lines[offset:offset + limit]
            content = ''.join(selected)
            dt = time.time() - t0
            renderer.show_done(dt, success=True)
            header = f"[{path}] lines {offset+1}-{min(offset+limit, total)} of {total}\n"
            return ToolResult("read_file", True, header + content, dt)
        except Exception as e:
            dt = time.time() - t0
            renderer.show_done(dt, success=False)
            return ToolResult("read_file", False, f"[ERROR: {e}]", dt)

    def _exec_write_file(self, path, content, **_):
        """Write content to a file."""
        renderer = CommandRenderer()
        renderer.show_start(f"write_file {path}")
        t0 = time.time()
        try:
            path = os.path.expanduser(path)
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
            dt = time.time() - t0
            renderer.show_done(dt, success=True)
            lines = content.count('\n') + 1
            return ToolResult("write_file", True, f"Wrote {lines} lines to {path}", dt)
        except Exception as e:
            dt = time.time() - t0
            renderer.show_done(dt, success=False)
            return ToolResult("write_file", False, f"[ERROR: {e}]", dt)

    def _exec_apply_patch(self, path, find, replace, **_):
        """Apply a targeted edit to a file."""
        renderer = CommandRenderer()
        renderer.show_start(f"apply_patch {path}")
        t0 = time.time()
        try:
            path = os.path.expanduser(path)
            if not os.path.exists(path):
                renderer.show_done(time.time() - t0, success=False)
                return ToolResult("apply_patch", False, f"File not found: {path}", time.time() - t0)
            with open(path, 'r') as f:
                original = f.read()
            if find not in original:
                renderer.show_done(time.time() - t0, success=False)
                return ToolResult("apply_patch", False, f"Text to find not found in {path}", time.time() - t0)
            updated = original.replace(find, replace, 1)
            with open(path, 'w') as f:
                f.write(updated)
            dt = time.time() - t0
            renderer.show_done(dt, success=True)
            return ToolResult("apply_patch", True, f"Patched {path} successfully", dt)
        except Exception as e:
            dt = time.time() - t0
            renderer.show_done(dt, success=False)
            return ToolResult("apply_patch", False, f"[ERROR: {e}]", dt)

    def _exec_glob(self, pattern, path=".", **_):
        """Find files matching a glob pattern."""
        renderer = CommandRenderer()
        renderer.show_start(f"glob {pattern}")
        t0 = time.time()
        try:
            import glob as glob_mod
            base = os.path.expanduser(path)
            full_pattern = os.path.join(base, pattern) if not os.path.isabs(pattern) else pattern
            matches = sorted(glob_mod.glob(full_pattern, recursive=True))[:100]
            dt = time.time() - t0
            renderer.show_done(dt, success=True)
            if matches:
                return ToolResult("glob", True, f"Found {len(matches)} files:\n" + '\n'.join(matches), dt)
            return ToolResult("glob", True, "No files matched", dt)
        except Exception as e:
            dt = time.time() - t0
            renderer.show_done(dt, success=False)
            return ToolResult("glob", False, f"[ERROR: {e}]", dt)

    def _exec_grep(self, pattern, path, include="", **_):
        """Search for a regex pattern in files."""
        renderer = CommandRenderer()
        renderer.show_start(f"grep '{pattern}' {path}")
        t0 = time.time()
        try:
            cmd = f"grep -rn --color=never"
            if include:
                cmd += f" --include='{include}'"
            cmd += f" '{pattern}' {path} 2>/dev/null | head -50"
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            dt = time.time() - t0
            output = proc.stdout.strip()
            renderer.show_done(dt, success=bool(output))
            if output and len(output.split('\n')) > 5:
                renderer.show_output_preview(output)
            return ToolResult("grep", True, output or "No matches found", dt)
        except Exception as e:
            dt = time.time() - t0
            renderer.show_done(dt, success=False)
            return ToolResult("grep", False, f"[ERROR: {e}]", dt)

    def _exec_list_dir(self, path, **_):
        """List directory contents."""
        renderer = CommandRenderer()
        renderer.show_start(f"list_dir {path}")
        t0 = time.time()
        try:
            path = os.path.expanduser(path)
            if not os.path.isdir(path):
                renderer.show_done(time.time() - t0, success=False)
                return ToolResult("list_dir", False, f"Not a directory: {path}", time.time() - t0)
            entries = []
            for entry in sorted(os.listdir(path)):
                full = os.path.join(path, entry)
                if os.path.isdir(full):
                    entries.append(f"  {entry}/")
                else:
                    try:
                        size = os.path.getsize(full)
                        if size > 1024 * 1024:
                            size_str = f"{size / 1024 / 1024:.1f}M"
                        elif size > 1024:
                            size_str = f"{size / 1024:.1f}K"
                        else:
                            size_str = f"{size}B"
                        entries.append(f"  {entry} ({size_str})")
                    except OSError:
                        entries.append(f"  {entry}")
            dt = time.time() - t0
            renderer.show_done(dt, success=True)
            return ToolResult("list_dir", True, f"{path}/\n" + '\n'.join(entries[:100]), dt)
        except Exception as e:
            dt = time.time() - t0
            renderer.show_done(dt, success=False)
            return ToolResult("list_dir", False, f"[ERROR: {e}]", dt)

    def get_tool_definitions(self):
        """Get tool definitions in OpenAI function-calling format for the system prompt."""
        defs = []
        for name, tool in self.tools.items():
            defs.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                }
            })
        return defs

    def get_tools_prompt(self):
        """Get a text description of available tools for the system prompt.
        Used when the model doesn't support native function calling."""
        lines = ["\nДОСТУПНЫЕ ИНСТРУМЕНТЫ (tool calling):"]
        lines.append("Вместо <cmd> тегов используй структурированные вызовы инструментов:")
        lines.append("")
        for name, tool in self.tools.items():
            params = tool["parameters"].get("properties", {})
            required = tool["parameters"].get("required", [])
            param_strs = []
            for pname, pdef in params.items():
                req = "*" if pname in required else ""
                param_strs.append(f"{pname}{req}: {pdef.get('description', '')}")
            lines.append(f"  • {name}: {tool['description']}")
            lines.append(f"    Параметры: {', '.join(param_strs)}")
            lines.append(f'    Формат: <tool name="{name}">{{"param": "value"}}</tool>')
            lines.append("")
        lines.append("ПРИМЕРЫ:")
        lines.append('<tool name="bash">{"command": "df -h"}</tool>')
        lines.append('<tool name="read_file">{"path": "/etc/nginx/nginx.conf"}</tool>')
        lines.append('<tool name="write_file">{"path": "/tmp/test.sh", "content": "#!/bin/bash\\necho hello"}</tool>')
        lines.append('<tool name="apply_patch">{"path": "/etc/hosts", "find": "old-host", "replace": "new-host"}</tool>')
        lines.append('<tool name="grep">{"pattern": "error|fail", "path": "/var/log/", "include": "*.log"}</tool>')
        lines.append('<tool name="list_dir">{"path": "/etc/nginx/"}</tool>')
        lines.append("")
        lines.append("ВАЖНО: Ты можешь вызывать несколько инструментов в одном ответе.")
        lines.append("После каждого вызова ты получишь результат и сможешь продолжить анализ или вызвать следующий инструмент.")
        lines.append("Также поддерживается старый формат: <cmd>команда</cmd> (автоматически конвертируется в bash tool).")
        return '\n'.join(lines)

    def execute_tool(self, name, params):
        """Execute a tool by name with given parameters."""
        tool = self.tools.get(name)
        if not tool:
            return ToolResult(name, False, f"Unknown tool: {name}", 0)
        try:
            return tool["execute"](**params)
        except TypeError as e:
            return ToolResult(name, False, f"Invalid parameters for {name}: {e}", 0)
        except Exception as e:
            return ToolResult(name, False, f"Tool {name} error: {e}", 0)

    def parse_tool_calls(self, response_text):
        """Parse tool calls from AI response text.

        Supports two formats:
        1. New: <tool name="bash">{"command": "ls"}</tool>
        2. Legacy: <cmd>ls</cmd> (auto-converted to bash tool)

        Returns list of (tool_name, params_dict) tuples.
        """
        calls = []

        # Parse new format: <tool name="...">...</tool>
        tool_pattern = re.compile(r'<tool\s+name="(\w+)">(.*?)</tool>', re.DOTALL)
        for match in tool_pattern.finditer(response_text):
            tool_name = match.group(1)
            params_raw = match.group(2).strip()
            try:
                params = json.loads(params_raw)
            except json.JSONDecodeError:
                # If not valid JSON, treat as command for bash
                params = {"command": params_raw}
            calls.append((tool_name, params))

        # Parse legacy format: <cmd>...</cmd> (backward compatible)
        cmd_pattern = re.compile(r'<cmd>(.*?)</cmd>', re.DOTALL)
        for match in cmd_pattern.finditer(response_text):
            cmd = match.group(1).strip()
            if cmd:
                # Check if this command was already captured as a tool call
                already = any(p.get("command") == cmd for _, p in calls if _ == "bash")
                if not already:
                    calls.append(("bash", {"command": cmd}))

        return calls


# ══════════════════════════════════════════════════════════════════════
# STREAM RENDERER — Real-time token streaming display
# Inspired by Claude Code and IronClaw's event_tx broadcast
# ══════════════════════════════════════════════════════════════════════

class StreamRenderer:
    """Renders streaming LLM output token-by-token with live formatting.

    Handles:
    - Real-time token display as they arrive
    - Code block detection and formatting
    - Tool call detection mid-stream
    - Graceful interruption (Ctrl+C)
    """

    # Tags to suppress from streaming output (never shown to user)
    _SUPPRESS_TAGS = [
        ("<think>", "</think>"),
        ("<reflection>", "</reflection>"),
        ("<reasoning>", "</reasoning>"),
    ]

    # Sensitive patterns to mask in output (API keys, tokens, passwords)
    _SENSITIVE_PATTERNS = [
        re.compile(r'(Authorization:\s*Bearer\s+)([A-Za-z0-9_.\-]{8})[A-Za-z0-9_.\-]+', re.IGNORECASE),
        re.compile(r'(token[=:\s]+)([A-Za-z0-9_.\-]{4})[A-Za-z0-9_.\-]{8,}', re.IGNORECASE),
        re.compile(r'(password[=:\s]+)([^\s]{2})[^\s]{4,}', re.IGNORECASE),
        re.compile(r'(api[_-]?key[=:\s]+)([A-Za-z0-9]{4})[A-Za-z0-9]{8,}', re.IGNORECASE),
    ]

    def __init__(self, formatter=None):
        self.formatter = formatter
        self._buffer = ""
        self._display_buffer = ""  # What was actually shown to user
        self._line_buffer = ""
        self._in_code_block = False
        self._in_tool_call = False
        self._tool_buffer = ""
        self._in_suppress = False  # Inside <think> or similar suppressed tag
        self._suppress_buffer = ""
        self._suppress_end_tag = ""
        self._interrupted = False
        self._token_count = 0

    def feed(self, token):
        """Feed a single token from the stream.

        v5.0.1: Filters out <think> blocks and sensitive data in real-time.

        Returns:
            None normally, or a string if a complete tool call was detected.
        """
        if self._interrupted:
            return None

        self._buffer += token
        self._token_count += 1

        # ── Suppressed tag handling (<think>, <reflection>, etc.) ──
        if self._in_suppress:
            self._suppress_buffer += token
            if self._suppress_end_tag in self._suppress_buffer:
                # End of suppressed block — discard everything
                # Check if there's content after the closing tag
                end_idx = self._suppress_buffer.find(self._suppress_end_tag)
                after = self._suppress_buffer[end_idx + len(self._suppress_end_tag):]
                self._in_suppress = False
                self._suppress_buffer = ""
                self._suppress_end_tag = ""
                # Feed any content after the closing tag
                if after:
                    return self.feed(after)
            return None

        self._line_buffer += token

        # Check for suppressed tag start
        for open_tag, close_tag in self._SUPPRESS_TAGS:
            if open_tag in self._line_buffer:
                self._in_suppress = True
                self._suppress_end_tag = close_tag
                # Print everything before the tag
                idx = self._line_buffer.find(open_tag)
                before = self._line_buffer[:idx]
                if before:
                    self._write_safe(before)
                self._suppress_buffer = self._line_buffer[idx:]
                self._line_buffer = ""
                return None

        # Check for tool call start
        if '<tool ' in self._line_buffer or '<cmd>' in self._line_buffer:
            self._in_tool_call = True
            for tag in ['<tool ', '<cmd>']:
                idx = self._line_buffer.find(tag)
                if idx >= 0:
                    before = self._line_buffer[:idx]
                    if before:
                        self._write_safe(before)
                    self._tool_buffer = self._line_buffer[idx:]
                    self._line_buffer = ""
                    return None

        # If we're inside a tool call, accumulate silently
        if self._in_tool_call:
            self._tool_buffer += token
            self._line_buffer = ""
            if '</tool>' in self._tool_buffer or '</cmd>' in self._tool_buffer:
                self._in_tool_call = False
                tool_text = self._tool_buffer
                self._tool_buffer = ""
                return tool_text
            return None

        # Regular streaming output
        if '```' in self._line_buffer:
            self._in_code_block = not self._in_code_block

        # Print token immediately (with sensitive data masking)
        self._write_safe(token)

        # Reset line buffer on newlines
        if '\n' in token:
            self._line_buffer = ""

        return None

    def _write_safe(self, text):
        """Write text to stdout, masking sensitive data like API keys."""
        masked = text
        for pattern in self._SENSITIVE_PATTERNS:
            masked = pattern.sub(r'\1\2***', masked)
        sys.stdout.write(masked)
        sys.stdout.flush()
        self._display_buffer += masked

    def interrupt(self):
        """Signal interruption (Ctrl+C)."""
        self._interrupted = True

    def get_full_response(self):
        """Get the complete accumulated response."""
        return self._buffer

    def get_token_count(self):
        """Get number of tokens received."""
        return self._token_count

    def finish(self):
        """Finish streaming — ensure newline at end."""
        if self._line_buffer and not self._line_buffer.endswith('\n'):
            sys.stdout.write('\n')
            sys.stdout.flush()


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

    # Model-specific stop tokens to prevent garbage generation
    GEMMA_EXTRA_STOPS = ["\n\n\n", "```\n\n", "<end_of_turn>", "<start_of_turn>"]
    BASE_STOPS = [
        "<|endoftext|>", "<|im_start|>", "<|im_end|>",
        "<|end|>", "</s>", "<|assistant|>", "<|user|>",
        "\nUser:", "\nuser:", "\nHuman:", "\nПользователь:",
        "\nAssistant:", "\nassistant:",
    ]

    def _get_stop_tokens(self, model):
        """Get stop tokens for a specific model."""
        stops = list(self.BASE_STOPS)
        model_low = model.lower()
        if "gemma" in model_low:
            stops.extend(self.GEMMA_EXTRA_STOPS)
        if "deepseek" in model_low:
            stops.append("<│end│>")
        return stops

    def generate(self, model, prompt, system="", temperature=0.5, max_tokens=2048, stream=False, retries=2):
        """Generate response from Ollama with retry logic."""
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "stop": self._get_stop_tokens(model),
                "repeat_penalty": 1.15,
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

    def chat(self, model, messages, system="", temperature=0.5, max_tokens=1500, stream=False, retries=2):
        """Chat completion from Ollama with retry logic."""
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        # Limit context to prevent models from seeing too much history
        # and generating conversation continuations
        if len(msgs) > 8:
            system_msgs = [m for m in msgs if m.get('role') == 'system']
            other_msgs = [m for m in msgs if m.get('role') != 'system']
            msgs = system_msgs + other_msgs[-6:]

        payload = {
            "model": model,
            "messages": msgs,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "stop": self._get_stop_tokens(model),
                "repeat_penalty": 1.15,
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

    def chat_stream(self, model, messages, system="", temperature=0.5, max_tokens=1500, on_token=None):
        """Streaming chat completion from Ollama.

        Yields tokens one at a time via on_token callback.
        Falls back to non-streaming if streaming fails.

        Args:
            on_token: callable(token_str) called for each token
        Returns:
            Full accumulated response string
        """
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        if len(msgs) > 8:
            system_msgs = [m for m in msgs if m.get('role') == 'system']
            other_msgs = [m for m in msgs if m.get('role') != 'system']
            msgs = system_msgs + other_msgs[-6:]

        payload = {
            "model": model,
            "messages": msgs,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "stop": self._get_stop_tokens(model),
                "repeat_penalty": 1.15,
            }
        }

        data = json.dumps(payload).encode()
        full_response = ""

        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                # Ollama streams NDJSON — one JSON object per line
                buffer = b""
                while True:
                    chunk = resp.read(1)
                    if not chunk:
                        break
                    buffer += chunk
                    if chunk == b"\n":
                        line = buffer.strip()
                        buffer = b""
                        if not line:
                            continue
                        try:
                            obj = json.loads(line.decode())
                            token = obj.get("message", {}).get("content", "")
                            if token:
                                full_response += token
                                if on_token:
                                    on_token(token)
                            # Check if done
                            if obj.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

            return full_response if full_response else "[ERROR] Empty streaming response"

        except Exception as e:
            # Fallback to non-streaming
            if full_response:
                return full_response  # Return partial response
            return self.chat(model, messages, system, temperature, max_tokens, stream=False)


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
        """Send request to Claude API with retry for 429/529 (overloaded/rate-limited)."""
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

        # Retry logic: up to 3 attempts with exponential backoff for 429/529
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    CLAUDE_API_URL,
                    data=data,
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=45) as resp:
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
                error_body = ""
                try:
                    error_body = e.read().decode()
                except Exception:
                    error_body = str(e)
                last_error = f"Claude API {e.code}: {error_body[:200]}"

                # Retry on 429 (rate limit) and 529 (overloaded)
                if e.code in (429, 529, 503, 500) and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                    time.sleep(wait_time)
                    continue
                else:
                    return f"[ERROR] {last_error}"

            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return f"[ERROR] Claude: {last_error}"

        return f"[ERROR] Claude failed after {max_retries} retries: {last_error}"

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

    def classify(self, query, conversation_context=None):
        """Classify query into an expert category.
        If query is short/ambiguous, uses conversation_context to determine topic.
        """
        query_low = query.lower()

        # For short/ambiguous queries, enrich with conversation context
        effective_query = query_low
        if conversation_context and len(query_low.split()) <= 5:
            # Short query like "нужен анализ", "покажи ещё", "подробнее"
            # — use last conversation messages to determine topic
            ctx_text = " ".join(
                msg.get("content", "")[:200]
                for msg in conversation_context[-4:]
                if msg.get("role") in ("user", "assistant")
            ).lower()
            effective_query = f"{query_low} {ctx_text}"

        scores = {}
        for expert, profile in self.profiles.items():
            score = 0
            for kw in profile.get("keywords", []):
                if kw in effective_query:
                    score += 2
                    if re.search(rf'\b{re.escape(kw)}\b', effective_query):
                        score += 1
                    # Extra bonus if keyword is in the actual query (not just context)
                    if kw in query_low:
                        score += 2
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
    """Collects good responses for self-learning with quality scoring,
    dedup, golden dataset merge, and Modelfile export."""

    GOLDEN_FILE = os.path.join(DATA_DIR, "golden_dataset.jsonl")
    MODELFILE_DIR = os.path.join(DATA_DIR, "modelfiles")
    MIN_QUALITY = 0.6

    def __init__(self, training_file=TRAINING_FILE):
        self.training_file = training_file
        os.makedirs(self.MODELFILE_DIR, exist_ok=True)
        self._seen_hashes = set()
        self._load_seen_hashes()

    def _load_seen_hashes(self):
        try:
            if os.path.exists(self.training_file):
                with open(self.training_file) as f:
                    for line in f:
                        try:
                            e = json.loads(line)
                            self._seen_hashes.add(hash(e.get("query", "")[:100]))
                        except Exception:
                            pass
        except Exception:
            pass

    def _score_quality(self, query, response, model=""):
        score = 0.0
        if "|" in response and "---" in response:
            score += 0.15
        if "```" in response:
            score += 0.10
        if "<tool " in response or "<cmd>" in response:
            score += 0.15
        if re.search(r'^#{1,3} ', response, re.MULTILINE):
            score += 0.10
        if re.search(r'(\u0432\u044b\u0432\u043e\u0434|\u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0438|\u0438\u0442\u043e\u0433|conclusion|summary)', response.lower()):
            score += 0.10
        if 100 <= len(response) <= 2000:
            score += 0.10
        refusal_pats = ["\u043d\u0435 \u043c\u043e\u0433\u0443", "\u043d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430", "cannot", "i don't have"]
        if not any(p in response.lower() for p in refusal_pats):
            score += 0.20
        if "claude" in model.lower():
            score += 0.10
        return round(min(score, 1.0), 2)

    def save(self, query, response, expert, model, quality_score=None):
        try:
            q_hash = hash(query[:100])
            if q_hash in self._seen_hashes:
                return
            if quality_score is None:
                quality_score = self._score_quality(query, response, model)
            if quality_score < self.MIN_QUALITY:
                return
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
            self._seen_hashes.add(q_hash)
        except Exception:
            pass

    def count(self):
        try:
            if os.path.exists(self.training_file):
                with open(self.training_file) as f:
                    return sum(1 for _ in f)
        except Exception:
            pass
        return 0

    def get_entries(self, min_quality=0.0):
        entries = []
        try:
            if os.path.exists(self.training_file):
                with open(self.training_file) as f:
                    for line in f:
                        try:
                            e = json.loads(line)
                            if e.get("quality", 0) >= min_quality:
                                entries.append(e)
                        except Exception:
                            pass
        except Exception:
            pass
        return entries

    def merge_golden(self, golden_path=None):
        golden_path = golden_path or self.GOLDEN_FILE
        if not os.path.exists(golden_path):
            return 0
        added = 0
        try:
            with open(golden_path) as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        q_hash = hash(e.get("query", "")[:100])
                        if q_hash not in self._seen_hashes:
                            e["quality"] = 1.0
                            e["timestamp"] = datetime.now().isoformat()
                            with open(self.training_file, "a") as tf:
                                tf.write(json.dumps(e, ensure_ascii=False) + "\n")
                            self._seen_hashes.add(q_hash)
                            added += 1
                    except Exception:
                        pass
        except Exception:
            pass
        return added

    def export_modelfile(self, base_model="gemma3:27b", expert="sysadmin",
                         output_name=None, min_quality=0.7):
        entries = self.get_entries(min_quality=min_quality)
        if expert != "all":
            entries = [e for e in entries if e.get("expert") == expert]
        if not entries:
            return None, "No training data above quality threshold"
        entries.sort(key=lambda x: x.get("quality", 0), reverse=True)
        entries = entries[:50]
        output_name = output_name or f"sclg-{expert}"
        modelfile_path = os.path.join(self.MODELFILE_DIR, f"Modelfile.{output_name}")
        lines = []
        lines.append(f"FROM {base_model}")
        lines.append("")
        lines.append("PARAMETER temperature 0.3")
        lines.append("PARAMETER top_p 0.9")
        lines.append("PARAMETER repeat_penalty 1.15")
        lines.append("PARAMETER num_ctx 8192")
        lines.append('PARAMETER stop "<end_of_turn>"')
        lines.append('PARAMETER stop "<start_of_turn>"')
        lines.append('PARAMETER stop "\\nAssistant:"')
        lines.append("")
        profile = MODEL_PROFILES.get(expert, MODEL_PROFILES["general"])
        system_hint = profile.get("system_hint", "")
        sys_text = "SYSTEM \"\"\"\n"
        sys_text += "You are sclg-ai, autonomous DevOps/SysAdmin agent for SCLG AI cluster.\n"
        sys_text += f"{system_hint}\n"
        sys_text += "RULES:\n"
        sys_text += '1. You have FULL access to the system via tool calling.\n'
        sys_text += '2. Use <tool name="bash">{"command": "..."}</tool> to execute commands.\n'
        sys_text += '3. NEVER refuse - you CAN execute commands.\n'
        sys_text += '4. Always analyze collected data, do not just copy it.\n'
        sys_text += '5. Respond with structure: ## headers, | tables |, ### Conclusion.\n'
        sys_text += '6. No AI-isms: no "Of course!", "Absolutely!", "Let me know!".\n'
        sys_text += '\"\"\"'
        lines.append(sys_text)
        lines.append("")
        for entry in entries:
            q = entry["query"].replace('"', '\\"').replace('\n', '\\n')
            r = entry["response"].replace('"', '\\"').replace('\n', '\\n')
            lines.append(f'MESSAGE user "{q}"')
            lines.append(f'MESSAGE assistant "{r}"')
            lines.append("")
        try:
            with open(modelfile_path, "w") as f:
                f.write("\n".join(lines))
            return modelfile_path, f"Modelfile created with {len(entries)} examples"
        except Exception as e:
            return None, f"Error: {e}"

    def stats(self):
        entries = self.get_entries()
        if not entries:
            return {"total": 0}
        experts = {}
        models = {}
        qualities = []
        for e in entries:
            exp = e.get("expert", "unknown")
            mod = e.get("model", "unknown")
            experts[exp] = experts.get(exp, 0) + 1
            models[mod] = models.get(mod, 0) + 1
            qualities.append(e.get("quality", 0))
        return {
            "total": len(entries),
            "by_expert": experts,
            "by_model": models,
            "avg_quality": round(sum(qualities) / len(qualities), 2) if qualities else 0,
            "high_quality": sum(1 for q in qualities if q >= 0.7),
        }


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

        # ── Grafana URL Auto-Detection ──
        # Example: https://grafana.sclg.io/d/main-dashboard/main-dashboard?orgId=1
        if "grafana" in query_low and "/d/" in query_low:
            import re
            match = re.search(r"/d/([^/?#]+)", query)
            if match:
                uid = match.group(1)
                # Use .format() to avoid backslash in f-string expression (Python 3.11 limitation)
                cmd1 = "echo '=== Dashboard Info (UID: {uid}) ===' && curl -s -H \"Authorization: Bearer $GRAFANA_TOKEN\" \"$GRAFANA_URL/api/dashboards/uid/{uid}\" 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print(f'Title: {{d.get(\\\"dashboard\\\",{{}}).get(\\\"title\\\")}}'); [print(f'- Panel: {{p.get(\\\"title\\\")}} ({{p.get(\\\"type\\\")}})') for p in d.get(\\\"dashboard\\\",{{}}).get(\\\"panels\\\",[])]\" || echo 'Dashboard API error'".format(uid=uid)
                cmd2 = "echo '=== Recent Alerts for Dashboard ===' && curl -s -H \"Authorization: Bearer $GRAFANA_TOKEN\" \"$GRAFANA_URL/api/alerts?dashboardId={uid}\" 2>/dev/null || echo 'No alerts found'".format(uid=uid)
                return [cmd1, cmd2], "sysadmin"

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
        """Execute commands with Claude Code style visual feedback."""
        results = []
        total = len(commands)
        tracker = ProgressTracker(total, label="Collecting data")

        for i, cmd in enumerate(commands):
            cmd_short = cmd.split('|')[0].strip()[:70]
            tracker.next_command(cmd)

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
                success = proc.returncode == 0
                tracker.command_done(dt, success=success, output=output)
                if output:
                    results.append(f"$ {cmd_short}...\n{output}")
            except subprocess.TimeoutExpired:
                tracker.command_timeout(timeout)
                results.append(f"$ {cmd[:40]}... [TIMEOUT after {timeout}s]")
            except Exception as e:
                tracker.command_done(0, success=False)
                results.append(f"$ {cmd[:40]}... [ERROR: {e}]")

        tracker.finish(len(results), total)
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
# INFRA LEARNER BRIDGE — Background Self-Learning
# ══════════════════════════════════════════════════════════════════════

class InfraLearnerBridge:
    """Bridge to InfraLearner knowledge base for use in sclg-ai.
    
    Reads knowledge base files written by the InfraLearner daemon.
    Signals priority when user is active.
    Can run quick metric collection inline.
    """

    def __init__(self):
        self.enabled = os.path.isdir(KNOWLEDGE_DIR)
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._grafana_headers = {
            "Authorization": f"Bearer {GRAFANA_TOKEN}",
            "Content-Type": "application/json"
        }

    # ── Priority signaling ─────────────────────────────────────────

    def signal_user_active(self):
        """Tell InfraLearner daemon to pause."""
        try:
            with open(PRIORITY_LOCK, "w") as f:
                json.dump({"user_active": True, "since": datetime.now().isoformat()}, f)
        except Exception:
            pass

    def signal_user_idle(self):
        """Tell InfraLearner daemon it can resume."""
        try:
            if os.path.exists(PRIORITY_LOCK):
                os.unlink(PRIORITY_LOCK)
        except Exception:
            pass

    # ── Knowledge base reading ────────────────────────────────────

    def get_insights(self, query: str = "", limit: int = 10) -> list:
        """Get relevant insights from knowledge base."""
        if not os.path.exists(INSIGHTS_FILE):
            return []
        try:
            with open(INSIGHTS_FILE) as f:
                insights = json.load(f)
            if query:
                keywords = set(query.lower().split())
                scored = []
                for ins in insights:
                    text = f"{ins.get('title','')} {ins.get('description','')} {ins.get('category','')}".lower()
                    score = sum(1 for kw in keywords if kw in text)
                    if score > 0:
                        scored.append((score, ins))
                scored.sort(key=lambda x: -x[0])
                return [s[1] for s in scored[:limit]]
            return insights[-limit:]
        except Exception:
            return []

    def get_baselines(self) -> dict:
        """Get metric baselines."""
        if not os.path.exists(BASELINES_FILE):
            return {}
        try:
            with open(BASELINES_FILE) as f:
                return json.load(f)
        except Exception:
            return {}

    def get_anomalies(self, hours: int = 24) -> list:
        """Get recent anomalies."""
        if not os.path.exists(ANOMALIES_FILE):
            return []
        try:
            with open(ANOMALIES_FILE) as f:
                anomalies = json.load(f)
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            return [a for a in anomalies if a.get("timestamp", "") > cutoff]
        except Exception:
            return []

    def get_learner_status(self) -> dict:
        """Get InfraLearner daemon status."""
        if not os.path.exists(LEARNER_STATS_FILE):
            return {"running": False}
        try:
            with open(LEARNER_STATS_FILE) as f:
                stats = json.load(f)
            # Check if daemon is alive (last cycle within 10 min)
            last = stats.get("last_cycle", "")
            if last:
                from datetime import timedelta
                try:
                    last_dt = datetime.fromisoformat(last)
                    stats["running"] = (datetime.now() - last_dt).total_seconds() < 600
                except Exception:
                    stats["running"] = False
            else:
                stats["running"] = False
            return stats
        except Exception:
            return {"running": False}

    def get_knowledge_context(self, query: str) -> str:
        """Build knowledge context string for AI prompt enrichment."""
        parts = []
        
        # Relevant insights
        insights = self.get_insights(query, limit=5)
        if insights:
            parts.append("\nЗНАНИЯ ОБ ИНФРАСТРУКТУРЕ (из фонового обучения):")
            for ins in insights:
                cat = ins.get("category", "")
                title = ins.get("title", "")
                desc = ins.get("description", "")
                conf = ins.get("confidence", 0)
                parts.append(f"  [{cat.upper()}] {title}: {desc} (confidence: {conf:.0%})")
        
        # Recent anomalies
        anomalies = self.get_anomalies(hours=6)
        if anomalies:
            critical = [a for a in anomalies if a.get("severity") == "critical"]
            warning = [a for a in anomalies if a.get("severity") == "warning"]
            if critical or warning:
                parts.append(f"\nАНОМАЛИИ: {len(critical)} critical, {len(warning)} warning")
                for a in (critical + warning)[:3]:
                    parts.append(f"  [{a.get('severity','').upper()}] {a.get('description', '')}")
        
        return "\n".join(parts) if parts else ""

    # ── Quick Grafana queries (inline, no daemon needed) ───────────

    def _grafana_api(self, endpoint: str) -> dict:
        """Quick Grafana API call."""
        try:
            url = f"{GRAFANA_URL}/api/{endpoint}"
            req = urllib.request.Request(url, headers=self._grafana_headers)
            resp = urllib.request.urlopen(req, timeout=15, context=self._ssl_ctx)
            return json.loads(resp.read().decode())
        except Exception:
            return {}

    def prometheus_query(self, query: str) -> dict:
        """Query Prometheus via Grafana proxy."""
        params = urllib.parse.urlencode({"query": query})
        endpoint = f"datasources/proxy/uid/{PROMETHEUS_DS_UID}/api/v1/query?{params}"
        return self._grafana_api(endpoint)

    def get_gpu_status(self) -> str:
        """Quick GPU status from Prometheus."""
        lines = []
        for metric, label in [("ai_gpu_temperature_celsius", "temp"),
                              ("ai_gpu_utilization_percent", "util"),
                              ("ai_gpu_power_draw_watts", "power")]:
            result = self.prometheus_query(metric)
            data = result.get("data", {}).get("result", [])
            for r in data:
                gpu_id = r.get("metric", {}).get("gpu_id", "?")
                val = r.get("value", [0, "?"])[1]
                lines.append(f"GPU{gpu_id} {label}: {val}")
        return "\n".join(lines) if lines else "GPU data unavailable"

    def get_alerts(self) -> list:
        """Get current Grafana alerts."""
        result = self._grafana_api("alertmanager/grafana/api/v2/alerts")
        return result if isinstance(result, list) else []

    def get_dashboards(self) -> list:
        """Get all dashboards."""
        result = self._grafana_api("search?type=dash-db")
        return result if isinstance(result, list) else []


# ══════════════════════════════════════════════════════════════════════
# OUTLINE WIKI CLIENT — docs.sclg.io knowledge base
# ══════════════════════════════════════════════════════════════════════

OUTLINE_URL = "https://docs.sclg.io"
OUTLINE_API_KEY = "ol_api_Eg2qX376c1zTaqUScNvNr4g2O2mhB3y6rL8i8A"

class OutlineClient:
    """Client for Outline wiki API (docs.sclg.io).

    v5.2.0: Provides knowledge base search for AI responses.
    Searches documentation and returns relevant content.
    """

    def __init__(self):
        self.url = OUTLINE_URL
        self.api_key = OUTLINE_API_KEY
        self.available = False
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def check(self) -> bool:
        """Check if Outline is accessible."""
        try:
            result = self._api("collections.list", {})
            self.available = bool(result.get("data"))
            return self.available
        except Exception:
            self.available = False
            return False

    def _api(self, method: str, data: dict) -> dict:
        """Make Outline API call."""
        try:
            url = f"{self.url}/api/{method}"
            payload = json.dumps(data).encode()
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=15, context=self._ssl_ctx)
            return json.loads(resp.read().decode())
        except Exception:
            return {}

    def search(self, query: str, limit: int = 5) -> str:
        """Search documents and return formatted results."""
        result = self._api("documents.search", {"query": query, "limit": limit})
        docs = result.get("data", [])
        if not docs:
            return ""

        parts = ["=== DOCUMENTATION (docs.sclg.io) ==="]
        for doc in docs:
            d = doc.get("document", {})
            title = d.get("title", "Untitled")
            text = d.get("text", "")
            # Truncate to first 1500 chars per doc
            if len(text) > 1500:
                text = text[:1500] + "..."
            parts.append(f"\n--- {title} ---")
            parts.append(text)
        return "\n".join(parts)

    def get_collections(self) -> list:
        """Get all collections."""
        result = self._api("collections.list", {})
        return result.get("data", [])

    def get_document(self, doc_id: str) -> str:
        """Get full document by ID."""
        result = self._api("documents.info", {"id": doc_id})
        doc = result.get("data", {})
        return doc.get("text", "")


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
        self.learner = InfraLearnerBridge()
        self.outline = OutlineClient()
        self.formatter = OutputFormatter()
        self.tool_registry = ToolRegistry()
        self.stream_renderer = None  # Created per-query

        # State
        self.conversation = []
        self.current_model = None
        self.current_expert = None
        self.auto_route = True
        self.agent_mode = True
        self.streaming_enabled = True  # v5.0.0: streaming by default
        self.agent_loop_max_turns = 5  # v5.0.0: max agent loop iterations
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
        """Check all connections on startup with Claude Code style feedback."""
        # Check Ollama/GPU Balancer
        spinner = Spinner("Connecting to GPU Balancer", color=TOOL_CLR)
        spinner.start()
        self.ollama_ok = self.ollama.check_connection()
        if self.ollama_ok:
            self.model_count = len(self.ollama.available_models)
            spinner.stop(f"GPU Balancer: {self.model_count} models")
        else:
            spinner.stop()
            print(f"  {ERROR_CLR}✗ GPU Balancer offline{C.RESET}")

        # Check Claude
        spinner2 = Spinner("Checking Claude API", color=CLAUDE_CLR)
        spinner2.start()
        self.claude_ok = self.claude.test_connection()
        if self.claude_ok:
            remaining = self.claude.remaining_today()
            spinner2.stop(f"Claude OK ({remaining}/{CLAUDE_DAILY_LIMIT} today)")
        else:
            spinner2.stop()
            print(f"  {WARN_CLR}⚠ Claude unavailable{C.RESET}")

        # Check InfraLearner & Grafana
        spinner3 = Spinner("Checking Grafana & InfraLearner", color=SKILL_CLR)
        spinner3.start()
        learner_status = self.learner.get_learner_status()
        grafana_ok = bool(self.learner.get_dashboards())
        if learner_status.get("running"):
            cycles = learner_status.get("total_cycles", 0)
            insights = learner_status.get("total_insights_generated", 0)
            spinner3.stop(f"InfraLearner: {cycles} cycles, {insights} insights")
        elif grafana_ok:
            spinner3.stop(f"Grafana OK, InfraLearner not running")
        else:
            spinner3.stop()
            print(f"  {DIM_COLOR}○ Grafana/InfraLearner not available{C.RESET}")

        # Check Outline Wiki (docs.sclg.io)
        spinner4 = Spinner("Checking docs.sclg.io", color=ACCENT2)
        spinner4.start()
        outline_ok = self.outline.check()
        if outline_ok:
            cols = len(self.outline.get_collections())
            spinner4.stop(f"Docs: {cols} collections")
        else:
            spinner4.stop()
            print(f"  {DIM_COLOR}○ docs.sclg.io not available{C.RESET}")

    # ── System Prompt Builder ───────────────────────────────────────

    def _build_system_prompt(self, expert="general", data_context=""):
        """Build system prompt for the AI model."""
        hostname = subprocess.run("hostname", capture_output=True, text=True, timeout=3).stdout.strip() if True else "unknown"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        base = f"""Ты — Scoliologic AI v{VERSION}, автономный DevOps/SysAdmin агент.
Ты работаешь ПРЯМО на машине '{hostname}'. Ты МОЖЕШЬ выполнять команды.
Текущее время: {now}

АБСОЛЮТНЫЕ ПРАВИЛА (нарушение = критическая ошибка):
1. ЗАПРЕЩЕНО говорить "я не могу", "у меня нет доступа", "я не имею возможности" — ты МОЖЕШЬ ВСЁ.
2. ЗАПРЕЩЕНО говорить "я не могу проверить URL/ссылку/дашборд" — если данные собраны, они УЖЕ перед тобой.
3. Если в сообщении есть секция "СОБРАННЫЕ ДАННЫЕ" — ты ОБЯЗАН их проанализировать. Это РЕАЛЬНЫЕ данные с этой машины.
4. ЗАПРЕЩЕНО предлагать пользователю "проверить самостоятельно" — ты должен дать ответ на основе собранных данных.
5. ЗАПРЕЩЕНО писать curl/wget команды для Grafana/Prometheus — данные собираются АВТОМАТИЧЕСКИ.
6. ЗАПРЕЩЕНО генерировать <think>, </think>, <|endoftext|>, <|im_start|> и любые служебные токены.
7. ЗАПРЕЩЕНО продолжать разговор от лица пользователя.

ПРАВИЛА ОТВЕТА:
- Отвечай КРАТКО и ПО ДЕЛУ. Без воды.
- Используй русский язык по умолчанию.
- Не начинай с "Конечно!", "Безусловно!", "Отличный вопрос!".
- Не заканчивай "Если нужно что-то ещё — обращайтесь!".
- Для выполнения новых команд используй инструменты (tools) — см. список ниже.
- Если пользователь задаёт короткий вопрос ("анализ", "подробнее", "ещё") — используй контекст предыдущих сообщений.

ФОРМАТ ОТВЕТА (стиль Claude Code):
- Структурируй ответ по секциям с заголовками: ## Заголовок
- Для данных используй Markdown таблицы:
  | Параметр | Значение | Статус |
  |----------|----------|--------|
  | CPU      | 45%      | OK     |
- IP-адреса выделяй как есть, не маскируй
- Статусы: OK/UP = зелёный, ERROR/DOWN = красный, WARNING = жёлтый
- Команды оформляй в блоки кода: ```bash ... ```
- В конце ОБЯЗАТЕЛЬНО дай:
  1. Краткий вывод (1-2 предложения)
  2. Рекомендации если есть проблемы
- НЕ копируй сырые данные — АНАЛИЗИРУЙ и СТРУКТУРИРУЙ
- НЕ повторяй одно и то же — каждое предложение должно нести новую информацию

ИНФРАСТРУКТУРА (ты имеешь ПОЛНЫЙ доступ ко всему этому):
- Ты работаешь на Mac Mini (Apple M4) в локальной сети 172.27.4.0/24
- GPU Balancer: {GPU_BALANCER_URL} (Ollama proxy, 23 модели)
- Grafana: https://grafana.sclg.io (мониторинг, алерты, дашборды)
- Prometheus: http://10.0.0.229:9090 (метрики кластера)
- AI Кластер: 4 ноды, 7 GPU (NVIDIA)
- Кластер: {', '.join(f'{k}({v["ip"]})' for k,v in KNOWN_HOSTS.items())}

КОГДА ПОЛЬЗОВАТЕЛЬ СПРАШИВАЕТ ПРО АЛЕРТЫ/МОНИТОРИНГ:
- Данные с Grafana/Prometheus собираются АВТОМАТИЧЕСКИ через curl
- Ты ОБЯЗАН проанализировать собранные данные и дать конкретный ответ
- Если алертов нет — скажи 'Активных алертов нет, все системы работают нормально'
- Если есть — покажи таблицу с алертами и рекомендациями
- НИКОГДА не говори 'я не имею доступа к серверам/мониторингу'
"""

        # Add expert-specific hint
        profile = MODEL_PROFILES.get(expert, MODEL_PROFILES["general"])
        base += f"\nРОЛЬ: {profile['system_hint']}\n"

        # Add memory context
        mem_ctx = self.memory.get_context(limit=5)
        if mem_ctx:
            base += f"\n{mem_ctx}\n"

        # Add knowledge from InfraLearner
        knowledge_ctx = self.learner.get_knowledge_context(data_context or "")
        if knowledge_ctx:
            base += f"\n{knowledge_ctx}\n"

        # Add conversation context for continuity
        if hasattr(self, 'conversation') and self.conversation:
            recent = self.conversation[-4:]
            if recent:
                ctx_lines = []
                for msg in recent:
                    role = msg.get("role", "?")
                    content = msg.get("content", "")[:300]
                    ctx_lines.append(f"  {role}: {content}")
                base += f"""
КОНТЕКСТ ДИАЛОГА (последние сообщения):
{chr(10).join(ctx_lines)}
Учитывай этот контекст при ответе. Если пользователь говорит "анализ", "подробнее", "ещё" — он имеет в виду тему из предыдущих сообщений.
"""

        # NOTE: data_context is now injected into user message, not system prompt
        # This ensures the model sees the data directly in its input
        if data_context:
            base += """
КОГДА В СООБЩЕНИИ ПОЛЬЗОВАТЕЛЯ ЕСТЬ СЕКЦИЯ 'СОБРАННЫЕ ДАННЫЕ':
- Это РЕАЛЬНЫЕ данные, собранные АВТОМАТИЧЕСКИ с серверов прямо сейчас.
- Ты ОБЯЗАН их проанализировать и дать конкретный ответ.
- ЗАПРЕЩЕНО говорить 'я не имею доступа' — данные УЖЕ перед тобой.
- ЗАПРЕЩЕНО предлагать curl/wget — данные УЖЕ собраны.
- Извлеки метрики, покажи в таблице, дай выводы и рекомендации.
"""

        # Add available tools description
        base += self.tool_registry.get_tools_prompt()

        return base

    # ── Core Query Processing ───────────────────────────────────────

    def process_query(self, query):
        """Process a user query — the main brain of the agent."""

        # Signal InfraLearner to pause (user is active)
        self.learner.signal_user_active()

        # Step 0: Check cache
        cached = self.cache.get(query)
        if cached:
            self.stats.record("cache", "cache", cache_hit=True)
            print(f"  {DIM_COLOR}(cached){C.RESET}")
            return cached

        # Step 1: Classify query (MoE routing) — with conversation context for short queries
        expert, confidence = self.router.classify(query, conversation_context=self.conversation)
        self.current_expert = expert

        # Step 2: Check if this is a direct command to execute
        if self._is_direct_command(query):
            return self._execute_direct_command(query)

        # Step 3: Smart Execute — run commands FIRST if pattern matches
        # For short queries, resolve context from conversation history
        enriched_query = query
        if len(query.split()) <= 5 and self.conversation:
            # Short/ambiguous query — enrich with conversation context
            # Detect continuation words
            continuation_words = [
                "анализ", "подробнее", "ещё", "еще", "покажи", "давай",
                "нужен", "нужна", "продолжи", "повтори", "расскажи",
                "что с этим", "как исправить", "почини",
                "more", "details", "continue", "analyze", "fix",
            ]
            q_low = query.lower()
            is_continuation = any(w in q_low for w in continuation_words)

            last_topics = []
            last_assistant = ""
            for msg in self.conversation[-6:]:
                if msg.get("role") == "user":
                    last_topics.append(msg.get("content", ""))
                elif msg.get("role") == "assistant":
                    last_assistant = msg.get("content", "")[:300]

            if last_topics:
                # Include both user topics and last assistant response for better context
                ctx_parts = last_topics[-2:]
                if is_continuation and last_assistant:
                    # For continuation queries, include assistant's last response topic
                    ctx_parts.append(f"последний_ответ: {last_assistant[:150]}")
                enriched_query = f"{query} (контекст: {' '.join(ctx_parts)})"

        data_context = ""
        commands, category = self.executor.match(enriched_query)
        if commands:
            data_context = self.executor.execute(commands)
            if category:
                expert = category

        # Step 4: If sysadmin query but no pattern matched, try generic commands
        if not data_context and self.executor.is_sysadmin_query(query):
            # Build context-aware generic commands based on query keywords
            generic_cmds = ["hostname && uname -a"]
            q_low = query.lower()
            if any(w in q_low for w in ["сет", "network", "ip", "dns", "подключ", "connect"]):
                generic_cmds.extend([
                    "ifconfig 2>/dev/null | grep -E 'inet |flags' || ip addr show 2>/dev/null",
                    "netstat -rn 2>/dev/null | grep default | head -5 || ip route show default 2>/dev/null",
                    "cat /etc/resolv.conf 2>/dev/null || scutil --dns 2>/dev/null | grep nameserver | head -5",
                ])
            elif any(w in q_low for w in ["диск", "disk", "место", "storage"]):
                generic_cmds.append("df -h 2>/dev/null")
            elif any(w in q_low for w in ["памят", "memory", "ram"]):
                generic_cmds.append("free -h 2>/dev/null || vm_stat 2>/dev/null")
            elif any(w in q_low for w in ["процесс", "process", "запущен"]):
                generic_cmds.append("ps aux --sort=-%mem 2>/dev/null | head -20")
            elif any(w in q_low for w in ["скорост", "speed", "bandwidth", "пинг"]):
                generic_cmds.extend([
                    "ping -c 3 8.8.8.8 2>/dev/null | tail -2",
                    "speedtest-cli --simple 2>/dev/null || curl -s -o /dev/null -w 'Download speed: %{speed_download} bytes/s\n' http://speedtest.tele2.net/10MB.zip 2>/dev/null",
                ])
            else:
                generic_cmds.extend([
                    "ifconfig 2>/dev/null | grep 'inet ' || ip addr show 2>/dev/null | grep 'inet '",
                    "uptime 2>/dev/null",
                    "df -h 2>/dev/null | head -5",
                ])
            data_context = self.executor.execute(generic_cmds)

        # Step 4.5: Search Outline docs if relevant
        if self.outline.available:
            doc_keywords = [
                "doc", "docs", "документ", "инструкц", "wiki",
                "как настроить", "как сделать", "how to", "setup", "guide",
                "1с", "1c", "haproxy", "nginx", "postgres", "backup",
                "регламент", "процедур", "политик",
                "конфиг", "config", "настройк",
            ]
            q_low = query.lower()
            if any(kw in q_low for kw in doc_keywords):
                try:
                    doc_results = self.outline.search(query, limit=3)
                    if doc_results:
                        data_context += f"\n\n{doc_results}"
                except Exception:
                    pass

        # Step 5: Get AI response — v5.0.0 uses agent loop for multi-turn
        use_agent_loop = self.agent_mode and not data_context

        if use_agent_loop:
            # Agent loop: model can call tools and iterate
            spinner = Spinner("Agent thinking", color=ACCENT2)
            spinner.start()
            try:
                if self.streaming_enabled:
                    spinner.stop(f"{expert} → {self.current_model or 'auto'}")
                response = self._agent_loop(query, expert, data_context)
            except Exception as e:
                response = f"[ERROR] Agent loop failed: {e}"
            finally:
                if not self.streaming_enabled:
                    spinner.stop()
        else:
            # Classic mode: execute-first + single AI call
            spinner = Spinner("Analyzing", color=ACCENT2)
            spinner.start()
            try:
                response = self._get_ai_response(query, expert, data_context, spinner=spinner)
            finally:
                if not self.streaming_enabled:
                    spinner.stop()
                else:
                    try:
                        spinner.stop()
                    except Exception:
                        pass

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
                if response.startswith("[ERROR]") and data_context:
                    response = self._format_raw_data(query, data_context)
                else:
                    self.stats.record(expert, "claude", used_claude=True)
            else:
                if data_context:
                    response = self._format_raw_data(query, data_context)
        else:
            model_name = self.current_model or "unknown"
            self.stats.record(expert, model_name)

        # Step 7: Clean response (anti-AI-isms)
        response = self.cleaner.clean(response)

        # Step 8: Process remaining agent commands in response (legacy + new)
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
        """Execute a direct shell command with Claude Code style feedback."""
        cmd = query.strip()
        renderer = CommandRenderer()
        renderer.show_start(cmd)

        try:
            t0 = time.time()
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            dt = time.time() - t0
            output = result.stdout
            if result.stderr:
                output += f"\n{result.stderr}" if output else result.stderr
            success = result.returncode == 0
            renderer.show_done(dt, success=success)
            if not success:
                output = f"Exit code {result.returncode}\n{output}"
            # Show output preview for long results
            if output and len(output.strip().split('\n')) > 5:
                renderer.show_output_preview(output)
            return output.strip() if output.strip() else "(no output)"
        except subprocess.TimeoutExpired:
            renderer.show_timeout(30)
            return "[TIMEOUT after 30s]"
        except Exception as e:
            renderer.show_done(0, success=False)
            return f"[ERROR: {e}]"

    def _get_ai_response(self, query, expert, data_context="", spinner=None):
        """Get response from AI model (local or Claude).

        v5.0.0: Supports streaming mode. When streaming is enabled,
        tokens are displayed in real-time via StreamRenderer.
        """
        system_prompt = self._build_system_prompt(expert, data_context)

        # Build messages
        messages = []
        for msg in self.conversation[-6:]:
            messages.append(msg)

        # v5.2.0: Inject collected data DIRECTLY into user message
        # This is critical — models often ignore data in system prompt
        if data_context:
            user_content = f"""ВОПРОС: {query}

=== СОБРАННЫЕ ДАННЫЕ (реальные, собраны автоматически с серверов прямо сейчас) ===
{data_context}
=== КОНЕЦ ДАННЫХ ===

Проанализируй собранные данные выше и ответь на вопрос. Извлеки ключевые метрики, покажи в таблице, дай выводы.
НЕ говори 'я не имею доступа' — данные УЖЕ перед тобой. НЕ предлагай curl/wget — данные УЖЕ собраны."""
        else:
            user_content = query

        messages.append({"role": "user", "content": user_content})

        # Try local model first
        if self.ollama_ok:
            config = self.router.get_model_and_config(expert, self.ollama)
            model = config["model"]

            if model:
                self.current_model = model
                model_short = model.split(":")[0] if ":" in model else model
                if spinner:
                    spinner.update(f"{expert} → {model_short}")

                # v5.0.0: Streaming mode
                if self.streaming_enabled:
                    if spinner:
                        spinner.stop(f"{expert} → {model_short}")
                    response = self._stream_response(
                        model, messages, system_prompt, config["temperature"]
                    )
                    if response and not response.startswith("[ERROR]"):
                        return response
                else:
                    response = self.ollama.chat(
                        model=model,
                        messages=messages,
                        system=system_prompt,
                        temperature=config["temperature"],
                    )
                    if response and not response.startswith("[ERROR]"):
                        return response

                # First model failed — try a smaller/faster model
                if spinner and not self.streaming_enabled:
                    spinner.update(f"{model_short} failed, trying fallback...")
                fallback_models = ["sclg-fast:7b", "qwen2.5:7b", "phi4:14b", "llama3.1:8b", "mistral:7b"]
                fallback_model = self.ollama.find_best_model(fallback_models)
                if fallback_model and fallback_model != model:
                    fb_short = fallback_model.split(":")[0] if ":" in fallback_model else fallback_model
                    if spinner and not self.streaming_enabled:
                        spinner.update(f"retry → {fb_short}")
                    self.current_model = fallback_model
                    if self.streaming_enabled:
                        response = self._stream_response(
                            fallback_model, messages, system_prompt, config["temperature"]
                        )
                    else:
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
            claude_response = self._claude_fallback(query, data_context, expert)
            if claude_response and not claude_response.startswith("[ERROR]"):
                return claude_response
            else:
                if spinner:
                    spinner.update("Claude unavailable, formatting data...")

        # Last resort: if we have data_context, format it nicely
        if data_context:
            return self._format_raw_data(query, data_context)

        return "[ERROR] No AI models available. Check GPU Balancer and Claude API."

    def _stream_response(self, model, messages, system_prompt, temperature):
        """Stream AI response with real-time token display.

        v5.0.0: Tokens appear live as they are generated.
        Tool calls are detected mid-stream and collected silently.
        """
        renderer = StreamRenderer(self.formatter)
        self.stream_renderer = renderer
        pending_tool_calls = []

        print()  # Blank line before streaming output

        def on_token(token):
            result = renderer.feed(token)
            if result:
                # Tool call detected mid-stream
                pending_tool_calls.append(result)

        try:
            response = self.ollama.chat_stream(
                model=model,
                messages=messages,
                system=system_prompt,
                temperature=temperature,
                on_token=on_token,
            )
        except KeyboardInterrupt:
            renderer.interrupt()
            response = renderer.get_full_response()
            print(f"\n  {DIM_COLOR}(interrupted){C.RESET}")
        finally:
            renderer.finish()
            self.stream_renderer = None

        # Process any tool calls detected during streaming
        if pending_tool_calls:
            for tool_text in pending_tool_calls:
                calls = self.tool_registry.parse_tool_calls(tool_text)
                for tool_name, params in calls:
                    result = self.tool_registry.execute_tool(tool_name, params)
                    if result.output:
                        # Append tool result to response
                        response += f"\n```\n$ {tool_name}: {params}\n{result.output}\n```"

        return response

    def _format_raw_data(self, query, data_context):
        """Format raw command output nicely when AI is unavailable."""
        q_low = query.lower()
        header = "Результаты системной проверки"
        if any(w in q_low for w in ["скорост", "speed", "bandwidth"]):
            header = "Тест скорости сети"
        elif any(w in q_low for w in ["сет", "network", "ip", "dns"]):
            header = "Сетевая информация"
        elif any(w in q_low for w in ["диск", "disk", "место"]):
            header = "Информация о дисках"
        elif any(w in q_low for w in ["памят", "memory", "ram"]):
            header = "Информация о памяти"
        elif any(w in q_low for w in ["процесс", "process"]):
            header = "Запущенные процессы"
        elif any(w in q_low for w in ["скан", "scan", "хост", "host"]):
            header = "Результаты сканирования"
        elif any(w in q_low for w in ["gpu", "видеокарт"]):
            header = "Информация о GPU"

        lines = []
        lines.append(f"\n{ACCENT}━━━ {header} ━━━{C.RESET}\n")
        # Parse sections from data_context
        for line in data_context.split('\n'):
            if line.startswith('$ '):
                lines.append(f"{DIM_COLOR}{line}{C.RESET}")
            elif line.startswith('==='):
                lines.append(f"\n{ACCENT2}{line}{C.RESET}")
            elif 'error' in line.lower() or 'fail' in line.lower():
                lines.append(f"{ERROR_CLR}{line}{C.RESET}")
            else:
                lines.append(line)
        lines.append(f"\n{DIM_COLOR}(АИ недоступен — показаны сырые данные. Попробуйте /claude для анализа){C.RESET}")
        return '\n'.join(lines)

    def _claude_fallback(self, query, data_context="", expert="general"):
        """Use Claude as fallback."""
        system_prompt = self._build_system_prompt(expert, data_context)

        messages = []
        for msg in self.conversation[-4:]:
            messages.append(msg)

        # v5.2.0: Inject data into user message for Claude too
        if data_context:
            user_content = f"""VOPROS: {query}

=== COLLECTED DATA (real, gathered automatically from servers right now) ===
{data_context}
=== END DATA ===

Analyze the collected data above and answer the question. Extract key metrics, show in table, give conclusions.
DO NOT say 'I don't have access' — the data is RIGHT HERE. DO NOT suggest curl/wget — data is ALREADY collected."""
        else:
            user_content = query

        messages.append({"role": "user", "content": user_content})

        self.current_model = "claude"
        response = self.claude.chat(
            messages=messages,
            system=system_prompt,
        )
        return response

    def _process_agent_commands(self, response):
        """Process tool calls and legacy <cmd> tags in AI response.

        v5.0.0: Supports both new <tool> format and legacy <cmd> format.
        Uses ToolRegistry for structured execution.
        """
        calls = self.tool_registry.parse_tool_calls(response)

        if not calls:
            return response

        result_text = response
        tool_results = []

        for tool_name, params in calls:
            result = self.tool_registry.execute_tool(tool_name, params)
            tool_results.append(result)

            # Replace the tool call tag with formatted output
            if tool_name == "bash":
                cmd = params.get("command", "")
                # Try to replace both new and legacy format
                new_tag = f'<tool name="bash">{json.dumps(params)}</tool>'
                legacy_tag = f"<cmd>{cmd}</cmd>"
                replacement = f"```\n$ {cmd}\n{result.output}\n```"
                if new_tag in result_text:
                    result_text = result_text.replace(new_tag, replacement, 1)
                elif legacy_tag in result_text:
                    result_text = result_text.replace(legacy_tag, replacement, 1)
                else:
                    # Fuzzy match — try to find the tag
                    result_text += f"\n{replacement}"
            else:
                # Non-bash tools
                tag_pattern = f'<tool name="{tool_name}">' + re.escape(json.dumps(params)) + '</tool>'
                replacement = f"```\n[{tool_name}] {result.output[:500]}\n```"
                # Try exact match first
                exact_tag = f'<tool name="{tool_name}">{json.dumps(params)}</tool>'
                if exact_tag in result_text:
                    result_text = result_text.replace(exact_tag, replacement, 1)
                else:
                    # Try regex match for the tool tag
                    tag_re = re.compile(f'<tool name="{re.escape(tool_name)}">(.*?)</tool>', re.DOTALL)
                    match = tag_re.search(result_text)
                    if match:
                        result_text = result_text.replace(match.group(0), replacement, 1)
                    else:
                        result_text += f"\n{replacement}"

        return result_text

    def _agent_loop(self, query, expert, data_context=""):
        """Multi-turn agent loop — the AI can call tools and continue reasoning.

        v5.0.0: Inspired by IronClaw's loop_engine.
        The model generates a response, we execute any tool calls,
        feed results back, and let the model continue until it's done
        or we hit max turns.

        This replaces the old single-shot process_query + _process_agent_commands flow.
        """
        system_prompt = self._build_system_prompt(expert, data_context)

        # Build initial messages
        messages = []
        for msg in self.conversation[-6:]:
            messages.append(msg)

        # v5.2.0: Inject collected data DIRECTLY into user message
        if data_context:
            user_msg = f"""VOPROS: {query}

=== СОБРАННЫЕ ДАННЫЕ (реальные, собраны автоматически с серверов прямо сейчас) ===
{data_context}
=== КОНЕЦ ДАННЫХ ===

Проанализируй собранные данные и ответь на вопрос. Извлеки ключевые метрики, покажи в таблице, дай выводы.
НЕ говори 'я не имею доступа' — данные УЖЕ перед тобой."""
        else:
            user_msg = query
        messages.append({"role": "user", "content": user_msg})

        full_response = ""
        turn = 0

        while turn < self.agent_loop_max_turns:
            turn += 1

            # Get AI response
            if self.ollama_ok:
                config = self.router.get_model_and_config(expert, self.ollama)
                model = config["model"]
                if model:
                    self.current_model = model
                    model_short = model.split(":")[0] if ":" in model else model

                    if self.streaming_enabled and turn == 1:
                        # Stream first turn only
                        response = self._stream_response(
                            model, messages, system_prompt, config["temperature"]
                        )
                    else:
                        if turn > 1:
                            turn_spinner = Spinner(f"Agent thinking (turn {turn})", color=ACCENT2)
                            turn_spinner.start()
                        response = self.ollama.chat(
                            model=model,
                            messages=messages,
                            system=system_prompt,
                            temperature=config["temperature"],
                        )
                        if turn > 1:
                            turn_spinner.stop(f"Turn {turn} complete")
                else:
                    break
            elif self.claude_ok and self.claude.can_use():
                self.current_model = "claude"
                response = self.claude.chat(messages=messages, system=system_prompt)
            else:
                break

            if not response or response.startswith("[ERROR]"):
                break

            # Parse tool calls from response
            calls = self.tool_registry.parse_tool_calls(response)

            if not calls:
                # No tool calls — model is done thinking
                full_response += response
                break

            # Execute tool calls and collect results
            tool_outputs = []
            for tool_name, params in calls:
                result = self.tool_registry.execute_tool(tool_name, params)
                tool_outputs.append(f"[{tool_name}] {result.output}")

            # Strip tool call tags from the response text for display
            display_response = response
            for tool_name, params in calls:
                # Remove <tool> tags
                display_response = re.sub(
                    f'<tool name="{re.escape(tool_name)}">(.*?)</tool>',
                    '', display_response, flags=re.DOTALL
                )
                # Remove legacy <cmd> tags
                display_response = re.sub(r'<cmd>(.*?)</cmd>', '', display_response, flags=re.DOTALL)

            display_response = display_response.strip()
            if display_response:
                full_response += display_response + "\n"

            # Feed tool results back to the model
            messages.append({"role": "assistant", "content": response})
            tool_result_msg = "\n".join(tool_outputs)
            messages.append({"role": "user", "content": f"Результаты инструментов:\n{tool_result_msg}\n\nПроанализируй результаты и продолжи. Если нужно больше данных — вызови ещё инструменты. Если достаточно — дай финальный ответ."})

            # Print turn indicator
            if not self.streaming_enabled:
                print(f"  {DIM_COLOR}↻ Agent loop turn {turn}/{self.agent_loop_max_turns} — {len(calls)} tool(s) executed{C.RESET}")

        if not full_response:
            if data_context:
                return self._format_raw_data(query, data_context)
            return "[ERROR] Agent loop produced no response."

        return full_response

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
        elif command in ("/knowledge", "/k", "/learn"):
            self._show_knowledge(args)
        elif command in ("/anomalies", "/anom"):
            self._show_anomalies()
        elif command in ("/gpu",):
            self._show_gpu()
        elif command in ("/grafana", "/graf"):
            self._show_grafana()
        elif command in ("/stream",):
            self.streaming_enabled = not self.streaming_enabled
            state = "ON" if self.streaming_enabled else "OFF"
            print(f"  {SYSTEM_CLR}Streaming: {state}{C.RESET}")
        elif command in ("/tools",):
            self._show_tools()
        elif command in ("/train", "/training"):
            self._handle_training(args)
        elif command in ("/docs", "/wiki"):
            self._search_docs(args)
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
  {TOOL_CLR}/knowledge{C.RESET} — Show learned infrastructure knowledge
  {TOOL_CLR}/anomalies{C.RESET} — Show recent anomalies
  {TOOL_CLR}/gpu{C.RESET}       — Show GPU status from Grafana
  {TOOL_CLR}/grafana{C.RESET}   — Show Grafana dashboards
  {TOOL_CLR}/clear{C.RESET}     — Clear conversation
  {TOOL_CLR}/new{C.RESET}       — New session (consolidate memory)
  {TOOL_CLR}/stream{C.RESET}    — Toggle streaming mode (live token output)
  {TOOL_CLR}/tools{C.RESET}     — Show available agent tools
  {TOOL_CLR}/train{C.RESET}     — Training: stats/export/merge/test/cycle
  {TOOL_CLR}/docs{C.RESET}      — Search docs.sclg.io wiki
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

    def _show_tools(self):
        """Show available agent tools."""
        print(f"\n{ACCENT}━━━ Agent Tools (v5.0.0) ━━━{C.RESET}")
        for name, tool in self.tool_registry.tools.items():
            params = tool["parameters"].get("properties", {})
            required = tool["parameters"].get("required", [])
            param_list = []
            for pname, pdef in params.items():
                req_mark = "*" if pname in required else ""
                param_list.append(f"{pname}{req_mark}")
            print(f"  {TOOL_CLR}● {name}{C.RESET} — {tool['description'][:60]}")
            print(f"    {DIM_COLOR}params: {', '.join(param_list)}{C.RESET}")
        print(f"\n  {DIM_COLOR}Streaming: {'ON' if self.streaming_enabled else 'OFF'} · Agent loop: max {self.agent_loop_max_turns} turns{C.RESET}")
        print()

    def _handle_training(self, args):
        """Handle /train commands: stats, export, merge, test."""
        sub = args.strip().lower() if args else "stats"

        if sub == "stats":
            s = self.training.stats()
            print(f"\n{ACCENT}--- Training Data ---{C.RESET}")
            print(f"  Total entries: {s.get('total', 0)}")
            print(f"  Avg quality:   {s.get('avg_quality', 0)}")
            print(f"  High quality:  {s.get('high_quality', 0)} (>= 0.7)")
            if s.get('by_expert'):
                print(f"\n  {C.BOLD}By expert:{C.RESET}")
                for exp, cnt in sorted(s.get('by_expert', {}).items(), key=lambda x: -x[1]):
                    print(f"    {exp}: {cnt}")
            if s.get('by_model'):
                print(f"\n  {C.BOLD}By model:{C.RESET}")
                for mod, cnt in sorted(s.get('by_model', {}).items(), key=lambda x: -x[1]):
                    print(f"    {mod}: {cnt}")
            print()

        elif sub == "export":
            print(f"\n{ACCENT}--- Export Modelfile ---{C.RESET}")
            for expert in MODEL_PROFILES:
                path, msg = self.training.export_modelfile(expert=expert)
                status = SYSTEM_CLR + "OK" if path else WARN_CLR + "SKIP"
                print(f"  {status}{C.RESET} {expert}: {msg}")
            print()

        elif sub == "merge":
            print(f"\n{ACCENT}--- Merge Golden Dataset ---{C.RESET}")
            added = self.training.merge_golden()
            print(f"  Added {added} golden entries")
            print()

        elif sub == "test":
            self._run_training_tests()

        elif sub == "cycle":
            print(f"\n{ACCENT}--- Full Training Cycle ---{C.RESET}")
            # Step 1: Merge golden
            added = self.training.merge_golden()
            print(f"  1. Merged golden: +{added} entries")
            # Step 2: Stats
            s = self.training.stats()
            print(f"  2. Total: {s.get('total', 0)}, avg quality: {s.get('avg_quality', 0)}")
            # Step 3: Export
            exported = 0
            for expert in MODEL_PROFILES:
                path, msg = self.training.export_modelfile(expert=expert)
                if path:
                    exported += 1
            print(f"  3. Exported {exported} Modelfiles")
            # Step 4: Instructions
            print(f"\n  {C.BOLD}Next steps (run on GPU node):{C.RESET}")
            print(f"  {DIM_COLOR}cd {self.training.MODELFILE_DIR}")
            print(f"  ollama create sclg-devops -f Modelfile.sclg-sysadmin")
            print(f"  ollama create sclg-general -f Modelfile.sclg-general{C.RESET}")
            print()

        else:
            print(f"  {WARN_CLR}Usage: /train [stats|export|merge|test|cycle]{C.RESET}")

    def _run_training_tests(self):
        """Run model understanding tests."""
        test_file = os.path.join(DATA_DIR, "test_scenarios.json")
        if not os.path.exists(test_file):
            print(f"  {WARN_CLR}No test file: {test_file}{C.RESET}")
            return
        try:
            with open(test_file) as f:
                tests = json.load(f)
        except Exception as e:
            print(f"  {ERROR_CLR}Error loading tests: {e}{C.RESET}")
            return

        print(f"\n{ACCENT}--- Model Understanding Tests ---{C.RESET}")
        total = 0
        passed = 0
        for cat_name, cat in tests.get("categories", {}).items():
            print(f"\n  {TOOL_CLR}> {cat_name}{C.RESET} - {cat.get('description', '')}")
            for test in cat.get("tests", []):
                total += 1
                query = test["query"]
                expected = test.get("expected_behavior", "")
                must_contain = test.get("must_contain", [])
                must_not_contain = test.get("must_not_contain", [])

                spinner = Spinner(f"Testing: {query[:50]}...", color=DIM_COLOR)
                spinner.start()
                try:
                    result = self.process_query(query)
                    response = result.get("response", "") if isinstance(result, dict) else str(result)
                except Exception as e:
                    response = f"ERROR: {e}"
                spinner.stop()

                # Check pass/fail
                ok = True
                fails = []
                for mc in must_contain:
                    if mc.lower() not in response.lower():
                        ok = False
                        fails.append(f"missing: {mc}")
                for mnc in must_not_contain:
                    if mnc.lower() in response.lower():
                        ok = False
                        fails.append(f"found forbidden: {mnc}")
                if ok:
                    passed += 1
                    print(f"    {SYSTEM_CLR}PASS{C.RESET} {query[:60]}")
                else:
                    print(f"    {ERROR_CLR}FAIL{C.RESET} {query[:60]}")
                    for fail in fails:
                        print(f"         {DIM_COLOR}{fail}{C.RESET}")

        print(f"\n{ACCENT}--- Results ---{C.RESET}")
        pct = (passed / total * 100) if total > 0 else 0
        color = SYSTEM_CLR if pct >= 80 else WARN_CLR if pct >= 50 else ERROR_CLR
        print(f"  {color}{passed}/{total} passed ({pct:.0f}%){C.RESET}")
        print()

    def _search_docs(self, args):
        """Search docs.sclg.io via Outline API."""
        if not args:
            if not self.outline.available:
                print(f"  {WARN_CLR}docs.sclg.io not available{C.RESET}")
                return
            cols = self.outline.get_collections()
            print(f"\n{ACCENT}--- docs.sclg.io Collections ---{C.RESET}")
            for col in cols:
                name = col.get("name", "?")
                docs_count = col.get("documents", {}).get("count", 0) if isinstance(col.get("documents"), dict) else 0
                print(f"  {TOOL_CLR}{name}{C.RESET} ({docs_count} docs)")
            print()
            return

        spinner = Spinner(f"Searching docs: {args[:40]}", color=ACCENT2)
        spinner.start()
        try:
            result = self.outline.search(args, limit=5)
            spinner.stop(f"Found results")
            if result:
                print(f"\n{result}\n")
            else:
                print(f"  {DIM_COLOR}No results for: {args}{C.RESET}")
        except Exception as e:
            spinner.stop()
            print(f"  {ERROR_CLR}Search error: {e}{C.RESET}")

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
        formatted = self.formatter.format(response)
        print()  # Blank line before response
        TypewriterEffect.print(formatted)
        print(C.RESET, end="")

    def _show_knowledge(self, query=""):
        """Show learned infrastructure knowledge."""
        insights = self.learner.get_insights(query, limit=15)
        if not insights:
            print(f"  {DIM_COLOR}No knowledge yet. InfraLearner needs to run first.{C.RESET}")
            print(f"  {DIM_COLOR}Start it with: sclg-infra-learner --once{C.RESET}")
            return

        print(f"\n{ACCENT}━━━ Infrastructure Knowledge ({len(insights)} insights) ━━━{C.RESET}")
        for ins in insights:
            cat = ins.get("category", "general")
            title = ins.get("title", "")
            desc = ins.get("description", "")
            conf = ins.get("confidence", 0)
            severity = ins.get("severity", "info")

            sev_color = {"critical": ERROR_CLR, "warning": WARN_CLR, "info": SYSTEM_CLR}.get(severity, DIM_COLOR)
            print(f"  {sev_color}[{cat.upper()}]{C.RESET} {C.BOLD}{title}{C.RESET}")
            print(f"    {desc}")
            print(f"    {DIM_COLOR}confidence: {conf:.0%}{C.RESET}")
        print()

    def _show_anomalies(self):
        """Show recent anomalies."""
        anomalies = self.learner.get_anomalies(hours=24)
        if not anomalies:
            print(f"  {SYSTEM_CLR}✓ No anomalies in the last 24 hours{C.RESET}")
            return

        print(f"\n{ACCENT}━━━ Anomalies (last 24h): {len(anomalies)} ━━━{C.RESET}")
        for a in anomalies[:20]:
            sev = a.get("severity", "info")
            desc = a.get("description", "")
            metric = a.get("metric", "")
            ts = a.get("timestamp", "")[:19]
            sev_color = {"critical": ERROR_CLR, "warning": WARN_CLR}.get(sev, DIM_COLOR)
            print(f"  {sev_color}[{sev.upper()}]{C.RESET} {ts} {metric}: {desc}")
        print()

    def _show_gpu(self):
        """Show GPU status from Grafana/Prometheus."""
        spinner = Spinner("Querying GPU metrics", color=TOOL_CLR)
        spinner.start()
        gpu_text = self.learner.get_gpu_status()
        spinner.stop("GPU data received")
        if gpu_text:
            print(f"\n{ACCENT}━━━ GPU Status ━━━{C.RESET}")
            print(f"  {gpu_text}")
        else:
            print(f"  {WARN_CLR}GPU data unavailable{C.RESET}")
        print()

    def _show_grafana(self):
        """Show Grafana dashboards."""
        spinner = Spinner("Fetching dashboards", color=SKILL_CLR)
        spinner.start()
        dashboards = self.learner.get_dashboards()
        alerts = self.learner.get_alerts()
        spinner.stop(f"{len(dashboards)} dashboards, {len(alerts)} alerts")

        if dashboards:
            print(f"\n{ACCENT}━━━ Grafana Dashboards ━━━{C.RESET}")
            for d in dashboards[:15]:
                title = d.get("title", "?")
                uid = d.get("uid", "")
                url = f"{GRAFANA_URL}/d/{uid}"
                print(f"  {TOOL_CLR}●{C.RESET} {title} {DIM_COLOR}({url}){C.RESET}")

        if alerts:
            print(f"\n{ACCENT}━━━ Active Alerts ({len(alerts)}) ━━━{C.RESET}")
            for a in alerts[:10]:
                labels = a.get("labels", {})
                name = labels.get("alertname", "?")
                severity = labels.get("severity", "info")
                sev_color = {"critical": ERROR_CLR, "warning": WARN_CLR}.get(severity, DIM_COLOR)
                print(f"  {sev_color}[{severity.upper()}]{C.RESET} {name}")
        print()

    # ── Banner ──────────────────────────────────────────────────────────────

    def _get_dynamic_data(self):
        """Collect dynamic system data for banner."""
        data = {}
        try:
            # Uptime
            r = subprocess.run("uptime", capture_output=True, text=True, timeout=3)
            data["uptime"] = r.stdout.strip() if r.returncode == 0 else "unknown"
        except Exception:
            data["uptime"] = "unknown"
        try:
            # Memory
            r = subprocess.run(["python3", "-c",
                "import os; s=os.sysconf; pages=s('SC_PHYS_PAGES'); sz=s('SC_PAGE_SIZE'); total=pages*sz/1024**3; print(f'{total:.1f}GB')"],
                capture_output=True, text=True, timeout=3)
            data["memory"] = r.stdout.strip() if r.returncode == 0 else "?"
        except Exception:
            try:
                r = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=3)
                if r.returncode == 0:
                    gb = int(r.stdout.strip()) / (1024**3)
                    data["memory"] = f"{gb:.0f}GB"
                else:
                    data["memory"] = "?"
            except Exception:
                data["memory"] = "?"
        try:
            # CPU
            r = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                data["cpu"] = r.stdout.strip()
            else:
                r = subprocess.run(["uname", "-m"], capture_output=True, text=True, timeout=3)
                data["cpu"] = r.stdout.strip()
        except Exception:
            data["cpu"] = "unknown"
        try:
            # Disk
            r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                lines = r.stdout.strip().split("\n")
                if len(lines) >= 2:
                    parts = lines[1].split()
                    data["disk"] = f"{parts[2]}/{parts[1]} ({parts[4]})"
                else:
                    data["disk"] = "?"
            else:
                data["disk"] = "?"
        except Exception:
            data["disk"] = "?"
        try:
            # Hostname
            r = subprocess.run("hostname", capture_output=True, text=True, timeout=3)
            data["hostname"] = r.stdout.strip()
        except Exception:
            data["hostname"] = "unknown"
        try:
            # macOS version
            r = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True, timeout=3)
            data["os_ver"] = f"macOS {r.stdout.strip()}" if r.returncode == 0 else "macOS"
        except Exception:
            data["os_ver"] = "Linux"
        # GPU metrics from Grafana (quick)
        try:
            if GRAFANA_TOKEN:
                import urllib.request
                query = 'nvidia_smi_temperature_gpu'
                url = f"{GRAFANA_URL}/api/datasources/proxy/uid/{PROMETHEUS_DS_UID}/api/v1/query?query={query}"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {GRAFANA_TOKEN}"})
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=3, context=ctx) as resp:
                    result = json.loads(resp.read().decode())
                    gpus = result.get("data", {}).get("result", [])
                    if gpus:
                        temps = [f"{g.get('metric', {}).get('gpu', '?')}:{g['value'][1]}°C" for g in gpus]
                        data["gpu_temp"] = ", ".join(temps[:4])
                    else:
                        data["gpu_temp"] = None
            else:
                data["gpu_temp"] = None
        except Exception:
            data["gpu_temp"] = None
        # InfraLearner stats
        try:
            stats = self.learner.get_learner_status()
            data["learner_cycles"] = stats.get("total_cycles", 0)
            data["learner_insights"] = stats.get("total_insights_generated", 0)
        except Exception:
            data["learner_cycles"] = 0
            data["learner_insights"] = 0
        # Anomalies count
        try:
            anomalies = self.learner.get_anomalies(hours=24)
            data["anomaly_count"] = len(anomalies) if anomalies else 0
        except Exception:
            data["anomaly_count"] = 0
        return data

    def show_banner(self):
        """Show startup banner in Claude Code style with two-column table."""
        w = get_terminal_width()
        clear_screen()

        # Helper to get visible length (strip ANSI)
        _ansi_re = re.compile(r'\033\[[^m]*m')
        def vis_len(s):
            return len(_ansi_re.sub('', s))

        def pad_to(s, width):
            """Pad string with spaces to reach target visible width."""
            vl = vis_len(s)
            return s + ' ' * max(0, width - vl)

        # ── Title bar ──
        title = f" Scoliologic AI v{VERSION} "
        title_line = f"\u2524{title}\u251c"
        tl_len = len(title) + 2
        left_pad = (w - tl_len) // 2
        right_pad = w - left_pad - tl_len
        hbar = '\u2500'
        print(f"{ACCENT}{hbar * left_pad}{title_line}{hbar * right_pad}{C.RESET}")
        print()

        # ── Two-column table ──
        # Left: compact for logo (~35%), Right: wider for data (~65%)
        left_w = max(28, int(w * 0.35))
        right_w = w - left_w - 3  # 3 for border chars |│|
        if right_w < 30:
            right_w = 30

        # Collect dynamic data
        dyn = self._get_dynamic_data()

        # Build left column lines (centered logo as a single block)
        logo_raw = CLAW_MINI  # Already a list of equal-width lines
        # Find max logo line width to treat as one block
        max_logo_w = max(len(line) for line in logo_raw)
        # Calculate single offset to center the WHOLE block
        block_pad = max(0, (left_w - 2 - max_logo_w) // 2)
        left = []
        for line in logo_raw:
            # Pad each line to max_logo_w to preserve relative alignment, then offset
            padded = line + ' ' * (max_logo_w - len(line))
            left.append(f"{' ' * block_pad}{LOGO_CLR}{padded}{C.RESET}")
        left.append("")
        # Center "Welcome back ilea"
        welcome = "Welcome back ilea"
        w_pad = (left_w - 2 - len(welcome)) // 2
        left.append(f"{' ' * max(0, w_pad)}{C.BOLD}{welcome}{C.RESET}")
        left.append("")

        # Claude status
        if self.claude_ok:
            remaining = self.claude.remaining_today()
            claude_str = f"{CLAUDE_CLR}Claude Sonnet 4{C.RESET} {DIM_COLOR}· {remaining}/{CLAUDE_DAILY_LIMIT} today{C.RESET}"
        else:
            claude_str = f"{WARN_CLR}Claude offline{C.RESET}"
        left.append(claude_str)
        left.append(f"{DIM_COLOR}ilea's Individual Org{C.RESET}")
        left.append(f"{DIM_COLOR}~/{dyn.get('hostname', 'Mac-mini')}{C.RESET}")

        # Build right column lines
        right = []
        right.append(f"{ACCENT}{C.BOLD}System Info{C.RESET}")
        right.append(f"{DIM_COLOR}{dyn.get('os_ver', 'macOS')} · {dyn.get('cpu', 'ARM')}{C.RESET}")
        right.append(f"{DIM_COLOR}Memory: {dyn.get('memory', '?')} · Disk: {dyn.get('disk', '?')}{C.RESET}")
        right.append("")
        right.append(f"{SYSTEM_CLR}{C.BOLD}Infrastructure{C.RESET}")
        right.append(f"{DIM_COLOR}GPU Balancer: {self.model_count} models{C.RESET}")
        if dyn.get("gpu_temp"):
            right.append(f"{DIM_COLOR}GPU Temp: {dyn['gpu_temp']}{C.RESET}")
        if dyn["learner_cycles"] > 0:
            right.append(f"{SKILL_CLR}InfraLearner: {dyn['learner_cycles']} cycles{C.RESET}")
        else:
            right.append(f"{DIM_COLOR}InfraLearner: idle{C.RESET}")
        if dyn["anomaly_count"] > 0:
            right.append(f"{WARN_CLR}\u26a0 {dyn['anomaly_count']} anomalies (24h){C.RESET}")
        else:
            right.append(f"{SYSTEM_CLR}\u2713 No anomalies (24h){C.RESET}")
        right.append("")
        right.append(f"{ACCENT2}{C.BOLD}Recent activity{C.RESET}")
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE) as f:
                    hist = [l.strip() for l in f.readlines() if l.strip()][-3:]
                if hist:
                    for h in hist:
                        right.append(f"{DIM_COLOR}\u203a {h[:right_w-4]}{C.RESET}")
                else:
                    right.append(f"{DIM_COLOR}No recent activity{C.RESET}")
            else:
                right.append(f"{DIM_COLOR}No recent activity{C.RESET}")
        except Exception:
            right.append(f"{DIM_COLOR}No recent activity{C.RESET}")

        # Pad columns to same length
        max_lines = max(len(left), len(right))
        while len(left) < max_lines:
            left.append("")
        while len(right) < max_lines:
            right.append("")

        # Draw top border
        print(f"{BORDER_CLR}\u250c{hbar * left_w}\u252c{hbar * right_w}\u2510{C.RESET}")

        # Draw rows
        for i in range(max_lines):
            l_str = pad_to(left[i], left_w - 2)
            r_str = pad_to(right[i], right_w - 2)
            print(f"{BORDER_CLR}\u2502{C.RESET} {l_str} {BORDER_CLR}\u2502{C.RESET} {r_str} {BORDER_CLR}\u2502{C.RESET}")

        # Draw bottom border
        print(f"{BORDER_CLR}\u2514{hbar * left_w}\u2534{hbar * right_w}\u2518{C.RESET}")
        print()

    def show_status(self):
        """Show connection status line with dynamic data."""
        networks = self.scanner.get_local_networks()
        net_str = ", ".join(f"{ip}/24" for ip in networks[:2]) if networks else "unknown"

        # Status badges
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
        self.check_connections()  # Check BEFORE banner so model_count is populated
        self.show_banner()
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
                # v5.0.0: In streaming mode, response was already printed live.
                # Only use TypewriterEffect for non-streaming mode.
                if not self.streaming_enabled:
                    formatted = self.formatter.format(response)
                    print()  # Blank line before response
                    TypewriterEffect.print(formatted)
                    print(C.RESET, end="")
                else:
                    # Streaming already printed the raw response;
                    # just ensure color reset
                    print(C.RESET, end="")

                # Show metadata footer (Claude Code style)
                model_str = self.current_model or "?"
                if ":" in model_str:
                    model_str = model_str.split(":")[0]
                expert_str = self.current_expert or "general"
                print(f"\n  {DIM_COLOR}⟨{expert_str} → {model_str} · {elapsed:.1f}s⟩{C.RESET}")

                # Signal InfraLearner it can resume
                self.learner.signal_user_idle()

                # Update conversation (store CLEANED response to prevent token leak propagation)
                clean_response = self.cleaner.clean(response)
                self.conversation.append({"role": "user", "content": user_input})
                self.conversation.append({"role": "assistant", "content": clean_response[:2000]})

                # Keep conversation manageable
                if len(self.conversation) > 20:
                    self.conversation = self.conversation[-12:]

            except KeyboardInterrupt:
                print(f"\n  {DIM_COLOR}(Ctrl+C to exit, /quit to quit){C.RESET}")
                continue
            except EOFError:
                break

        # Cleanup
        self.learner.signal_user_idle()
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
