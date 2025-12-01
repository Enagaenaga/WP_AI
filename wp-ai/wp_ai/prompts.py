SYSTEM_PROMPT = """**CRITICAL INSTRUCTION**: You MUST respond with ONLY a valid JSON object. No markdown, no code blocks, no explanations.

You are WP Doctor AI, an intelligent assistant for WordPress operations.
Your goal is to help the user manage their WordPress site by generating WP-CLI commands.

## Constraints & Rules
1. **Safety First**: Never generate destructive commands (e.g., `db drop`, `rm -rf`) without explicit user confirmation and strong warning.
2. **WP-CLI Command Format**: You must generate commands in the EXACT format required by the target host environment.
3. **JSON Output**: You MUST output your plan in strict JSON format.

## WP-CLI Command Format Rules
{wp_cli_format_instructions}

## Output Format - CRITICAL REQUIREMENTS

**YOU MUST FOLLOW THESE RULES EXACTLY:**

1. ✅ **DO**: Output ONLY a raw JSON object starting with {{ and ending with }}
2. ✅ **DO**: Use this exact structure:
{{
  "intent": "Brief description of what you are about to do",
  "commands": [{example_command}],
  "risk": "low",
  "reason": "Explanation of why these commands are chosen"
}}

3. ❌ **DO NOT**: Use markdown code blocks like ```json or ```
4. ❌ **DO NOT**: Add any text before the JSON object
5. ❌ **DO NOT**: Add any text after the JSON object
6. ❌ **DO NOT**: Add any explanations or comments

**The "risk" field MUST be one of**: "low", "medium", "high", or "unknown"

**EXAMPLE OF CORRECT OUTPUT:**
{{"intent": "Clear WordPress cache", "commands": ["wp cache flush"], "risk": "low", "reason": "Safe operation to refresh cache"}}

**EXAMPLE OF INCORRECT OUTPUT (DO NOT DO THIS):**
```json
{{"intent": "Clear cache", "commands": ["wp cache flush"], "risk": "low", "reason": "Safe"}}
```

## Context
Target Host: {host}

**REMEMBER**: Your entire response must be ONLY the JSON object. Nothing else.
"""

def build_prompt(instruction: str, host=None, host_config=None, context: str = "") -> str:
    """Build the full prompt for the LLM.
    
    Args:
        instruction: User's instruction
        host: Host name (string) - for backward compatibility
        host_config: HostConfig object containing SSH configuration
        context: Optional system context
        
    Returns:
        Complete prompt string for the LLM
    """
    # Determine host name and config
    if host_config:
        host_name = host_config.name if hasattr(host_config, 'name') else 'unknown'
    elif host:
        host_name = host if isinstance(host, str) else 'unknown'
    else:
        host_name = 'unknown'
    
    # WP-CLI command format instructions
    wp_cli_instructions = ""
    example_command = '"wp plugin list --status=active --format=table"'
    
    if host_config and hasattr(host_config, 'ssh') and host_config.ssh:
        ssh_config = host_config.ssh
        
        # wp_path が設定されている場合
        if ssh_config.wp_path:
            wp_cli_instructions = f"""**CRITICAL COMMAND FORMAT REQUIREMENT**:
This host uses a custom WP-CLI path. You MUST follow this EXACT format for ALL commands:

1. Start with: `{ssh_config.wp_path}`
2. Follow with the WP-CLI subcommand (WITHOUT the 'wp' prefix)
3. End with: `--path='{ssh_config.wordpress_path}'`

**Examples:**
- Instead of: `wp cache flush`
  You MUST generate: `{ssh_config.wp_path} cache flush --path='{ssh_config.wordpress_path}'`

- Instead of: `wp plugin list --status=active`
  You MUST generate: `{ssh_config.wp_path} plugin list --status=active --path='{ssh_config.wordpress_path}'`

- Instead of: `wp core version`
  You MUST generate: `{ssh_config.wp_path} core version --path='{ssh_config.wordpress_path}'`

**REMEMBER**: Remove 'wp' from the beginning and add the custom path and --path parameter!
"""
            example_command = f'"{ssh_config.wp_path} cache flush --path=\'{ssh_config.wordpress_path}\'"'
        
        # wp_path がなくても wordpress_path が設定されている場合
        elif ssh_config.wordpress_path:
            wp_cli_instructions = f"""**IMPORTANT**: This host requires the WordPress path to be specified.
You MUST add `--path='{ssh_config.wordpress_path}'` to all WP-CLI commands.

Example: `wp plugin list --path='{ssh_config.wordpress_path}'`
"""
            example_command = f'"wp plugin list --status=active --format=table --path=\'{ssh_config.wordpress_path}\'"'
        
        # 標準的な wp コマンド
        else:
            wp_cli_instructions = """Generate standard WP-CLI commands starting with `wp`.

Example: `wp plugin list --status=active`
"""
    else:
        # SSH設定がない場合は標準コマンド
        wp_cli_instructions = """Generate standard WP-CLI commands starting with `wp`.

Example: `wp plugin list --status=active`
"""
    
    # Build the prompt
    prompt = SYSTEM_PROMPT.format(
        host=host_name,
        wp_cli_format_instructions=wp_cli_instructions,
        example_command=example_command
    )
    
    if context:
        prompt += f"\n\n[Current System Context]\n{context}"
    
    prompt += f"\n\n[User Instruction]\n{instruction}"
    
    return prompt
