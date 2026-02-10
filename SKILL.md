---
name: local-ai-assistant
description: Provides a comprehensive guide for deploying and managing a personal, locally-run AI assistant using OpenClaw and Ollama. This skill transforms Manus into a multi-faceted partner capable of acting as a programmer intern, creative partner, system administrator, and DevOps engineer. Use this skill for tasks involving local model setup, code writing and debugging, image and text generation, system administration (file management, package installation, scheduled tasks), and advanced DevOps practices (CI/CD, IaC, Kubernetes, monitoring, security).
license: Complete terms in LICENSE.txt
---

# Local AI Assistant Skill

This skill provides the knowledge and workflows to deploy, manage, and utilize a powerful, self-hosted AI assistant built on OpenClaw and local language models via Ollama. It enables Manus to perform a wide range of tasks, acting as a versatile partner for development, creative work, and system management.

## Core Capabilities

This skill integrates four key roles into a single, cohesive assistant:

| Role                  | Description                               | Key Functions                                                     |
| :-------------------- | :---------------------------------------- | :---------------------------------------------------------------- |
| **Programmer Intern**   | Assists with coding and development tasks. | Writing scripts, debugging code, working with Git and GitHub.     |
| **Creative Partner**    | Generates creative content.               | Creating images from text, transcribing audio, and synthesizing speech. |
| **System Administrator**| Manages the underlying system and files.  | File operations, package installation, process management, and scheduling tasks. |
| **DevOps Engineer**     | Automates and manages infrastructure.     | CI/CD, Infrastructure as Code (IaC), container orchestration, monitoring, and security. |

## Core Workflows

This skill is structured around a set of core workflows. Follow these steps to effectively use the local AI assistant.

1.  **Initial Setup**: Begin by setting up the OpenClaw environment with a local model. This is a one-time process.
2.  **Task Execution**: Once set up, you can issue commands related to any of the four roles.
3.  **System Maintenance**: Regularly perform system administration and DevOps tasks to ensure the assistant runs smoothly and securely.

## Skill Navigation

This skill is organized into several documents to provide detailed guidance without overwhelming the context window. Refer to the appropriate document based on your needs.

- **Initial Setup & Configuration**
  - `references/openclaw-setup.md`: A step-by-step guide to installing and configuring OpenClaw, Ollama, and the necessary local models.

- **Role-Specific Guides**
  - `references/programmer.md`: Instructions and examples for code-related tasks.
  - `references/creative.md`: Guidance on using the creative tools for image, audio, and text generation.
  - `references/sysadmin.md`: Best practices and scripts for system administration.
  - `references/devops.md`: Advanced workflows for DevOps, including CI/CD and IaC.

- **Specialized Topics**
  - `references/monitoring.md`: Detailed instructions for setting up and using the Prometheus, Grafana, and Loki monitoring stack.
  - `references/security.md`: A guide to security hardening, automated audits, and incident response.

- **Scripts & Templates**
  - `scripts/`: A collection of ready-to-use automation scripts for various tasks.
  - `templates/`: Reusable configuration files for services like Docker, Nginx, and Prometheus.
