'''# Programmer Intern Guide

This guide outlines how to use the local AI assistant for programming tasks. The assistant can write code, debug issues, and interact with version control systems.

## Writing Code

To have the assistant write code, provide a clear and specific prompt.

**Example Request:**
> "Напиши мне простой Python-скрипт, который будет скачивать все изображения с веб-страницы по заданному URL. Скрипт должен сохранять изображения в папку с именем, основанным на домене сайта."

**Expected Action:**
The assistant will generate a Python script file (e.g., `image_downloader.py`) and provide it to you. You should then review and execute the script.

**Workflow:**
1.  **User:** Provides a detailed request for a script.
2.  **Assistant:** Asks clarifying questions if needed.
3.  **Assistant:** Writes the code and saves it to a file using the `file` tool.
4.  **Assistant:** Informs the user about the created file.

## Debugging Code

The assistant can help identify and fix errors in your code.

**Example Request:**
> "У меня ошибка в этом Python-файле. Не могу понять, почему возникает `IndexError`. Вот файл: `/path/to/my/buggy_script.py`. Помоги найти проблему."

**Workflow:**
1.  **User:** Provides the file with the error and a description of the issue.
2.  **Assistant:** Reads the specified file using the `file` tool.
3.  **Assistant:** Analyzes the code to identify the potential cause of the error.
4.  **Assistant:** Suggests a fix, either by explaining the problem and solution or by providing a corrected code snippet using the `edit` action of the `file` tool.

## Working with GitHub

The assistant can interact with GitHub repositories using shell commands.

**Example Request:**
> "Зайди в мой репозиторий `my-awesome-project` на GitHub, посмотри последний pull request и проверь, есть ли в нем конфликты слияния."

**Prerequisites:**
- The `gh` command-line tool must be installed and authenticated.
- The repository must be cloned locally, or the assistant needs the URL to clone it.

**Workflow:**
1.  **User:** Specifies the repository and the task.
2.  **Assistant:** Uses `shell` commands to navigate to the repository directory (`cd /path/to/repo`).
3.  **Assistant:** Executes `gh` commands to inspect pull requests (e.g., `gh pr list`, `gh pr diff`, `gh pr checkout <pr-number>`).
4.  **Assistant:** Analyzes the output to check for merge conflicts or other issues.
5.  **Assistant:** Reports the findings back to the user.

**Common GitHub Commands:**
- `gh repo clone <owner>/<repo>`
- `gh pr list`
- `gh pr view <pr-number>`
- `gh pr diff <pr-number>`
- `gh pr checkout <pr-number>`
- `git pull`
- `git merge ...`
'''
