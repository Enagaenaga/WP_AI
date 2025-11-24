# WP-AI (WP Doctor AI GUI)

WP-AI is a powerful desktop GUI application designed to assist WordPress administrators in managing and troubleshooting their sites using AI. It integrates with Google Gemini (and OpenAI) to generate execution plans, analyze logs, and perform complex tasks via SSH and WP-CLI.

## Features

* **AI Planner**: Describe your task in natural language (e.g., "List all active plugins", "Check for updates"), and the AI will generate a sequence of WP-CLI commands to execute.
* **SSH Execution**: Securely connects to your WordPress server via SSH to execute commands directly. Supports key-based authentication.
* **Execution History**: Saves all executed plans and commands, allowing you to review past actions and re-run them easily.
* **Plugin Analysis**: (Coming soon) Analyzes installed plugins for conflicts, security issues, and performance impact.
* **System Info**: (Coming soon) Displays detailed server and WordPress environment information.
* **Log Viewer**: (Coming soon) Fetches and analyzes WordPress debug logs and PHP error logs.

## Prerequisites

* **Windows OS** (Currently optimized for Windows)
* **Python 3.10+**
* **SSH Access** to your WordPress server
* **WP-CLI** installed on the server (or a standalone `wp-cli.phar` file)

## Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/Enagaenaga/WP_AI.git
    cd WP-AI
    ```

2. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

    *(Note: If `requirements.txt` is missing, install: `tk paramiko tomli google-generativeai pydantic`)*

## Configuration

1. **Create `config.toml`**:
    Copy the example configuration (or create a new one) at `wp-ai/config.toml`.

2. **Edit `config.toml`**:
    Configure your LLM provider (Gemini) and SSH host details.

    ```toml
    [llm]
    provider = "gemini"
    model = "gemini-flash-lite-latest"
    # api_key is loaded from environment variable GOOGLE_API_KEY or can be set here (not recommended for git)

    [hosts.ssh]
    host = "your-server.com"
    port = 22
    user = "your-username"
    key_path = "C:\\Users\\YourName\\.ssh\\id_rsa"
    wp_path = "/path/to/wp-cli.phar" # If wp is not in PATH
    wordpress_path = "/path/to/wordpress/root" # Path to WP installation
    ```

## Usage

1. **Launch the GUI:**
    Double-click `Launch_WP_AI_GUI.bat` or run:

    ```bash
    python -m wp_ai.main
    ```

2. **Select Host**: Choose your configured host from the dropdown.
3. **AI Planner**: Click "AI Planner" to start a new task.
4. **History**: Click "History" to view past operations.

## Project Structure

* `wp_ai/`: Main Python package
  * `gui/`: Tkinter GUI components (`launcher.py`, `planner_window.py`, etc.)
  * `llm.py`: LLM client integration
  * `ssh.py`: SSH connection and command runner
  * `config.py`: Configuration models
* `Launch_WP_AI_GUI.bat`: Launcher script for Windows

## License

[MIT License](LICENSE) (or specify your license)
