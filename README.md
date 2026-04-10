# sclg-ai — Scoliologic AI Console

Autonomous DevOps/SysAdmin agent that runs on Mac Mini M4 Pro. Execute first, explain later.

## Architecture

sclg-ai v4.1 integrates ideas from five open-source projects into a single-file Python agent:

| Source | Feature | Integration |
|--------|---------|-------------|
| ai-unified-platform | Parallel inference, request caching | RequestCache with TTL and hash-based lookup |
| ai-router-moe | MoE expert routing, YAML config | ExpertRouter with keyword + confidence scoring |
| local-ai-assistant | Monitoring, structured roles | MODEL_PROFILES with 5 expert categories |
| nanobot | Dream memory, skills, lifecycle hooks | DreamMemory with short-term/long-term consolidation |
| avoid-ai-writing | Anti-AI-isms post-processor | ResponseCleaner with 3-tier word replacement |

## Key Features

**Execute-First Approach** — for any system/network query, sclg-ai runs shell commands locally on the Mac Mini before sending results to the AI model for analysis. The model never says "I can't access your system" because the data is already collected.

**MoE Expert Routing** — queries are classified into expert categories (code, sysadmin, analysis, creative, general) and routed to the best available model on the GPU cluster.

**Claude Fallback** — if the local model refuses to analyze collected data or gives a generic response, the agent automatically falls back to Claude Sonnet with full context.

**Dream Memory** — two-stage persistent memory system. Short-term facts are kept during the session; important facts (IPs, errors, configs) are automatically promoted to long-term storage.

**Response Cleaning** — all responses pass through a post-processor that strips chatbot openers ("Certainly!"), closers ("Let me know if you need anything else!"), filler transitions ("Moreover,"), and replaces AI-isms (leverage→use, robust→reliable).

## Infrastructure

The agent connects to a GPU cluster via a load balancer:

| Node | IP | Hardware |
|------|-----|----------|
| ai-server | 10.0.0.229 | GPU Balancer (main) |
| ai002 | 172.27.5.114 | 2x RTX 5070 Ti |
| ai012 | 172.27.5.150 | RTX 2000 Ada |
| ai003 | 172.27.4.242 | RTX 5070 Ti |
| mac-mini | 172.27.4.255 | Mac Mini M4 Pro |

## Usage

```bash
sclg-ai              # Interactive console
sclg-ai --version    # Show version
sclg-ai -e "query"   # Single query mode
sclg-ai --scan       # Quick network scan
sclg-ai --hosts      # Show known hosts
sclg-ai --stats      # Show usage statistics
```

## Slash Commands

| Command | Description |
|---------|-------------|
| `/models` | Show available AI models |
| `/hosts` | Show known infrastructure hosts |
| `/stats` | Show usage statistics |
| `/memory` | Show agent memory |
| `/scan [net]` | Scan network |
| `/ssh host cmd` | Execute command on remote host |
| `/claude query` | Force Claude for this query |
| `/clear` | Clear conversation |
| `/new` | New session (consolidate memory) |

## Auto-Deploy

Push to `main` branch triggers automatic deployment to Mac Mini via GitHub Actions through the bastion server.

## License

Private — Scoliologic AI
