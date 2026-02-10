'''# Security Hardening and Incident Response Guide

This guide focuses on securing your self-hosted AI assistant and automating security tasks. A proactive security posture is critical when running an agent with access to system resources.

## 1. Principle of Least Privilege

- **Run in Docker**: Always run OpenClaw inside a Docker container. This is the most critical security measure.
- **Use a Non-Root User**: Ensure the Docker container runs as a non-privileged user.
- **Limit Tool Access**: In `openclaw.json`, only enable the tools (`skills`) that the assistant absolutely needs. Disable powerful tools like `exec` (shell access) if not required for daily tasks, or implement a confirmation step.

## 2. Automated Security Hardening

The assistant can use scripts to automate the hardening of the underlying Linux system. A template script `scripts/harden_server.sh` is provided in this skill.

**Key Hardening Steps in the Script:**
- **Update System**: Ensures all packages are up-to-date with the latest security patches.
- **Configure Firewall**: Sets up `ufw` (Uncomplicated Firewall) to deny all incoming traffic by default and only allow essential ports (e.g., SSH, HTTP/S).
- **Disable Unused Services**: Reduces the attack surface by stopping and disabling unnecessary services.
- **Secure SSH**: Disables root login and password authentication, enforcing key-based login.
- **Audit Open Ports**: Lists all listening ports to help identify unauthorized services.

**Example Request:**
> "Проведи базовое укрепление безопасности на этом сервере."

**Workflow:**
1.  **User:** Requests server hardening.
2.  **Assistant:** Locates and reviews the `scripts/harden_server.sh` script.
3.  **Assistant:** Asks the user for confirmation before running, as it will make significant system changes.
4.  **Assistant:** Executes the script using the `shell` tool: `sudo bash /home/ubuntu/skills/local-ai-assistant/scripts/harden_server.sh`.
5.  **Assistant:** Reports the actions taken.

## 3. Automated Security Audits

Regularly auditing the system for vulnerabilities is crucial. The assistant can use tools like `lynis` to perform in-depth security scans.

**Example Request:**
> "Проведи аудит безопасности системы с помощью lynis и покажи мне основные предупреждения."

**Workflow:**
1.  **Assistant:** Checks if `lynis` is installed. If not, installs it (`sudo apt-get install lynis -y`).
2.  **Assistant:** Runs the audit command:
    ```bash
    sudo lynis audit system --quiet --no-colors > /tmp/lynis_report.txt
    ```
3.  **Assistant:** Reads the report file `/tmp/lynis_report.txt`.
4.  **Assistant:** Parses the report, focusing on the "Warnings" and "Suggestions" sections.
5.  **Assistant:** Summarizes the key findings and recommends remediation steps to the user.

## 4. Incident Response Playbook

If a security incident is suspected, the assistant can follow a basic incident response playbook.

**Example Request:**
> "Я думаю, на сервере подозрительная активность. Запусти протокол реагирования на инциденты."

**Incident Response Workflow:**
1.  **Isolate (Optional, Manual Step Recommended)**: The assistant should first recommend the user to isolate the machine from the network if the threat is severe.

2.  **Collect Volatile Data**: The assistant runs a script (`scripts/incident_snapshot.sh`) to quickly collect volatile data for analysis. This script captures:
    -   Current network connections (`netstat -tulpn`).
    -   Running processes (`ps aux`).
    -   Logged-in users (`who`).
    -   Recent command history (`history`).
    -   Key log files (`/var/log/auth.log`, `/var/log/syslog`).
    The output is saved to a timestamped file in a secure location.

3.  **Analyze**: The assistant analyzes the collected data for signs of compromise:
    -   Unusual network connections to unknown IPs.
    -   Suspicious processes not part of the standard deployment.
    -   Unauthorized user logins.
    -   Anomalies in system or authentication logs.

4.  **Report**: The assistant provides a summary of its findings, highlighting suspicious activities and recommending next steps, such as blocking an IP address, killing a process, or taking the system offline for a full forensic analysis.
'''
