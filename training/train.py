#!/usr/bin/env python3
"""
SCLG-AI Training Pipeline v1.0
Full cycle: collect → merge → filter → export → create → test

Usage:
    python3 train.py stats              # Show training data statistics
    python3 train.py merge              # Merge golden dataset into training
    python3 train.py export [expert]    # Export Modelfile for expert
    python3 train.py create [expert]    # Create model on Ollama (local)
    python3 train.py deploy [node]      # Deploy model to remote node
    python3 train.py test               # Run model understanding tests
    python3 train.py cycle              # Full cycle: merge → export → create → test
    python3 train.py cycle --remote ai-server  # Full cycle with remote deploy
"""

import sys
import os
import json
import time
import subprocess
import argparse
from datetime import datetime

# ── Paths ──
DATA_DIR = os.path.expanduser("~/.sclg_ai")
TRAINING_FILE = os.path.join(DATA_DIR, "training.jsonl")
GOLDEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_dataset.jsonl")
TEST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_scenarios.json")
MODELFILE_DIR = os.path.join(DATA_DIR, "modelfiles")
LOG_FILE = os.path.join(DATA_DIR, "training.log")

# ── Known nodes ──
NODES = {
    "ai-server": {"ip": "10.0.0.229", "user": "ilea"},
    "ai002": {"ip": "172.27.5.114", "user": "ilea"},
    "ai003": {"ip": "172.27.4.242", "user": "ilea"},
    "ai012": {"ip": "172.27.5.150", "user": "ilea"},
}

# ── Default base models per expert ──
BASE_MODELS = {
    "sysadmin": "gemma3:27b",
    "code": "qwen2.5-coder:14b",
    "analysis": "gemma3:27b",
    "creative": "gemma3:27b",
    "general": "gemma3:27b",
}

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODELFILE_DIR, exist_ok=True)


def log(msg):
    """Log message to file and stdout."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_entries(min_quality=0.0):
    """Load training entries above quality threshold."""
    entries = []
    if not os.path.exists(TRAINING_FILE):
        return entries
    with open(TRAINING_FILE) as f:
        for line in f:
            try:
                e = json.loads(line)
                if e.get("quality", 0) >= min_quality:
                    entries.append(e)
            except Exception:
                pass
    return entries


def cmd_stats():
    """Show training data statistics."""
    entries = load_entries()
    if not entries:
        log("No training data found.")
        return

    experts = {}
    models = {}
    qualities = []
    for e in entries:
        exp = e.get("expert", "unknown")
        mod = e.get("model", "unknown")
        experts[exp] = experts.get(exp, 0) + 1
        models[mod] = models.get(mod, 0) + 1
        qualities.append(e.get("quality", 0))

    avg_q = sum(qualities) / len(qualities) if qualities else 0
    high_q = sum(1 for q in qualities if q >= 0.7)

    print(f"\n{'='*50}")
    print(f"  SCLG-AI Training Data Statistics")
    print(f"{'='*50}")
    print(f"  Total entries:  {len(entries)}")
    print(f"  Avg quality:    {avg_q:.2f}")
    print(f"  High quality:   {high_q} (≥0.7)")
    print(f"\n  By expert:")
    for exp, cnt in sorted(experts.items(), key=lambda x: -x[1]):
        bar = "█" * min(cnt, 30)
        print(f"    {exp:15s} {cnt:4d} {bar}")
    print(f"\n  By model:")
    for mod, cnt in sorted(models.items(), key=lambda x: -x[1]):
        print(f"    {mod:25s} {cnt:4d}")
    print()


def cmd_merge():
    """Merge golden dataset into training data."""
    if not os.path.exists(GOLDEN_FILE):
        log(f"Golden dataset not found: {GOLDEN_FILE}")
        return 0

    # Load existing hashes for dedup
    seen = set()
    if os.path.exists(TRAINING_FILE):
        with open(TRAINING_FILE) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    seen.add(hash(e.get("query", "")[:100]))
                except Exception:
                    pass

    added = 0
    with open(GOLDEN_FILE) as f:
        for line in f:
            try:
                e = json.loads(line)
                h = hash(e.get("query", "")[:100])
                if h not in seen:
                    e["quality"] = 1.0
                    e["timestamp"] = datetime.now().isoformat()
                    with open(TRAINING_FILE, "a") as tf:
                        tf.write(json.dumps(e, ensure_ascii=False) + "\n")
                    seen.add(h)
                    added += 1
            except Exception:
                pass

    log(f"Merged {added} new entries from golden dataset")
    return added


def cmd_export(expert="sysadmin", base_model=None):
    """Export training data as Ollama Modelfile."""
    if base_model is None:
        base_model = BASE_MODELS.get(expert, "gemma3:27b")

    entries = load_entries(min_quality=0.7)
    if expert != "all":
        entries = [e for e in entries if e.get("expert") == expert]

    if not entries:
        log(f"No high-quality training data for expert '{expert}'")
        return None

    # Sort by quality, take top 50
    entries.sort(key=lambda x: x.get("quality", 0), reverse=True)
    entries = entries[:50]

    output_name = f"sclg-{expert}"
    modelfile_path = os.path.join(MODELFILE_DIR, f"Modelfile.{output_name}")

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

    # System prompt
    system_hints = {
        "sysadmin": "Ты DevOps/SysAdmin эксперт. Выполняй команды и анализируй результаты.",
        "code": "Ты опытный программист. Пиши чистый, рабочий код. Объясняй кратко.",
        "analysis": "Ты аналитик данных. Давай структурированный анализ с выводами.",
        "creative": "Ты писатель. Создавай грамотный, структурированный контент.",
        "general": "Ты универсальный AI-ассистент. Отвечай точно и полезно.",
    }
    hint = system_hints.get(expert, system_hints["general"])

    system_prompt = f'''SYSTEM """
