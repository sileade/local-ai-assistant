#!/usr/bin/env python3
"""
SCLG InfraLearner v1.0.0
═══════════════════════════════════════════════════════════════
Background self-learning agent that continuously analyzes
Grafana/Prometheus/Loki data, builds infrastructure knowledge base,
and yields resources to priority user requests.

Architecture:
  ┌─────────────────────────────────────────────────┐
  │              InfraLearner Daemon                 │
  │                                                  │
  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
  │  │ Collector │→ │ Analyzer │→ │ KnowledgeBase │  │
  │  │ (Grafana) │  │ (AI/ML)  │  │ (JSON store) │  │
  │  └──────────┘  └──────────┘  └──────────────┘  │
  │       ↑                            ↓            │
  │  ┌──────────┐              ┌──────────────┐    │
  │  │ Scheduler│              │ Query Engine │    │
  │  │ (cron)   │              │ (for sclg-ai)│    │
  │  └──────────┘              └──────────────┘    │
  │                                                  │
  │  Priority: USER_REQUEST > LEARNING > IDLE        │
  └─────────────────────────────────────────────────┘

Usage:
  sclg-infra-learner                    # Run as daemon
  sclg-infra-learner --once             # Single learning cycle
  sclg-infra-learner --query "GPU temp" # Query knowledge base
  sclg-infra-learner --status           # Show learning status
  sclg-infra-learner --version          # Show version
"""

import os
import sys
import json
import time
import signal
import hashlib
import logging
import threading
import traceback
import base64
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field, asdict
from collections import defaultdict

try:
    import urllib.request
    import urllib.error
    import urllib.parse
except ImportError:
    pass

VERSION = "1.0.0"

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Grafana
GRAFANA_URL = os.environ.get("GRAFANA_URL", "https://grafana.sclg.io")
GRAFANA_TOKEN = os.environ.get("GRAFANA_TOKEN", "")
GRAFANA_USER = "admin"
GRAFANA_PASS = os.environ.get("GRAFANA_PASS", "")

# Prometheus (direct access via bastion → alpine-grafana)
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://10.0.0.201:9090")

# Loki
LOKI_URL = os.environ.get("LOKI_URL", "http://10.0.0.200:3100")

# AI for analysis
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://172.27.4.1:11434")
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Learning schedule
LEARN_INTERVAL_IDLE = 300       # 5 min when idle
LEARN_INTERVAL_ACTIVE = 900     # 15 min when user is active
DEEP_LEARN_INTERVAL = 3600      # 1 hour for deep analysis
ANOMALY_CHECK_INTERVAL = 120    # 2 min for anomaly detection

# Data storage
DATA_DIR = Path.home() / ".sclg-ai" / "knowledge"
METRICS_DIR = DATA_DIR / "metrics"
ANOMALIES_DIR = DATA_DIR / "anomalies"
BASELINES_DIR = DATA_DIR / "baselines"
INSIGHTS_DIR = DATA_DIR / "insights"
LOGS_DIR = DATA_DIR / "logs"

# Priority system
PRIORITY_FILE = DATA_DIR / "priority.lock"

# Logging
LOG_FILE = DATA_DIR / "learner.log"

# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

class LearnerState(Enum):
    IDLE = "idle"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    LEARNING = "learning"
    PAUSED = "paused"          # Paused for user request
    DEEP_ANALYSIS = "deep_analysis"

@dataclass
class MetricBaseline:
    """Normal range for a metric"""
    name: str
    labels: Dict[str, str]
    min_val: float
    max_val: float
    avg_val: float
    stddev: float
    samples: int
    last_updated: str
    
@dataclass
class Anomaly:
    """Detected anomaly"""
    timestamp: str
    metric: str
    value: float
    expected_range: Tuple[float, float]
    severity: str  # info, warning, critical
    description: str
    resolved: bool = False

@dataclass
class InfraInsight:
    """Learned insight about infrastructure"""
    category: str  # network, gpu, storage, service, security
    title: str
    description: str
    confidence: float  # 0.0 - 1.0
    evidence: List[str]
    learned_at: str
    useful_count: int = 0

@dataclass
class LearnerStats:
    """Learning statistics"""
    total_cycles: int = 0
    total_metrics_collected: int = 0
    total_anomalies_detected: int = 0
    total_insights_generated: int = 0
    total_queries_answered: int = 0
    uptime_seconds: float = 0
    last_cycle: str = ""
    state: str = "idle"

