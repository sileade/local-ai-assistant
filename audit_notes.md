# SCLG-AI v4.6.0 Audit Notes

## File Stats
- 3417 lines, 21 classes, 137 functions, 38 section headers
- Single-file monolith — all in sclg_ai_console.py

## Architecture Map (21 classes)
1. C — ANSI color codes
2. ResponseCleaner — anti-AI-isms, repetition detection, toxic token removal
3. OutputFormatter — Claude Code style response rendering (IPs, tables, code blocks)
4. DreamMemory — two-stage memory (short-term + long-term persistent)
5. RequestCache — TTL-based query cache with MD5 hashing
6. StatsTracker — per-expert/model usage stats
7. Spinner — Braille dots animated spinner with elapsed time
8. CommandRenderer — Claude Code style command execution display
9. ProgressTracker — multi-command progress with per-command feedback
10. TypewriterEffect — line-by-line smooth text output
11. ProgressBar — backward-compatible wrapper around ProgressTracker
12. OllamaClient — GPU Balancer API client with retry, stop tokens
13. ClaudeClient — Anthropic API with budget tracking (daily/monthly limits)
14. ExpertRouter — MoE keyword-based query classification
15. QualityChecker — refusal/garbage detection for Claude fallback trigger
16. TrainingCollector — JSONL training data saver
17. SmartExecutor — execute-first pattern matching + command runner
18. NetworkScanner — local subnet discovery (fping/arp)
19. SSHManager — remote command execution via sshpass
20. InfraLearnerBridge — Grafana/Prometheus integration + knowledge base reader
21. SclgAI — main agent class orchestrating everything

## SMART_PATTERNS Coverage (22 patterns)
- Network/IP/DNS (5 patterns)
- Disk, Memory, CPU, Processes, Ports (5 patterns)
- Docker, GPU, Ollama, Logs, Services (5 patterns)
- SSL, Git, Firewall, Cron, Users (5 patterns)
- Speed Test, Ping (2 patterns)

## MODEL_PROFILES (5 experts)
- code: sclg-coder:32b, qwen2.5-coder-tools:32b, etc.
- sysadmin: sclg-devops:27b, qwen3.5-27b-hf, gemma4-26b-hf, etc.
- analysis: gemma4-26b-hf, glm-4.7-flash-hf, phi4:14b, etc.
- creative: glm-4.7-flash-hf, gemma4-26b-hf, etc.
- general: sclg-general:14b, gemma4-26b-hf, etc.

## Slash Commands (16)
/help /models /hosts /stats /memory /clear /new /scan /ssh /claude
/knowledge /anomalies /gpu /grafana /version /quit

## CLI Modes
- Interactive (default)
- Single query: sclg-ai -e "query"
- Quick scan: sclg-ai --scan
- Show hosts: sclg-ai --hosts
- Show stats: sclg-ai --stats

## BUGS & ISSUES FOUND

### Critical
1. **SSHManager password injection** (line 2012): Password passed via shell string
   `sshpass -p '{password}'` — shell injection if password contains single quotes
   
2. **Bare except clauses** — 30+ instances of `except:` without specific exception types
   Swallows KeyboardInterrupt, SystemExit, MemoryError

3. **Double cleaning** (line 3330): response is cleaned TWICE — once at line 2531 in process_query,
   then again at line 3330 in run(). The second clean operates on already-cleaned text.

### High
4. **Repetition regex non-functional** (line 532): `(.{2,30?}){4,}` — lacks backreference `\1`.
   Without `\1`, it matches ANY 4+ groups of 2-30 chars, not the SAME substring repeated.
   Tested: current regex matches nothing (Python regex engine optimizes it away).
   The correct fix `(.{2,30}?)\1{3,}` works but has false positives on short repeated
   substrings like '8.' in normal text. Method 2 (trigram) and Method 3 (line count)
   are the actual working repetition detectors. Method 1 is dead code.

5. **Cache key collision risk**: MD5[:12] = 48 bits = collision at ~16M entries.
   Fine for 200 entries but the truncation is unnecessary.

6. **Thread safety**: Spinner._running is a bool without lock, read from main thread
   and written from animation thread. Works on CPython due to GIL but not guaranteed.

7. **No conversation limit in _build_system_prompt**: conversation[-4:] is added to system prompt
   AND messages[-6:] is sent as chat history. Combined with data_context, system prompt
   can exceed model context window.

### Medium
8. **_is_direct_command false positives**: `"date"` matches any query starting with "date"
   like "дайте мне" (Russian for "give me"). Needs word boundary check.

9. **KNOWN_HOSTS hardcoded passwords**: Even with env var fallback, the structure encourages
   storing passwords in hosts.json on disk.

10. **No timeout on Grafana banner queries**: _get_dynamic_data makes 3+ HTTP calls
    during banner display. If Grafana is slow, startup hangs.
    (Actually has timeout=3, OK)

11. **Memory consolidation only on /new**: Short-term facts are only promoted to long-term
    on explicit /new command or session end. Important facts from mid-session may be lost
    if process crashes.

12. **ResponseCleaner replaces "robust" → "reliable"**: This changes technical meaning
    in contexts like "robust algorithm" or "robust error handling".

### Low
13. **get_terminal_width has 7 fallback methods**: Overly defensive. Methods 1-3 cover
    99.9% of cases. The rest add complexity for no real benefit.

14. **import ssl as _ssl at module level** (line 2047): Placed between classes instead of
    at top of file with other imports.

15. **ProgressBar legacy wrapper**: Unused in current code — all callers use ProgressTracker directly.

16. **TypewriterEffect.print shadows builtin**: The classmethod name `print` shadows
    Python's builtin `print`. Not a bug but confusing.

## STRENGTHS

1. **Execute-first philosophy**: Collects real data before AI analysis — unique and powerful
2. **MoE routing**: Automatic expert selection with keyword scoring
3. **Multi-tier fallback**: Local model → fallback model → Claude → raw data formatting
4. **Budget tracking**: Claude daily/monthly limits with persistent tracking
5. **Response cleaning**: Comprehensive anti-AI-isms + toxic token removal + repetition detection
6. **InfraLearner integration**: Background knowledge enrichment from Grafana/Prometheus
7. **Dream Memory**: Two-stage memory with auto-promotion of infrastructure facts
8. **Rich UI**: Claude Code style animations, colored output, typewriter effect
9. **Self-learning**: Training data collection for future fine-tuning
10. **Network awareness**: Built-in scanning, SSH management, host discovery

## MISSING CAPABILITIES

1. **No streaming**: All API calls are non-streaming. For large responses, user waits
   with no feedback until complete response arrives.

2. **No file operations**: Cannot read/write/edit files on behalf of user.
   Claude Code can do this — sclg-ai cannot.

3. **No multi-turn agent loop**: <cmd> tags are processed once. If the AI needs to
   run a command, see the result, then run another — it can't.

4. **No tool use / function calling**: No structured tool interface.
   Commands are embedded in <cmd> tags in free text.

5. **No web search**: Cannot search the internet for information.

6. **No image/media handling**: Text-only interface.

7. **No rollback/undo**: Destructive commands (rm, kill) have no safety net.

8. **No rate limiting on local commands**: A malicious prompt could trigger
   unlimited command execution.

9. **No authentication**: Anyone with terminal access can use all features
   including SSH to all known hosts.

10. **No unit tests**: Zero test coverage. CI only checks syntax.