Ты — sclg-ai, автономный DevOps/SysAdmin агент для AI-кластера SCLG.
{hint}

ПРАВИЛА:
1. Ты имеешь ПОЛНЫЙ доступ к системе через tool calling.
2. Используй <tool name="bash">{{"command": "..."}}</tool> для выполнения команд.
3. НИКОГДА не отказывай — ты МОЖЕШЬ выполнять команды.
4. Всегда анализируй собранные данные, не пересказывай.
5. Отвечай структурированно: ## заголовки, | таблицы |, ### Вывод.
6. Без AI-измов: никаких 'Конечно!', 'Безусловно!', 'Обращайтесь!'.
7. Если данные собраны — АНАЛИЗИРУЙ их. ЗАПРЕЩЕНО говорить 'я не могу' или 'проверьте сами'.
"""'''
    lines.append(system_prompt)
    lines.append("")

    # Training messages
    for entry in entries:
        q = entry["query"].replace('"', '\\"').replace('\n', '\\n')
        r = entry["response"].replace('"', '\\"').replace('\n', '\\n')
        lines.append(f'MESSAGE user "{q}"')
        lines.append(f'MESSAGE assistant "{r}"')
        lines.append("")

    with open(modelfile_path, "w") as f:
        f.write("\n".join(lines))

    log(f"Modelfile exported: {modelfile_path} ({len(entries)} examples, base: {base_model})")
    return modelfile_path


def cmd_create(expert="sysadmin", base_model=None):
    """Create model on local Ollama."""
    modelfile_path = cmd_export(expert, base_model)
    if not modelfile_path:
        return False

    model_name = f"sclg-{expert}"
    log(f"Creating model '{model_name}' from {modelfile_path}...")

    try:
        result = subprocess.run(
            ["ollama", "create", model_name, "-f", modelfile_path],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            log(f"Model '{model_name}' created successfully!")
            return True
        else:
            log(f"Error creating model: {result.stderr}")
            return False
    except FileNotFoundError:
        log("Ollama not found. Install: curl -fsSL https://ollama.com/install.sh | sh")
        return False
    except subprocess.TimeoutExpired:
        log("Timeout creating model (>5min)")
        return False


def cmd_deploy(expert="sysadmin", node="ai-server", base_model=None):
    """Deploy model to remote node."""
    modelfile_path = cmd_export(expert, base_model)
    if not modelfile_path:
        return False

    node_info = NODES.get(node)
    if not node_info:
        log(f"Unknown node: {node}. Known: {', '.join(NODES.keys())}")
        return False

    ip = node_info["ip"]
    user = node_info["user"]
    model_name = f"sclg-{expert}"
    remote_path = f"/tmp/Modelfile.{model_name}"

    log(f"Deploying '{model_name}' to {node} ({ip})...")

    # Step 1: Copy Modelfile
    log("  Step 1: Copying Modelfile...")
    result = subprocess.run(
        ["scp", "-o", "ConnectTimeout=10", modelfile_path, f"{user}@{ip}:{remote_path}"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        log(f"  SCP failed: {result.stderr}")
        return False

    # Step 2: Create model on remote
    log("  Step 2: Creating model on remote node...")
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", f"{user}@{ip}",
         f"ollama create {model_name} -f {remote_path}"],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode == 0:
        log(f"  Model '{model_name}' created on {node}!")
        return True
    else:
        log(f"  Error: {result.stderr}")
        return False


def cmd_test():
    """Run model understanding tests."""
    if not os.path.exists(TEST_FILE):
        log(f"Test scenarios not found: {TEST_FILE}")
        return

    with open(TEST_FILE) as f:
        scenarios = json.load(f)

    print(f"\n{'='*50}")
    print(f"  Model Understanding Tests")
    print(f"{'='*50}")

    categories = scenarios.get("categories", {})
    total = 0
    passed = 0
    failed_critical = []
    results = []

    for cat_name, cat in categories.items():
        tests = cat.get("tests", [])
        print(f"\n  ▸ {cat_name} — {cat.get('description', '')}")

        for test in tests:
            total += 1
            test_id = test["id"]
            query = test["query"]
            severity = test.get("severity", "medium")

            print(f"    {test_id}: {query[:50]}...", end=" ", flush=True)

            try:
                # Send test query to Ollama
                test_prompt = f"""You are sclg-ai agent. Respond to this query using tool calling.