# ═══════════════════════════════════════════════════════════════
# GRAFANA/PROMETHEUS DATA COLLECTOR
# ═══════════════════════════════════════════════════════════════

class DataCollector:
    """Collects metrics from Grafana API, Prometheus, and Loki"""
    
    def __init__(self):
        self.logger = logging.getLogger("collector")
        # Use service account token for Grafana API
        self.grafana_headers = {
            "Authorization": f"Bearer {GRAFANA_TOKEN}",
            "Content-Type": "application/json"
        }
        # Basic auth fallback
        auth_str = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASS}".encode()).decode()
        self.grafana_basic_headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json"
        }
    
    def _grafana_request(self, endpoint: str, method: str = "GET", data: dict = None) -> Optional[dict]:
        """Make authenticated Grafana API request"""
        url = f"{GRAFANA_URL}/api/{endpoint}"
        try:
            body = json.dumps(data).encode() if data else None
            req = urllib.request.Request(url, data=body, headers=self.grafana_headers, method=method)
            # Disable SSL verification for internal certs
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            resp = urllib.request.urlopen(req, timeout=30, context=ctx)
            return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 401:
                # Try basic auth
                try:
                    req2 = urllib.request.Request(url, data=body, headers=self.grafana_basic_headers, method=method)
                    resp2 = urllib.request.urlopen(req2, timeout=30, context=ctx)
                    return json.loads(resp2.read().decode())
                except Exception:
                    pass
            self.logger.warning(f"Grafana API error {e.code}: {endpoint}")
            return None
        except Exception as e:
            self.logger.warning(f"Grafana request failed: {e}")
            return None
    
    def _prometheus_query(self, query: str) -> Optional[dict]:
        """Query Prometheus via Grafana proxy"""
        # Use Grafana's Prometheus datasource proxy
        endpoint = f"datasources/proxy/uid/efdhopzhssvswb/api/v1/query"
        params = urllib.parse.urlencode({"query": query})
        return self._grafana_request(f"{endpoint}?{params}")
    
    def _prometheus_query_range(self, query: str, start: str, end: str, step: str = "60s") -> Optional[dict]:
        """Query Prometheus range via Grafana proxy"""
        endpoint = f"datasources/proxy/uid/efdhopzhssvswb/api/v1/query_range"
        params = urllib.parse.urlencode({
            "query": query,
            "start": start,
            "end": end,
            "step": step
        })
        return self._grafana_request(f"{endpoint}?{params}")
    
    def get_dashboards(self) -> List[dict]:
        """Get all Grafana dashboards"""
        result = self._grafana_request("search?type=dash-db")
        return result if isinstance(result, list) else []
    
    def get_dashboard_detail(self, uid: str) -> Optional[dict]:
        """Get dashboard details by UID"""
        return self._grafana_request(f"dashboards/uid/{uid}")
    
    def get_alerts(self) -> List[dict]:
        """Get current alert states"""
        result = self._grafana_request("alertmanager/grafana/api/v2/alerts")
        return result if isinstance(result, list) else []
    
    def get_alert_rules(self) -> Optional[dict]:
        """Get all alert rules"""
        return self._grafana_request("ruler/grafana/api/v1/rules")
    
    def get_annotations(self, hours: int = 24) -> List[dict]:
        """Get recent annotations"""
        now = int(time.time() * 1000)
        from_ts = now - (hours * 3600 * 1000)
        result = self._grafana_request(f"annotations?from={from_ts}&to={now}&limit=100")
        return result if isinstance(result, list) else []
    
    def get_datasources(self) -> List[dict]:
        """Get all datasources"""
        result = self._grafana_request("datasources")
        return result if isinstance(result, list) else []
    
    # ── Key Metrics Collection ──
    
    def collect_ai_server_metrics(self) -> Dict[str, Any]:
        """Collect AI server metrics"""
        metrics = {}
        queries = {
            "gpu_temp": 'ai_gpu_temperature_celsius{exported_host="172.27.5.114"}',
            "gpu_util": 'ai_gpu_utilization_percent{exported_host="172.27.5.114"}',
            "gpu_vram_used": 'ai_gpu_memory_used_bytes{exported_host="172.27.5.114"}',
            "gpu_vram_total": 'ai_gpu_memory_total_bytes{exported_host="172.27.5.114"}',
            "gpu_power": 'ai_gpu_power_draw_watts{exported_host="172.27.5.114"}',
            "ollama_up": 'ai_ollama_up{exported_host="172.27.5.114"}',
            "ollama_models": 'ai_ollama_models_count{exported_host="172.27.5.114"}',
            "ollama_running": 'ai_ollama_running_models{exported_host="172.27.5.114"}',
            "server_up": 'ai_server_up{exported_host="172.27.5.114"}',
            "cpu_temp": 'ai_system_cpu_temperature_celsius{exported_host="172.27.5.114"}',
            "mem_used": 'ai_system_mem_used_bytes{exported_host="172.27.5.114"}',
            "mem_total": 'ai_system_mem_total_bytes{exported_host="172.27.5.114"}',
            "load_1m": 'ai_system_load_1m{exported_host="172.27.5.114"}',
            "disk_used": 'ai_system_disk_used_bytes{exported_host="172.27.5.114"}',
            "disk_total": 'ai_system_disk_total_bytes{exported_host="172.27.5.114"}',
        }
        for name, query in queries.items():
            result = self._prometheus_query(query)
            if result and result.get("data", {}).get("result"):
                for r in result["data"]["result"]:
                    key = name
                    if r.get("metric", {}).get("gpu_id"):
                        key = f"{name}_gpu{r['metric']['gpu_id']}"
                    metrics[key] = float(r["value"][1])
        return metrics
    
    def collect_network_metrics(self) -> Dict[str, Any]:
        """Collect MikroTik network metrics"""
        metrics = {}
        queries = {
            "router_cpu": 'mktxp_system_cpu_load',
            "router_memory": 'mktxp_system_free_memory',
            "router_uptime": 'mktxp_system_uptime',
        }
        for name, query in queries.items():
            result = self._prometheus_query(query)
            if result and result.get("data", {}).get("result"):
                for r in result["data"]["result"]:
                    host = r.get("metric", {}).get("address", "unknown")
                    metrics[f"{name}_{host}"] = float(r["value"][1])
        return metrics
    
    def collect_cctv_metrics(self) -> Dict[str, Any]:
        """Collect Hikvision CCTV metrics"""
        metrics = {}
        queries = {
            "nvr_up": 'hikvision_nvr_up',
            "cameras_online": 'hikvision_channel_online',
            "hdd_status": 'hikvision_hdd_status',
            "hdd_free": 'hikvision_hdd_free_bytes',
        }
        for name, query in queries.items():
            result = self._prometheus_query(query)
            if result and result.get("data", {}).get("result"):
                for r in result["data"]["result"]:
                    alias = r.get("metric", {}).get("alias", "unknown")
                    channel = r.get("metric", {}).get("channel_name", "")
                    key = f"{name}_{alias}"
                    if channel:
                        key += f"_{channel}"
                    metrics[key] = float(r["value"][1])
        return metrics
    
    def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect node_exporter system metrics for monitoring server"""
        metrics = {}
        queries = {
            "cpu_usage": '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            "mem_available": 'node_memory_MemAvailable_bytes',
            "mem_total": 'node_memory_MemTotal_bytes',
            "disk_avail_root": 'node_filesystem_avail_bytes{mountpoint="/"}',
            "load_1m": 'node_load1',
        }
        for name, query in queries.items():
            result = self._prometheus_query(query)
            if result and result.get("data", {}).get("result"):
                metrics[name] = float(result["data"]["result"][0]["value"][1])
        return metrics
    
    def collect_all(self) -> Dict[str, Dict[str, Any]]:
        """Collect all metrics"""
        self.logger.info("Collecting all metrics...")
        data = {
            "timestamp": datetime.now().isoformat(),
            "ai_server": self.collect_ai_server_metrics(),
            "network": self.collect_network_metrics(),
            "cctv": self.collect_cctv_metrics(),
            "system": self.collect_system_metrics(),
            "alerts": self.get_alerts(),
            "annotations": self.get_annotations(hours=1),
        }
        total = sum(len(v) for v in data.values() if isinstance(v, dict))
        self.logger.info(f"Collected {total} metric values")
        return data


# ═══════════════════════════════════════════════════════════════
# KNOWLEDGE BASE
# ═══════════════════════════════════════════════════════════════

class KnowledgeBase:
    """Persistent knowledge base about infrastructure"""
    
    def __init__(self):
        self.logger = logging.getLogger("knowledge")
        self.baselines: Dict[str, MetricBaseline] = {}
        self.anomalies: List[Anomaly] = []
        self.insights: List[InfraInsight] = []
        self.metric_history: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        self._load()
    
    def _load(self):
        """Load knowledge from disk"""
        # Load baselines
        baselines_file = BASELINES_DIR / "baselines.json"
        if baselines_file.exists():
            try:
                data = json.loads(baselines_file.read_text())
                for k, v in data.items():
                    self.baselines[k] = MetricBaseline(**v)
                self.logger.info(f"Loaded {len(self.baselines)} baselines")
            except Exception as e:
                self.logger.warning(f"Failed to load baselines: {e}")
        
        # Load insights
        insights_file = INSIGHTS_DIR / "insights.json"
        if insights_file.exists():
            try:
                data = json.loads(insights_file.read_text())
                self.insights = [InfraInsight(**i) for i in data]
                self.logger.info(f"Loaded {len(self.insights)} insights")
            except Exception as e:
                self.logger.warning(f"Failed to load insights: {e}")
        
        # Load recent anomalies
        anomalies_file = ANOMALIES_DIR / "recent.json"
        if anomalies_file.exists():
            try:
                data = json.loads(anomalies_file.read_text())
                self.anomalies = [Anomaly(**a) for a in data[-500:]]  # Keep last 500
            except Exception as e:
                self.logger.warning(f"Failed to load anomalies: {e}")
    
    def save(self):
        """Save knowledge to disk"""
        # Save baselines
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        baselines_file = BASELINES_DIR / "baselines.json"
        baselines_data = {k: asdict(v) for k, v in self.baselines.items()}
        baselines_file.write_text(json.dumps(baselines_data, indent=2, ensure_ascii=False))
        
        # Save insights
        INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        insights_file = INSIGHTS_DIR / "insights.json"
        insights_file.write_text(json.dumps([asdict(i) for i in self.insights], indent=2, ensure_ascii=False))
        
        # Save anomalies
        ANOMALIES_DIR.mkdir(parents=True, exist_ok=True)
        anomalies_file = ANOMALIES_DIR / "recent.json"
        anomalies_file.write_text(json.dumps([asdict(a) for a in self.anomalies[-500:]], indent=2, ensure_ascii=False))
    
    def update_baseline(self, name: str, value: float, labels: Dict[str, str] = None):
        """Update metric baseline with new value"""
        if name in self.baselines:
            b = self.baselines[name]
            # Exponential moving average
            n = min(b.samples + 1, 1000)
            alpha = 2.0 / (n + 1)
            new_avg = b.avg_val * (1 - alpha) + value * alpha
            # Update stddev estimate
            diff = value - new_avg
            new_stddev = (b.stddev * (1 - alpha) + abs(diff) * alpha) if b.stddev > 0 else abs(diff)
            
            b.avg_val = new_avg
            b.stddev = max(new_stddev, 0.001)
            b.min_val = min(b.min_val, value)
            b.max_val = max(b.max_val, value)
            b.samples = n
            b.last_updated = datetime.now().isoformat()
        else:
            self.baselines[name] = MetricBaseline(
                name=name,
                labels=labels or {},
                min_val=value,
                max_val=value,
                avg_val=value,
                stddev=0.001,
                samples=1,
                last_updated=datetime.now().isoformat()
            )
    
    def check_anomaly(self, name: str, value: float) -> Optional[Anomaly]:
        """Check if value is anomalous compared to baseline"""
        if name not in self.baselines or self.baselines[name].samples < 10:
            return None
        
        b = self.baselines[name]
        # Z-score based anomaly detection
        z_score = abs(value - b.avg_val) / max(b.stddev, 0.001)
        
        if z_score > 4.0:
            severity = "critical"
        elif z_score > 3.0:
            severity = "warning"
        elif z_score > 2.5:
            severity = "info"
        else:
            return None
        
        anomaly = Anomaly(
            timestamp=datetime.now().isoformat(),
            metric=name,
            value=value,
            expected_range=(b.avg_val - 2*b.stddev, b.avg_val + 2*b.stddev),
            severity=severity,
            description=f"{name}={value:.2f} (expected {b.avg_val:.2f} +/- {2*b.stddev:.2f}, z={z_score:.1f})"
        )
        self.anomalies.append(anomaly)
        return anomaly
    
    def add_insight(self, category: str, title: str, description: str, 
                    confidence: float, evidence: List[str]):
        """Add a new insight"""
        # Check for duplicate
        for existing in self.insights:
            if existing.title == title:
                existing.confidence = max(existing.confidence, confidence)
                existing.evidence.extend(evidence)
                existing.evidence = existing.evidence[-10:]  # Keep last 10
                return
        
        insight = InfraInsight(
            category=category,
            title=title,
            description=description,
            confidence=confidence,
            evidence=evidence,
            learned_at=datetime.now().isoformat()
        )
        self.insights.append(insight)
        # Keep max 1000 insights
        if len(self.insights) > 1000:
            # Remove lowest confidence
            self.insights.sort(key=lambda x: x.confidence, reverse=True)
            self.insights = self.insights[:1000]
    
    def query(self, question: str) -> List[InfraInsight]:
        """Query knowledge base for relevant insights"""
        question_lower = question.lower()
        keywords = set(question_lower.split())
        
        scored = []
        for insight in self.insights:
            score = 0
            text = f"{insight.title} {insight.description} {insight.category}".lower()
            for kw in keywords:
                if kw in text:
                    score += 1
            if score > 0:
                scored.append((score, insight))
        
        scored.sort(key=lambda x: (-x[0], -x[1].confidence))
        return [s[1] for s in scored[:10]]
    
    def get_baseline_summary(self) -> str:
        """Get human-readable baseline summary"""
        if not self.baselines:
            return "No baselines established yet."
        
        lines = ["Infrastructure Baselines:"]
        categories = defaultdict(list)
        for name, b in self.baselines.items():
            cat = name.split("_")[0] if "_" in name else "other"
            categories[cat].append(b)
        
        for cat, baselines in sorted(categories.items()):
            lines.append(f"\n  {cat.upper()}:")
            for b in baselines[:5]:
                lines.append(f"    {b.name}: avg={b.avg_val:.2f} range=[{b.min_val:.2f}, {b.max_val:.2f}] ({b.samples} samples)")
        
        return "\n".join(lines)
    
    def get_anomaly_summary(self, hours: int = 24) -> str:
        """Get recent anomalies summary"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        recent = [a for a in self.anomalies if a.timestamp > cutoff]
        
        if not recent:
            return f"No anomalies in the last {hours} hours."
        
        critical = [a for a in recent if a.severity == "critical"]
        warning = [a for a in recent if a.severity == "warning"]
        info = [a for a in recent if a.severity == "info"]
        
        lines = [f"Anomalies (last {hours}h): {len(critical)} critical, {len(warning)} warning, {len(info)} info"]
        for a in critical + warning[:5]:
            lines.append(f"  [{a.severity.upper()}] {a.description}")
        
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# AI ANALYZER
# ═══════════════════════════════════════════════════════════════

