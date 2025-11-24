import typer
from rich import print
from rich.prompt import Prompt
from .config import set_api_key, load_config, write_default_config, history_append
from .llm import LLMClient

import json
import re
from typing import Optional, List
from pydantic import BaseModel, ValidationError, field_validator
from .api import WPDoctorClient
from .context import build_context_text
from .auth import get_api_basic_auth_keys, set_api_basic_auth_keys

app = typer.Typer()

# Sub-apps
creds_app = typer.Typer(help="Manage API credentials in keyring")
api_app = typer.Typer(help="Test REST API connectivity")
system_app = typer.Typer(help="WP Doctor system subcommands")
plugins_app = typer.Typer(help="WP Doctor plugins subcommands")
logs_app = typer.Typer(help="WP Doctor logs subcommands")
actions_app = typer.Typer(help="Common WP-CLI actions")
llm_config_app = typer.Typer(help="Configure LLM provider and model")
aichat_app = typer.Typer(help="Direct chat with the configured LLM")

# Register sub-apps
app.add_typer(creds_app, name="creds")
app.add_typer(api_app, name="api")
app.add_typer(system_app, name="system")
app.add_typer(plugins_app, name="plugins")
app.add_typer(logs_app, name="logs")
app.add_typer(actions_app, name="actions")
app.add_typer(llm_config_app, name="llm-config")
app.add_typer(aichat_app, name="aichat")


class PlanStep(BaseModel):
    cmd: str
    risk: Optional[str] = None
    explain: Optional[str] = None

class PlanModel(BaseModel):
    intent: Optional[str] = None
    risk: Optional[str] = None
    reason: Optional[str] = None
    commands: Optional[List[str]] = None
    steps: Optional[List[PlanStep]] = None
    requires_confirmation: Optional[bool] = None

    @field_validator('risk')
    @classmethod
    def validate_risk(cls, v):
        if v is None:
            return v
        allowed = {"low", "medium", "high", "unknown"}
        if v not in allowed:
            raise ValueError(f"risk must be one of {allowed}")
        return v

    def normalized_commands(self) -> List[str]:
        if self.commands:
            return self.commands
        if self.steps:
            return [s.cmd for s in self.steps if s.cmd]
        return []


def _policy_violations(commands, blocklist_patterns):
    violations = []
    for cmd in commands or []:
        for pat in blocklist_patterns or []:
            if re.search(pat, cmd):
                violations.append({"command": cmd, "pattern": pat})
    return violations


def _validate_ai_response(response_text: str) -> PlanModel:
    # Strip code fences if present
    text = response_text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif text.startswith("```"):
        text = text.split("```", 1)[1].split("```", 1)[0].strip()

    data = json.loads(text)
    plan = PlanModel(**data)
    cmds = plan.normalized_commands()
    if not cmds:
        raise ValueError("AI plan contains no commands. Expected 'commands' or 'steps[*].cmd'.")
    return plan


@app.command()
def init(path: str = typer.Option("", help="Optional path to write config.toml")):
    """
    Initialize configuration.
    Generates config.toml and sets up API keys.
    """
    print("[bold green]Initializing WP Doctor AI CLI...[/bold green]")

    # 1. API Key Setup
    provider = Prompt.ask("Select LLM Provider", choices=["gemini", "openai"], default="gemini")
    api_key = Prompt.ask(f"Enter your {provider} API Key", password=True)

    if api_key:
        set_api_key(provider, api_key)
        print(f"[green]API Key for {provider} saved to keyring.[/green]")

    # 2. Generate config.toml if not exists
    target = None
    if path:
        from pathlib import Path
        target = Path(path)
    write_default_config(target)
    print("[green]config.toml generated (or updated) with defaults.[/green]\n[dim]Edit hosts and policy as needed.[/dim]")


from .prompts import build_prompt


