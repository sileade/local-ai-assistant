'''# Creative Partner Guide

This guide covers how to use the local AI assistant for creative tasks, including generating images, transcribing audio, and synthesizing speech. For a fully local setup, these tasks require dedicated models and MCP servers.

## 1. Image Generation

The assistant can generate images from text descriptions. While the `openclaw_guide.md` mentions cloud services like Fal.ai, a truly local setup can be achieved using a ComfyUI MCP server.

**Local Setup with ComfyUI:**

1.  **Install ComfyUI**: Follow the official instructions to install ComfyUI, a powerful and modular GUI for Stable Diffusion.
2.  **Install ComfyUI MCP Server**: Use the community-provided MCP server to connect OpenClaw to ComfyUI.
    ```bash
    # Inside your ComfyUI/custom_nodes directory
    git clone https://github.com/Peleke/comfyui-mcp.git
    ```
3.  **Configure**: Point the MCP server to your running ComfyUI instance. This typically runs on `http://127.0.0.1:8188`.
4.  **Connect to OpenClaw**: Add the ComfyUI MCP server to your `openclaw.json` configuration.

**Example Request:**
> "Нарисуй мне логотип для моего нового проекта: 'космический енот в очках', в мультяшном стиле."

**Workflow:**
1.  **User:** Provides a descriptive prompt for the image.
2.  **Assistant:** Uses the configured image generation tool (ComfyUI MCP) to create the image.
3.  **Assistant:** Sends the generated image file back to the user.

## 2. Speech-to-Text (Audio Transcription)

The assistant can transcribe audio from various sources, including voice messages and video files.

**Local Setup with Whisper:**

1.  **Deploy Whisper MCP Server**: Use a self-hosted Whisper MCP server. A popular option is available on GitHub.
    ```bash
    # Clone the repository
    git clone https://github.com/arcaputo3/mcp-server-whisper.git
    cd mcp-server-whisper

    # Install dependencies and run
    pip install -r requirements.txt
    python main.py
    ```
2.  **Connect to OpenClaw**: Add the local Whisper MCP server to your `openclaw.json` configuration.

**Example Request:**
> (User sends a Telegram voice message)
> "Расшифруй это голосовое сообщение."

**Workflow:**
1.  **User:** Sends an audio file or a voice message.
2.  **Assistant:** The OpenClaw Telegram channel automatically receives the file.
3.  **Assistant:** The `whisper` tool is invoked, sending the audio to the local Whisper MCP server for transcription.
4.  **Assistant:** The transcribed text is returned to the user.

## 3. Text-to-Speech (Speech Synthesis)

The assistant can convert text into a spoken audio file.

**Local Setup with Piper TTS:**

Piper is a fast, local text-to-speech system that works well on CPU.

1.  **Download Piper**: Get the Piper executable and desired voice models from the official repository.
2.  **Create a Wrapper Script**: To make it easy for the assistant to use, create a simple shell script in the `scripts/` directory of this skill (e.g., `scripts/tts.sh`).

    ```bash
    #!/bin/bash
    TEXT="$1"
    OUTPUT_FILE="$2"
    VOICE_MODEL="/path/to/your/voice.onnx"
    PIPER_EXECUTABLE="/path/to/piper/piper"

    echo "$TEXT" | "$PIPER_EXECUTABLE" -m "$VOICE_MODEL" -f "$OUTPUT_FILE"
    ```

**Example Request:**
> "Прочитай мне вслух текст из этого файла: `article.txt`. Сохрани результат в `audio_version.wav`."

**Workflow:**
1.  **User:** Provides the text or a file containing the text.
2.  **Assistant:** Reads the text from the file.
3.  **Assistant:** Executes the `tts.sh` script using the `shell` tool, passing the text and output file path as arguments.
4.  **Assistant:** Informs the user that the audio file has been created and provides the path.
'''
