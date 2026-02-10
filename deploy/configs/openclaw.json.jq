{
  "provider": {
    "type": "openai-compatible",
    "baseURL": $baseURL,
    "modelId": $model,
    "apiKey": "ollama"
  },
  "agent": {
    "model": $model
  },
  "channels": {
    "telegram": {
      "enabled": ($botToken | length > 0),
      "botToken": $botToken,
      "dmPolicy": "pairing"
    }
  },
  "sandbox": {
    "enabled": true,
    "type": "docker",
    "docker": {
      "containerName": "openclaw-sandbox"
    }
  }
}