@app.command()
def plan(instruction: str, host: str = typer.Option("default", help="Target host name"), with_context: bool = typer.Option(False, help="Include live system context from API")):
    """Plan commands for an instruction without executing them."""
    config = load_config()
    host_config = config.get_host(host)

    if not host_config:
        print(f"[bold red]Error:[/bold] Host '{host}' not found in config.")
        return

    # Optionally gather live context
    context_text = ""
    if with_context and host_config.api_url:
        try:
            user, pwd = get_api_basic_auth_keys(host)
            if user and pwd:
                api_client = WPDoctorClient(host_config.api_url, username=user, password=pwd)
                payloads = {
                    'system_info': api_client.system_info(),
                    'plugins_analysis': api_client.plugins_analysis(status='active', with_updates=True),
                    'error_logs': api_client.error_logs(lines=50, level='error'),
                    'db_check': api_client.db_check(),
                }
                context_text = build_context_text(payloads)
            else:
                print("[yellow]No API credentials found; skipping context.[/yellow]")
        except Exception as e:
            print(f"[yellow]Context fetch failed:[/] {e}")

    try:
        client = LLMClient(config.llm)
        prompt = build_prompt(instruction, host=host_config.name, context=context_text)

        print("[bold blue]Thinking...[/bold blue]")
        response_text = client.generate_content(prompt)

        try:
            plan_model = _validate_ai_response(response_text)
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            print(f"[bold red]Error:[/bold] Invalid AI response: {e}")
            print(response_text)
            return

        violations = _policy_violations(plan_model.normalized_commands(), load_config().policy.blocklist)
        if violations:
            print("[bold red]Blocked by policy. The following commands match blocklist patterns:[/bold]")
            for v in violations:
                print(f"  - {v['command']} (pattern: {v['pattern']})")
            return

        print(f"\n[bold]Intent:[/bold] {plan_model.intent}")
        print(f"[bold]Risk:[/bold] {plan_model.risk}")
        print(f"[bold]Reason:[/bold] {plan_model.reason}")
        print("[bold]Proposed Commands:[/bold]")
        for cmd in plan_model.normalized_commands():
            print(f"  - {cmd}")

    except Exception as e:
        print(f"[bold red]Error:[/bold] {e}")


@app.command()
def say(instruction: str, host: str = typer.Option("default", help="Target host name"), yes: bool = typer.Option(False, help="Skip confirmation"), with_context: bool = typer.Option(True, help="Include live system context from API")):
    """
    Execute an instruction via AI planning.
    """
    config = load_config()
    host_config = config.get_host(host)

    if not host_config:
        print(f"[bold red]Error:[/bold] Host '{host}' not found in config.")
        return

    # Optionally gather live context
    context_text = ""
    if with_context and host_config.api_url:
        try:
            user, pwd = get_api_basic_auth_keys(host)
            if user and pwd:
                api_client = WPDoctorClient(host_config.api_url, username=user, password=pwd)
                payloads = {
                    'system_info': api_client.system_info(),
                    'plugins_analysis': api_client.plugins_analysis(status='active', with_updates=True),
                    'error_logs': api_client.error_logs(lines=50, level='error'),
                    'db_check': api_client.db_check(),
                }
                context_text = build_context_text(payloads)
            else:
                print("[yellow]No API credentials found; skipping context.[/yellow]")
        except Exception as e:
            print(f"[yellow]Context fetch failed:[/] {e}")

    try:
        client = LLMClient(config.llm)
        prompt = build_prompt(instruction, host=host_config.name, context=context_text)

        print("[bold blue]Thinking...[/bold blue]")
        response_text = client.generate_content(prompt)

        # Clean up markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        try:
            plan_model = _validate_ai_response(response_text)
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            print(f"[bold red]Error:[/bold] Invalid AI response: {e}")
            print(response_text)
            return

        violations = _policy_violations(plan_model.normalized_commands(), config.policy.blocklist)
        if violations:
            print("[bold red]Blocked by policy. The following commands match blocklist patterns:[/bold]")
            for v in violations:
                print(f"  - {v['command']} (pattern: {v['pattern']})")
            return

        print(f"\n[bold]Intent:[/bold] {plan_model.intent}")
        print(f"[bold]Risk:[/bold] {plan_model.risk}")
        print(f"[bold]Reason:[/bold] {plan_model.reason}")
        print("[bold]Proposed Commands:[/bold]")
        for cmd in plan_model.normalized_commands():
            print(f"  - {cmd}")

        if not yes:
            if not Prompt.ask("\nExecute these commands?", choices=["y", "n"], default="y") == "y":
                print("[yellow]Aborted.[/yellow]")
                return

        # Execute
        from .ssh import SSHRunner
        runner = SSHRunner(host_config.ssh)
        results = []
        try:
            runner.connect()
            for cmd in plan_model.normalized_commands():
                print(f"\n[bold]Running:[/] {cmd}")
                exit_code = runner.run_command(cmd)
                results.append({"command": cmd, "exit_code": exit_code})
                if exit_code != 0:
                    print(f"[bold red]Command failed with exit code {exit_code}[/bold]")
                    break
        finally:
            runner.close()
            history_append({
                "host": host_config.name,
                "instruction": instruction,
                "plan": plan_model.model_dump(mode="json"),
                "results": results,
            })

    except Exception as e:
        print(f"[bold red]Error:[/bold] {e}")


