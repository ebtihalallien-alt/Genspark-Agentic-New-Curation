
import os
from typing import List, Dict

from groq import Groq


class ModelClient:
    """Base interface for language model clients."""

    def generate(self, messages: List[Dict[str, str]]) -> str:
        raise NotImplementedError(
            "Subclasses must implement generate()."
        )


class GroqModelClient(ModelClient):
    """Language model client using the Groq API."""

    def __init__(
        self,
        api_key: str = None,
        model: str = "openai/gpt-oss-120b",
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")

        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not configured."
            )

        self.model = model
        self.client = Groq(api_key=self.api_key)

    def generate(self, messages: List[Dict[str, str]]) -> str:
        if not isinstance(messages, list) or not messages:
            raise ValueError(
                "messages must be a non-empty list."
            )

        allowed_roles = {"system", "user", "assistant"}

        for message in messages:
            if not isinstance(message, dict):
                raise ValueError(
                    "Each message must be a dictionary."
                )

            if message.get("role") not in allowed_roles:
                raise ValueError("Invalid message role.")

            if not isinstance(message.get("content"), str):
                raise ValueError(
                    "Message content must be a string."
                )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_tokens=600,
        )

        content = response.choices[0].message.content

        if not content or not content.strip():
            raise RuntimeError(
                "The model returned an empty response."
            )

        return content.strip()