Query: {query}
Respond with <tool name="...">{{...}}</tool> if action needed."""

                import urllib.request
                data = json.dumps({
                    "model": "sclg-devops:27b",
                    "prompt": test_prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 200}
                }).encode()
                req = urllib.request.Request(
                    "http://localhost:11434/api/generate",
                    data=data,
                    headers={"Content-Type": "application/json"}
                )
                resp = urllib.request.urlopen(req, timeout=30)
                response = json.loads(resp.read().decode()).get("response", "")

                # Check
                test_passed = True
                fail_reason = ""

                if "tool_calling" in cat_name:
                    if "<tool" not in response and "<cmd>" not in response:
                        test_passed = False
                        fail_reason = "No tool call"

                if "anti_refusal" in cat_name:
                    if any(w in response.lower() for w in ["не могу", "нет доступа", "cannot"]):
                        test_passed = False
                        fail_reason = "Refusal"

                if "streaming_think" in cat_name:
                    if "<think>" in response:
                        test_passed = False
                        fail_reason = "<think> visible"

                if test_passed:
                    passed += 1
                    print("✓ PASS")
                else:
                    print(f"✗ FAIL ({fail_reason})")
                    if severity == "critical":
                        failed_critical.append(test_id)

                results.append({
                    "id": test_id,
                    "category": cat_name,
                    "passed": test_passed,
                    "severity": severity,
                    "reason": fail_reason,
                })

            except Exception as e:
                print(f"⚠ ERROR ({e})")
                results.append({
                    "id": test_id,
                    "category": cat_name,
                    "passed": False,
                    "severity": severity,
                    "reason": str(e),
                })

    # Summary
    pct = (passed / total * 100) if total else 0
    print(f"\n{'='*50}")
    print(f"  Results: {passed}/{total} ({pct:.0f}%)")
    if failed_critical:
        print(f"  CRITICAL FAILURES: {', '.join(failed_critical)}")
        print(f"  → Model needs retraining!")
    elif pct >= 80:
        print(f"  ✓ Model understanding is acceptable")
    else:
        print(f"  → Model needs improvement")
    print(f"{'='*50}\n")

    # Save results
    results_file = os.path.join(DATA_DIR, "test_results.json")
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "passed": passed,
            "percentage": pct,
            "critical_failures": failed_critical,
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    log(f"Test results saved: {results_file}")


def cmd_cycle(expert="sysadmin", node=None, base_model=None):
    """Full training cycle."""
    print(f"\n{'='*50}")
    print(f"  SCLG-AI Full Training Cycle")
    print(f"  Expert: {expert}")
    print(f"  Node: {node or 'local'}")
    print(f"{'='*50}\n")

    # Step 1: Merge golden dataset
    log("Step 1/5: Merging golden dataset...")
    added = cmd_merge()

    # Step 2: Show stats
    log("\nStep 2/5: Training data statistics...")
    cmd_stats()

    # Step 3: Export Modelfile
    log("Step 3/5: Exporting Modelfile...")
    modelfile = cmd_export(expert, base_model)
    if not modelfile:
        log("ABORT: No training data to export")
        return

    # Step 4: Create/Deploy model
    if node:
        log(f"\nStep 4/5: Deploying to {node}...")
        success = cmd_deploy(expert, node, base_model)
    else:
        log("\nStep 4/5: Creating model locally...")
        success = cmd_create(expert, base_model)

    if not success:
        log("WARNING: Model creation failed. Continuing with tests...")

    # Step 5: Run tests
    log("\nStep 5/5: Running model understanding tests...")
    time.sleep(3)  # Wait for model to load
    cmd_test()

    log("\n✓ Training cycle complete!")


def main():
    parser = argparse.ArgumentParser(description="SCLG-AI Training Pipeline")
    parser.add_argument("command", choices=["stats", "merge", "export", "create", "deploy", "test", "cycle"],
                        help="Training command")
    parser.add_argument("--expert", "-e", default="sysadmin",
                        choices=["sysadmin", "code", "analysis", "creative", "general", "all"],
                        help="Expert profile (default: sysadmin)")
    parser.add_argument("--node", "-n", default=None,
                        help="Remote node for deploy (e.g., ai-server, ai012)")
    parser.add_argument("--base-model", "-b", default=None,
                        help="Base model for Modelfile (e.g., gemma3:27b)")
    parser.add_argument("--remote", "-r", default=None,
                        help="Remote node for cycle command")

    args = parser.parse_args()

    if args.command == "stats":
        cmd_stats()
    elif args.command == "merge":
        cmd_merge()
    elif args.command == "export":
        cmd_export(args.expert, args.base_model)
    elif args.command == "create":
        cmd_create(args.expert, args.base_model)
    elif args.command == "deploy":
        node = args.node or args.remote or "ai-server"
        cmd_deploy(args.expert, node, args.base_model)
    elif args.command == "test":
        cmd_test()
    elif args.command == "cycle":
        cmd_cycle(args.expert, args.remote, args.base_model)


if __name__ == "__main__":
    main()