@app.command()
def run(command: str, host: str = typer.Option("default", help="Target host name")):
    """
    Run a raw WP-CLI command.
    """
    config = load_config()
    host_config = config.get_host(host)

    if not host_config:
        print(f"[bold red]Error:[/bold] Host '{host}' not found in config.")
        return

    from .ssh import SSHRunner
    try:
        runner = SSHRunner(host_config.ssh)
        print(f"[bold]Running:[/] {command} on {host}")
        exit_code = runner.run_command(command)
        if exit_code != 0:
            print(f"[bold red]Command failed with exit code {exit_code}[/bold]")
            raise typer.Exit(code=exit_code)
    except Exception as e:
        print(f"[bold red]Connection Error:[/] {e}")
        raise typer.Exit(code=1)
    finally:
        if 'runner' in locals():
            runner.close()


@app.command()
def history(limit: int = typer.Option(20, help="Number of recent entries to show")):
    """Show recent execution history."""
    from .config import HISTORY_FILE
    try:
        if not HISTORY_FILE.exists():
            print("[yellow]No history yet.[/yellow]")
            return
        lines = HISTORY_FILE.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-limit:]:
            print(line)
    except Exception as e:
        print(f"[bold red]Error reading history:[/] {e}")


@creds_app.command("set")
def creds_set(host: str = typer.Option(..., "--host", help="Host name as defined in config.toml"), username: str = typer.Option(..., "--username", prompt=True), password: str = typer.Option(..., "--password", prompt=True, hide_input=True)):
    """Save API Basic Auth (Application Password) to keyring for the host."""
    config = load_config()
    host_config = config.get_host(host)
    if not host_config or not host_config.api_url:
        print(f"[bold red]Error:[/bold] Host '{host}' not found or api_url missing in config.")
        raise typer.Exit(code=1)
    set_api_basic_auth_keys(host, username, password)
    print(f"[green]Saved credentials for host '{host}' to keyring.[/green]")


@api_app.command("ping")
def api_ping(host: str = typer.Option(..., "--host", help="Host name as defined in config.toml")):
    """Call /wpdoctor/v1/system-info using stored credentials and print summary."""
    config = load_config()
    host_config = config.get_host(host)
    if not host_config or not host_config.api_url:
        print(f"[bold red]Error:[/bold] Host '{host}' not found or api_url missing in config.")
        raise typer.Exit(code=1)
    user, pwd = get_api_basic_auth_keys(host)
    if not user or not pwd:
        print("[bold red]Error:[/bold] Credentials not found. Run 'wp-ai creds set --host {host}'.")
        raise typer.Exit(code=1)
    try:
        client = WPDoctorClient(host_config.api_url, username=user, password=pwd)
        si = client.system_info()
        wp = si.get('wordpress_version') or si.get('wp_version')
        php = si.get('php_version')
        os = si.get('server_os')
        print(f"[green]OK[/green] system-info: WP={wp} PHP={php} OS={os}")
    except Exception as e:
        print(f"[bold red]API Error:[/bold] {e}")
        raise typer.Exit(code=1)


@system_app.command("info")
def system_info(host: str = typer.Option(..., "--host", help="Host name in config.toml")):
    """Fetch system info via WP Doctor API."""
    config = load_config()
    host_config = config.get_host(host)
    if not host_config or not host_config.api_url:
        print(f"[bold red]Error:[/bold] Host '{host}' not found or api_url missing in config.")
        raise typer.Exit(code=1)
    user, pwd = get_api_basic_auth_keys(host)
    if not user or not pwd:
        print("[bold red]Error:[/bold] Credentials not found. Run 'wp-ai creds set --host {host}'.")
        raise typer.Exit(code=1)
    try:
        client = WPDoctorClient(host_config.api_url, username=user, password=pwd)
        data = client.system_info()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[bold red]API Error:[/bold] {e}")
        raise typer.Exit(code=1)


