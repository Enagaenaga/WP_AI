#!/usr/bin/env python3
"""Helper script to set API key via keyring (no hardcoded secrets)."""
import keyring
import sys
import getpass

if __name__ == "__main__":
    # Check if command line arguments are provided
    if len(sys.argv) == 3:
        provider, api_key = sys.argv[1], sys.argv[2]
    else:
        # Interactive mode
        print("===========================================")
        print("   WP-AI API Key Setup (Interactive Mode)")
        print("===========================================")
        print()
        print("Supported providers:")
        print("  - gemini    (Google Gemini API)")
        print("  - openai    (OpenAI API)")
        print("  - anthropic (Anthropic Claude API)")
        print()
        
        # Get provider
        provider = input("Enter provider name [gemini]: ").strip() or "gemini"
        
        # Check if key already exists
        existing_key = keyring.get_password("wp-ai", f"{provider}_api_key")
        if existing_key:
            print(f"\nNote: An API key for '{provider}' already exists.")
            overwrite = input("Do you want to overwrite it? (y/N): ").strip().lower()
            if overwrite not in ['y', 'yes']:
                print("Cancelled.")
                sys.exit(0)
        
        # Get API key
        print(f"\nEnter your {provider} API key:")
        print("(Input will be hidden for security)")
        api_key = getpass.getpass("> ").strip()
        
        if not api_key:
            print("Error: API key cannot be empty")
            sys.exit(1)
    
    # Save to keyring
    try:
        keyring.set_password("wp-ai", f"{provider}_api_key", api_key)
        print()
        print("=" * 43)
        print(f"✓ {provider} API Key saved successfully!")
        print("=" * 43)
        print()
        print(f"You can now use wp-ai with {provider} provider.")
        print("Run 'wp-ai --help' to see available commands.")
    except Exception as e:
        print(f"Error saving API key: {e}")
        sys.exit(1)
