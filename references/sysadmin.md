'''# System Administrator Guide

This guide details how to leverage the local AI assistant for system administration tasks. The assistant can manage files, install software, and automate tasks using schedules.

## 1. File Management

The assistant can perform a wide range of file operations using shell commands.

**Example Request:**
> "Найди все PDF-файлы в папке `~/Documents` за последний месяц и перемести их в `~/Archive/PDFs`."

**Workflow:**
1.  **User:** Describes the file operation.
2.  **Assistant:** Translates the request into a shell command.
3.  **Assistant:** Executes the command using the `shell` tool.
    ```bash
    # Create the destination directory if it doesn't exist
    mkdir -p ~/Archive/PDFs

    # Find and move the files
    find ~/Documents -name "*.pdf" -mtime -30 -exec mv {} ~/Archive/PDFs/ \;
    ```
4.  **Assistant:** Confirms the completion of the task.

**Common Commands:** `ls`, `cp`, `mv`, `rm`, `find`, `grep`, `tar`, `zip`.

## 2. Software Installation

The assistant can install and manage software packages using the system's package manager.

**Example Request:**
> "Установи последнюю версию библиотеки `pandas` для Python 3."

**Workflow:**
1.  **User:** Specifies the software to be installed.
2.  **Assistant:** Determines the correct package manager and command.
3.  **Assistant:** Executes the installation command using the `shell` tool.
    ```bash
    sudo pip3 install --upgrade pandas
    ```
4.  **Assistant:** Verifies the installation and reports back.

**Common Package Managers:** `apt`, `yum`, `pip`, `npm`.

## 3. Scheduled Tasks (Cron Jobs)

The assistant can schedule recurring tasks using the `schedule` tool, which manages cron jobs.

**Example Request:**
> "Каждый понедельник в 9 утра запускай скрипт `/home/ubuntu/scripts/create_backup.sh` для создания бэкапа базы данных."

**Workflow:**
1.  **User:** Describes the task, the schedule, and the script to be executed.
2.  **Assistant:** Uses the `schedule` tool to create the cron job.

    ```python
    default_api.schedule(
        brief="Schedule a weekly database backup",
        type="cron",
        repeat=True,
        name="Weekly DB Backup",
        cron="0 9 * * 1",
        prompt="Run the database backup script located at /home/ubuntu/scripts/create_backup.sh"
    )
    ```
3.  **Assistant:** Confirms that the task has been scheduled.

## 4. System Health Monitoring

The assistant can run scripts to check system health and report key metrics.

**Example Script (`scripts/health_check.sh`):**

```bash
#!/bin/bash
echo "--- System Health Report ---"

echo "\n== CPU Usage =="
df -h

echo "\n== Memory Usage =="
free -h

echo "\n== Disk Space =="
df -h

echo "\n== Running Processes (Top 5 CPU) =="
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -n 6

echo "\n--- End of Report ---"
```

**Example Request:**
> "Проведи проверку состояния системы и покажи мне отчет."

**Workflow:**
1.  **User:** Asks for a system health check.
2.  **Assistant:** Executes the `health_check.sh` script using the `shell` tool.
3.  **Assistant:** Presents the output to the user in a readable format.
'''