@plugins_app.command("analysis")
def plugins_analysis(host: str = typer.Option(..., "--host"), status: str = typer.Option("active", help="Filter by status: active|inactive|all"), with_updates: bool = typer.Option(True, help="Include update info")):
    config = load_config()
    host_config = config.get_host(host)
    if not host_config or not host_config.api_url:
        print(f"[bold red]Error:[/bold] Host '{host}' not found or api_url missing in config.")
        raise typer.Exit(code=1)
    user, pwd = get_api_basic_auth_keys(host)
    if not user or not pwd:
        print("[bold red]Error:[/bold] Credentials not found. Run 'wp-ai creds set --host {host}'.")
        raise typer.Exit(code=1)
    try:
        client = WPDoctorClient(host_config.api_url, username=user, password=pwd)
        data = client.plugins_analysis(status=status, with_updates=with_updates)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[bold red]API Error:[/bold] {e}")
        raise typer.Exit(code=1)


@logs_app.command("tail")
def logs_tail(host: str = typer.Option(..., "--host"), lines: int = typer.Option(50), level: str = typer.Option("all", help="all|error|warning|notice")):
    config = load_config()
    host_config = config.get_host(host)
    if not host_config or not host_config.api_url:
        print(f"[bold red]Error:[/bold] Host '{host}' not found or api_url missing in config.")
        raise typer.Exit(code=1)
    user, pwd = get_api_basic_auth_keys(host)
    if not user or not pwd:
        print("[bold red]Error:[/bold] Credentials not found. Run 'wp-ai creds set --host {host}'.")
        raise typer.Exit(code=1)
    try:
        client = WPDoctorClient(host_config.api_url, username=user, password=pwd)
        data = client.error_logs(lines=lines, level=level)
        # Print unified tail
        tail = data.get('tail') or data.get('lines') or data.get('log')
        if isinstance(tail, list):
            print("\n".join(tail))
        elif isinstance(tail, str):
            print(tail)
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[bold red]API Error:[/bold] {e}")
        raise typer.Exit(code=1)


@actions_app.command("cache-flush")
def action_cache_flush(host: str = typer.Option("default", "--host")):
    return run("wp cache flush", host=host)


@actions_app.command("rewrite-flush")
def action_rewrite_flush(host: str = typer.Option("default", "--host"), hard: bool = typer.Option(True, help="Use --hard")):
    cmd = "wp rewrite flush --hard" if hard else "wp rewrite flush"
    return run(cmd, host=host)


@actions_app.command("plugin-activate")
def action_plugin_activate(slug: str, host: str = typer.Option("default", "--host")):
    return run(f"wp plugin activate {slug}", host=host)


@actions_app.command("plugin-deactivate")
def action_plugin_deactivate(slug: str, host: str = typer.Option("default", "--host")):
    return run(f"wp plugin deactivate {slug}", host=host)


@llm_config_app.command("show")
def llm_show():
    cfg = load_config()
    print(json.dumps(cfg.llm.model_dump(), ensure_ascii=False, indent=2))


@llm_config_app.command("set")
def llm_set(provider: str = typer.Option(...), model: str = typer.Option(...)):
    from .config import CONFIG_FILE, ensure_config_dir
    cfg = load_config()
    cfg.llm.provider = provider
    cfg.llm.model = model
    # Persist minimal change by rewriting the default template then patching values
    ensure_config_dir()
    # naive write: load current TOML text and replace lines for llm (simple MVP)
    try:
        text = CONFIG_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        write_default_config()
        text = CONFIG_FILE.read_text(encoding="utf-8")
    import re as _re
    text = _re.sub(r"provider\s*=\s*\".*?\"", f'provider = "{provider}"', text)
    text = _re.sub(r"model\s*=\s*\".*?\"", f'model = "{model}"', text)
    CONFIG_FILE.write_text(text, encoding="utf-8")
    print("[green]LLM config updated.[/green]")


@aichat_app.command("ask")
def aichat_ask(message: str):
    cfg = load_config()
    try:
        client = LLMClient(cfg.llm)
        print("[bold blue]LLM...[/]")
        resp = client.generate_content(message)
        print(resp)
    except Exception as e:
        # Avoid Rich markup errors by using simple print
        import sys
        print(f"LLM Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
