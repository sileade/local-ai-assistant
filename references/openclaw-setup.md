'''# OpenClaw and Local Model Setup Guide

This guide provides a comprehensive walkthrough for setting up your personal AI assistant using OpenClaw with a local AI model running via Ollama. This setup ensures maximum privacy and control.

## 1. Prerequisites

Before you begin, ensure your system meets the following requirements:

- **Node.js**: Version 22 or higher.
- **Docker and Docker Compose**: For containerized and secure execution.
- **Ollama**: Installed and running. Download from [https://ollama.com/](https://ollama.com/).
- **GPU (Recommended)**: A GPU with at least 8-12 GB of VRAM is strongly recommended for acceptable performance.

## 2. Install and Configure a Local LLM with Ollama

First, download a suitable model for tool use. Models with a large context window (64k+ tokens) are preferred.

```bash
# Pull a recommended model (e.g., qwen3-coder)
ollama pull qwen3-coder
```

Ensure the Ollama server is running in the background.

## 3. Install OpenClaw (Docker Recommended)

Using Docker is the safest way to run OpenClaw, as it isolates the agent from your host system.

```bash
# 1. Clone the OpenClaw repository
git clone https://github.com/openclaw/openclaw.git
cd openclaw

# 2. Run the automated setup script
./docker-setup.sh
```

This script will build the Docker image, run the initial configuration wizard, and set up a `docker-compose.yml` file.

## 4. Configure OpenClaw for Local Model

After the setup script finishes, you need to edit the OpenClaw configuration to point to your local Ollama server. The configuration is located at `~/.openclaw/openclaw.json`.

Open the file and modify the `provider` and `agent` sections as follows:

```json
{
  "provider": {
    "type": "openai-compatible",
    "baseURL": "http://localhost:11434/v1",
    "modelId": "qwen3-coder",
    "apiKey": "ollama"
  },
  "agent": {
    "model": "ollama/qwen3-coder"
  }
  // ... other configurations like channels
}
```

**Key Configuration Points:**
- `baseURL`: Points to the default Ollama API endpoint.
- `modelId`: The name of the model you downloaded with Ollama.
- `apiKey`: Can be any string, as it's not required for local Ollama.

## 5. Start OpenClaw

If you used the Docker setup, you can start the OpenClaw gateway with Docker Compose:

```bash
docker compose up -d
```

Your local AI assistant is now running. You can interact with it through the channels you configured during the `onboard` process (e.g., Telegram).

## 6. Expanding Capabilities with MCP Servers

To add functionalities like audio transcription or image generation, you can install MCP (Model Context Protocol) servers. Many are available as pre-packaged skills on ClawHub.

**Example: Adding Whisper for audio transcription**

```bash
# Execute this inside the OpenClaw CLI container
docker compose run --rm openclaw-cli npx clawhub@latest install whisper-transcription
```

This makes the `whisper` tool available to your agent. You will need to provide an `OPENAI_API_KEY` for this specific skill, as it uses the OpenAI Whisper API by default. For a fully local setup, you would need to deploy a local Whisper MCP server (see `references/creative.md`).
'''
