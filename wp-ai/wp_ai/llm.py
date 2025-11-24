import google.generativeai as genai
from .config import get_api_key, LLMConfig

class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = get_api_key(config.provider)
        if not self.api_key:
            raise ValueError(f"API Key for {config.provider} not found. Please set it using 'wp-ai init' or environment variable.")

        if config.provider == "gemini":
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(config.model)
        else:
            # TODO: Implement OpenAI
            raise NotImplementedError(f"Provider {config.provider} not yet implemented.")

    def generate_content(self, prompt: str) -> str:
        """Generate content from the LLM."""
        if self.config.provider == "gemini":
            response = self.model.generate_content(prompt)
            return response.text
        return ""
    
    def generate_content_stream(self, messages: list):
        """Generate content from the LLM with streaming support.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            
        Yields:
            bytes: Chunks of the response as they arrive
        """
        if self.config.provider == "gemini":
            # Convert messages to Gemini format
            # For Gemini, we need to build a conversation history
            # System message is handled separately, user/assistant messages go in history
            
            # Extract system message if present
            system_instruction = None
            conversation_parts = []
            
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    system_instruction = content
                elif role == "user":
                    conversation_parts.append({"role": "user", "parts": [content]})
                elif role == "assistant":
                    conversation_parts.append({"role": "model", "parts": [content]})
            
            # Use streaming generate_content
            try:
                # If we have system instruction, we should recreate the model with it
                if system_instruction:
                    import google.generativeai as genai
                    model = genai.GenerativeModel(
                        self.config.model,
                        system_instruction=system_instruction
                    )
                else:
                    model = self.model
                
                # For streaming, we pass the full conversation history
                if conversation_parts:
                    response = model.generate_content(conversation_parts, stream=True)
                    
                    for chunk in response:
                        if chunk.text:
                            yield chunk.text.encode('utf-8')
                else:
                    yield b""
            except Exception as e:
                error_msg = f"Streaming error: {str(e)}"
                yield error_msg.encode('utf-8')
        else:
            # TODO: Implement OpenAI streaming
            yield b"Streaming not implemented for this provider"