class AIAnalyzer:
    """Uses AI to analyze metrics and generate insights"""
    
    def __init__(self):
        self.logger = logging.getLogger("analyzer")
    
    def _call_ollama(self, prompt: str, model: str = "qwen2.5:7b") -> Optional[str]:
        """Call Ollama for analysis"""
        try:
            data = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 500}
            }).encode()
            req = urllib.request.Request(
                f"{OLLAMA_HOST}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            resp = urllib.request.urlopen(req, timeout=120)
            result = json.loads(resp.read().decode())
            return result.get("response", "")
        except Exception as e:
            self.logger.debug(f"Ollama failed: {e}")
            return None
    
    def _call_claude(self, prompt: str) -> Optional[str]:
        """Call Claude API for deep analysis"""
        if not CLAUDE_API_KEY:
            return None
        try:
            data = json.dumps({
                "model": CLAUDE_MODEL,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01"
                }
            )
            resp = urllib.request.urlopen(req, timeout=60)
            result = json.loads(resp.read().decode())
            if result.get("content"):
                return result["content"][0].get("text", "")
            return None
        except Exception as e:
            self.logger.debug(f"Claude failed: {e}")
            return None
    
    def analyze_metrics(self, data: Dict, kb: KnowledgeBase) -> List[Dict]:
        """Analyze collected metrics and generate insights"""
        insights = []
        
        # 1. Update baselines and check anomalies
        for category, metrics in data.items():
            if not isinstance(metrics, dict):
                continue
            for name, value in metrics.items():
                if isinstance(value, (int, float)):
                    full_name = f"{category}_{name}"
                    kb.update_baseline(full_name, value)
                    anomaly = kb.check_anomaly(full_name, value)
                    if anomaly:
                        insights.append({
                            "type": "anomaly",
                            "severity": anomaly.severity,
                            "metric": full_name,
                            "value": value,
                            "description": anomaly.description
                        })
        
        # 2. Pattern detection (no AI needed)
        ai_metrics = data.get("ai_server", {})
        
        # GPU temperature check
        for key, val in ai_metrics.items():
            if "gpu_temp" in key and isinstance(val, (int, float)):
                if val > 85:
                    kb.add_insight("gpu", "GPU overheating risk",
                        f"GPU temperature {val}C exceeds safe threshold (85C)",
                        0.9, [f"{key}={val}C at {data.get('timestamp', 'now')}"])
                elif val > 75:
                    kb.add_insight("gpu", "GPU temperature elevated",
                        f"GPU temperature {val}C is elevated but within limits",
                        0.6, [f"{key}={val}C"])
        
        # VRAM usage check
        for key, val in ai_metrics.items():
            if "gpu_vram_used" in key and isinstance(val, (int, float)):
                total_key = key.replace("vram_used", "vram_total")
                total = ai_metrics.get(total_key, 0)
                if total > 0:
                    pct = (val / total) * 100
                    if pct > 90:
                        kb.add_insight("gpu", "VRAM nearly full",
                            f"GPU VRAM usage {pct:.0f}% — may cause OOM errors",
                            0.8, [f"{key}: {val/(1024**3):.1f}GB / {total/(1024**3):.1f}GB"])
        
        # Ollama status
        if ai_metrics.get("ollama_up", 0) == 0:
            kb.add_insight("service", "Ollama service down",
                "Ollama API is not responding on AI server",
                0.95, [f"ollama_up=0 at {data.get('timestamp', 'now')}"])
        
        # Disk usage
        disk_used = ai_metrics.get("disk_used", 0)
        disk_total = ai_metrics.get("disk_total", 0)
        if disk_total > 0:
            pct = (disk_used / disk_total) * 100
            if pct > 90:
                kb.add_insight("storage", "AI server disk nearly full",
                    f"Disk usage {pct:.0f}% on AI server — models may fail to download",
                    0.85, [f"disk: {disk_used/(1024**3):.0f}GB / {disk_total/(1024**3):.0f}GB"])
        
        # CCTV checks
        cctv = data.get("cctv", {})
        offline_cameras = [k for k, v in cctv.items() if "cameras_online" in k and v == 0]
        if offline_cameras:
            kb.add_insight("cctv", f"{len(offline_cameras)} cameras offline",
                f"Offline cameras: {', '.join(offline_cameras[:5])}",
                0.9, offline_cameras[:10])
        
        # Alert analysis
        alerts = data.get("alerts", [])
        if isinstance(alerts, list):
            firing = [a for a in alerts if a.get("status", {}).get("state") == "active"]
            if firing:
                for alert in firing[:5]:
                    labels = alert.get("labels", {})
                    kb.add_insight("alert", f"Active alert: {labels.get('alertname', 'unknown')}",
                        f"Alert firing: {labels}",
                        0.95, [json.dumps(labels)])
        
        return insights
    
    def deep_analyze(self, kb: KnowledgeBase, data: Dict) -> Optional[str]:
        """Deep AI analysis of current state (uses Ollama or Claude)"""
        # Build context
        baseline_summary = kb.get_baseline_summary()
        anomaly_summary = kb.get_anomaly_summary(hours=6)
        
        # Summarize current metrics
        current = []
        for cat, metrics in data.items():
            if isinstance(metrics, dict) and metrics:
                current.append(f"\n{cat}:")
                for k, v in list(metrics.items())[:10]:
                    if isinstance(v, (int, float)):
                        current.append(f"  {k}: {v}")
        
        prompt = f"""Analyze this infrastructure monitoring data and provide insights.
Focus on: anomalies, trends, potential issues, optimization opportunities.

{baseline_summary}

{anomaly_summary}

Current metrics:
{''.join(current[:50])}

Active alerts: {len(data.get('alerts', []))} alerts

Provide 3-5 concise insights in format:
[CATEGORY] Title: Description (confidence: X%)
Categories: gpu, network, storage, service, security, performance"""
        
        # Try Ollama first (free), then Claude
        result = self._call_ollama(prompt)
        if not result:
            result = self._call_claude(prompt)
        
        if result:
            # Parse insights from AI response
            for line in result.split("\n"):
                line = line.strip()
                if line.startswith("[") and "]" in line:
                    try:
                        cat = line[1:line.index("]")].lower()
                        rest = line[line.index("]")+1:].strip()
                        if ":" in rest:
                            title, desc = rest.split(":", 1)
                            conf_match = re.search(r'(\d+)%', desc)
                            confidence = int(conf_match.group(1)) / 100 if conf_match else 0.5
                            kb.add_insight(cat, title.strip(), desc.strip(), confidence, ["ai_analysis"])
                    except Exception:
                        pass
        
        return result


# ═══════════════════════════════════════════════════════════════
# PRIORITY MANAGER
# ═══════════════════════════════════════════════════════════════

class PriorityManager:
    """Manages priority between learning and user requests"""
    
    def __init__(self):
        self.logger = logging.getLogger("priority")
        self._user_active = False
        self._pause_until = 0
    
    def user_request_start(self):
        """Signal that user request is being processed"""
        self._user_active = True
        self._pause_until = time.time() + 30  # Pause learning for 30s after request
        PRIORITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        PRIORITY_FILE.write_text(json.dumps({
            "user_active": True,
            "since": datetime.now().isoformat()
        }))
        self.logger.info("User request — pausing learning")
    
    def user_request_end(self):
        """Signal that user request is done"""
        self._user_active = False
        self._pause_until = time.time() + 10  # Cool down 10s
        if PRIORITY_FILE.exists():
            PRIORITY_FILE.unlink()
    
    def should_learn(self) -> bool:
        """Check if learning should proceed"""
        if self._user_active:
            return False
        if time.time() < self._pause_until:
            return False
        # Check external priority file (from sclg-ai)
        if PRIORITY_FILE.exists():
            try:
                data = json.loads(PRIORITY_FILE.read_text())
                if data.get("user_active"):
                    return False
            except Exception:
                pass
        return True
    
    def get_interval(self) -> int:
        """Get current learning interval based on activity"""
        if self._user_active:
            return LEARN_INTERVAL_ACTIVE
        return LEARN_INTERVAL_IDLE


# ═══════════════════════════════════════════════════════════════
# INFRA LEARNER DAEMON
# ═══════════════════════════════════════════════════════════════

class InfraLearner:
    """Main learning daemon"""
    
    def __init__(self):
        self.collector = DataCollector()
        self.kb = KnowledgeBase()
        self.analyzer = AIAnalyzer()
        self.priority = PriorityManager()
        self.stats = LearnerStats()
        self.state = LearnerState.IDLE
        self._running = True
        self._last_deep = 0
        self.logger = logging.getLogger("learner")
        
        # Load stats
        stats_file = DATA_DIR / "stats.json"
        if stats_file.exists():
            try:
                data = json.loads(stats_file.read_text())
                self.stats = LearnerStats(**data)
            except Exception:
                pass
    
    def _save_stats(self):
        """Save learning stats"""
        self.stats.state = self.state.value
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        stats_file = DATA_DIR / "stats.json"
        stats_file.write_text(json.dumps(asdict(self.stats), indent=2))
    
    def learning_cycle(self) -> Dict:
        """Run one learning cycle"""
        self.state = LearnerState.COLLECTING
        self.logger.info("Starting learning cycle...")
        
        # 1. Collect data
        data = self.collector.collect_all()
        metric_count = sum(len(v) for v in data.values() if isinstance(v, dict))
        self.stats.total_metrics_collected += metric_count
        
        if not self.priority.should_learn():
            self.logger.info("User active — skipping analysis")
            self.state = LearnerState.PAUSED
            return {"status": "paused", "metrics": metric_count}
        
        # 2. Analyze
        self.state = LearnerState.ANALYZING
        insights = self.analyzer.analyze_metrics(data, self.kb)
        anomaly_count = len([i for i in insights if i["type"] == "anomaly"])
        self.stats.total_anomalies_detected += anomaly_count
        
        # 3. Deep analysis (hourly)
        deep_result = None
        if time.time() - self._last_deep > DEEP_LEARN_INTERVAL and self.priority.should_learn():
            self.state = LearnerState.DEEP_ANALYSIS
            self.logger.info("Running deep analysis...")
            deep_result = self.analyzer.deep_analyze(self.kb, data)
            self._last_deep = time.time()
        
        # 4. Save
        self.state = LearnerState.LEARNING
        self.kb.save()
        
        # Save raw data snapshot
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_file = METRICS_DIR / f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        # Keep only last 288 snapshots (24h at 5min intervals)
        existing = sorted(METRICS_DIR.glob("snapshot_*.json"))
        for old in existing[:-288]:
            old.unlink()
        snapshot_file.write_text(json.dumps(data, indent=2, default=str))
        
        # Update stats
        self.stats.total_cycles += 1
        self.stats.last_cycle = datetime.now().isoformat()
        self.stats.total_insights_generated = len(self.kb.insights)
        self._save_stats()
        
        self.state = LearnerState.IDLE
        self.logger.info(f"Cycle complete: {metric_count} metrics, {anomaly_count} anomalies, {len(self.kb.insights)} total insights")
        
        return {
            "status": "complete",
            "metrics": metric_count,
            "anomalies": anomaly_count,
            "insights": len(insights),
            "deep_analysis": deep_result is not None
        }
    
    def query(self, question: str) -> str:
        """Query the knowledge base"""
        self.priority.user_request_start()
        try:
            insights = self.kb.query(question)
            if not insights:
                return "No relevant knowledge found yet. The learner needs more time to build the knowledge base."
            
            lines = [f"Found {len(insights)} relevant insights:\n"]
            for i, insight in enumerate(insights, 1):
                lines.append(f"{i}. [{insight.category.upper()}] {insight.title}")
                lines.append(f"   {insight.description}")
                lines.append(f"   Confidence: {insight.confidence:.0%} | Learned: {insight.learned_at[:16]}")
                lines.append("")
            
            self.stats.total_queries_answered += 1
            self._save_stats()
            return "\n".join(lines)
        finally:
            self.priority.user_request_end()
    
    def get_status(self) -> str:
        """Get learner status"""
        lines = [
            f"SCLG InfraLearner v{VERSION}",
            f"State: {self.state.value}",
            f"Cycles: {self.stats.total_cycles}",
            f"Metrics collected: {self.stats.total_metrics_collected}",
            f"Anomalies detected: {self.stats.total_anomalies_detected}",
            f"Insights: {self.stats.total_insights_generated}",
            f"Queries answered: {self.stats.total_queries_answered}",
            f"Last cycle: {self.stats.last_cycle or 'never'}",
            f"Baselines: {len(self.kb.baselines)}",
            "",
            self.kb.get_anomaly_summary(hours=6),
        ]
        return "\n".join(lines)
    
    def run_daemon(self):
        """Run as background daemon"""
        self.logger.info(f"InfraLearner v{VERSION} starting as daemon...")
        
        # Create dirs
        for d in [DATA_DIR, METRICS_DIR, ANOMALIES_DIR, BASELINES_DIR, INSIGHTS_DIR, LOGS_DIR]:
            d.mkdir(parents=True, exist_ok=True)
        
        def signal_handler(sig, frame):
            self.logger.info("Shutting down...")
            self._running = False
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        start_time = time.time()
        
        while self._running:
            try:
                if self.priority.should_learn():
                    result = self.learning_cycle()
                    self.logger.info(f"Cycle result: {result}")
                else:
                    self.logger.debug("Waiting (user active)...")
                
                self.stats.uptime_seconds = time.time() - start_time
                self._save_stats()
                
                # Sleep with interruptibility
                interval = self.priority.get_interval()
                for _ in range(interval):
                    if not self._running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Cycle error: {e}")
                self.logger.debug(traceback.format_exc())
                time.sleep(60)  # Wait a minute on error
        
        self.kb.save()
        self._save_stats()
        self.logger.info("InfraLearner stopped.")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def setup_logging():
    """Setup logging"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(LOG_FILE), encoding="utf-8")
        ]
    )

def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--version":
            print(f"sclg-infra-learner v{VERSION}")
            return
        
        if arg == "--status":
            setup_logging()
            learner = InfraLearner()
            print(learner.get_status())
            return
        
        if arg == "--once":
            setup_logging()
            learner = InfraLearner()
            result = learner.learning_cycle()
            print(json.dumps(result, indent=2))
            return
        
        if arg == "--query" and len(sys.argv) > 2:
            setup_logging()
            learner = InfraLearner()
            question = " ".join(sys.argv[2:])
            print(learner.query(question))
            return
        
        if arg == "--baselines":
            setup_logging()
            learner = InfraLearner()
            print(learner.kb.get_baseline_summary())
            return
        
        if arg == "--anomalies":
            hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
            setup_logging()
            learner = InfraLearner()
            print(learner.kb.get_anomaly_summary(hours=hours))
            return
        
        print(f"Unknown argument: {arg}")
        print("Usage:")
        print("  sclg-infra-learner              # Run as daemon")
        print("  sclg-infra-learner --once        # Single cycle")
        print("  sclg-infra-learner --query TEXT   # Query knowledge")
        print("  sclg-infra-learner --status       # Show status")
        print("  sclg-infra-learner --baselines    # Show baselines")
        print("  sclg-infra-learner --anomalies [hours]  # Show anomalies")
        print("  sclg-infra-learner --version      # Show version")
        return
    
    # Default: run as daemon
    setup_logging()
    learner = InfraLearner()
    learner.run_daemon()

if __name__ == "__main__":
    main()
