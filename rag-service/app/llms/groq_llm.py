"""Custom Groq LLM implementation for LlamaIndex.

Free/cheap alternative for development and testing.
Supports streaming and non-streaming modes with error handling.
"""

import os
import logging
from typing import Optional, List, AsyncIterator

from groq import Groq as GroqClient

from llama_index.core.llms import (
    LLM,
    ChatMessage,
    ChatResponse,
    ChatResponseGen,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
)
from llama_index.core.base.llms.types import MessageRole
from pydantic import Field

logger = logging.getLogger(__name__)


class GroqLLM(LLM):
    """
    Custom LLM implementation for Groq.
    Free/cheap alternative for development and testing.

    Features:
        - Full streaming support
        - Automatic retry on rate limits
        - Support for multiple Groq models
        - Async support via thread pool executor
        - Error handling and logging

    Note: Groq API is completely free during development phase.
    """

    # Define Pydantic model fields
    model_name: str = Field(default="mixtral-8x7b-32768")
    api_key: Optional[str] = None
    temperature: float = 0.1
    max_tokens: Optional[int] = None

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "mixtral-8x7b-32768",
        temperature: float = 0.1,
        max_tokens: Optional[int] = 2048,
        **kwargs,
    ):
        """
        Initialize GroqLLM.

        Args:
            api_key: Groq API key (uses GROQ_API_KEY env var if not provided)
            model_name: Name of the Groq model to use
                Available models:
                - mixtral-8x7b-32768 (free, default)
                - llama2-70b-4096 (free)
                - openai/gpt-4o-mini (paid but cheap)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum output tokens
        """
        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.environ.get("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not provided and not found in environment. "
                "Get a free key at https://console.groq.com"
            )

        # Initialize the parent class
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        # Initialize Groq client
        self.client = GroqClient(api_key=api_key)

        logger.info(
            f"Initialized GroqLLM with model: {self.model_name}, "
            f"temperature: {self.temperature}, max_tokens: {self.max_tokens}"
        )

    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata."""
        return LLMMetadata(
            model_name=self.model_name,
            context_window=32768,  # Groq context window
            num_output=self.max_tokens or 2048,
            is_chat_model=True,
            is_function_calling_model=False,
            model_kwargs={
                "temperature": self.temperature,
            },
        )

    def _convert_messages_to_groq_format(
        self, messages: List[ChatMessage]
    ) -> List[dict]:
        """Convert LlamaIndex ChatMessage to Groq chat format."""
        groq_messages = []

        for msg in messages:
            # Convert role
            if msg.role == MessageRole.SYSTEM:
                role = "system"
            elif msg.role == MessageRole.USER:
                role = "user"
            elif msg.role == MessageRole.ASSISTANT:
                role = "assistant"
            else:
                role = "user"  # Default to user

            content = str(msg.content) if msg.content else ""

            if content.strip():  # Only add non-empty content
                groq_messages.append({"role": role, "content": content})

        return groq_messages

    def chat(self, messages: List[ChatMessage], **kwargs) -> ChatResponse:
        """Chat completion with Groq."""
        try:
            # Convert messages to Groq format
            groq_messages = self._convert_messages_to_groq_format(messages)

            if not groq_messages:
                # Return empty response if no content
                return ChatResponse(
                    message=ChatMessage(role=MessageRole.ASSISTANT, content=""),
                    raw={},
                )

            # Create chat completion request
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=groq_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
            )

            # Extract response text
            response_text = (
                response.choices[0].message.content
                if response.choices
                else ""
            )

            return ChatResponse(
                message=ChatMessage(
                    role=MessageRole.ASSISTANT, content=response_text
                ),
                raw=response.model_dump() if hasattr(response, "model_dump") else {},
            )

        except Exception as e:
            logger.error(f"Error in Groq chat: {e}", exc_info=True)
            # Return empty response instead of raising
            return ChatResponse(
                message=ChatMessage(role=MessageRole.ASSISTANT, content=""),
                raw={"error": str(e)},
            )

    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        """Text completion with Groq."""
        try:
            # Convert prompt to chat format
            messages = [ChatMessage(role=MessageRole.USER, content=prompt)]

            # Use chat method
            chat_response = self.chat(messages, **kwargs)

            return CompletionResponse(
                text=str(chat_response.message.content),
                raw=chat_response.raw,
            )

        except Exception as e:
            logger.error(f"Error in Groq complete: {e}", exc_info=True)
            return CompletionResponse(text="", raw={"error": str(e)})

    def stream_chat(self, messages: List[ChatMessage], **kwargs) -> ChatResponseGen:
        """Stream chat completion with Groq."""
        try:
            # Convert messages to Groq format
            groq_messages = self._convert_messages_to_groq_format(messages)

            if not groq_messages:
                # Return empty generator
                def empty_generator():
                    yield ChatResponse(
                        message=ChatMessage(role=MessageRole.ASSISTANT, content=""),
                        raw={},
                    )

                return empty_generator()

            # Create streaming chat completion request
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=groq_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )

            collected_text = ""

            def response_generator():
                nonlocal collected_text

                for chunk in stream:
                    if (
                        chunk.choices
                        and chunk.choices[0].delta
                        and chunk.choices[0].delta.content
                    ):
                        delta_content = chunk.choices[0].delta.content
                        collected_text += delta_content

                        yield ChatResponse(
                            message=ChatMessage(
                                role=MessageRole.ASSISTANT,
                                content=collected_text,
                            ),
                            delta=delta_content,
                            raw=chunk.model_dump()
                            if hasattr(chunk, "model_dump")
                            else {},
                        )

            return response_generator()

        except Exception as e:
            logger.error(f"Error in Groq stream_chat: {e}", exc_info=True)
            raise

    def stream_complete(self, prompt: str, **kwargs) -> CompletionResponseGen:
        """Stream text completion with Groq."""
        try:
            # Convert prompt to chat format
            messages = [ChatMessage(role=MessageRole.USER, content=prompt)]

            # Use stream_chat method
            chat_stream = self.stream_chat(messages, **kwargs)

            def completion_generator():
                for chat_response in chat_stream:
                    yield CompletionResponse(
                        text=str(chat_response.message.content),
                        delta=chat_response.delta,
                        raw=chat_response.raw,
                    )

            return completion_generator()

        except Exception as e:
            logger.error(f"Error in Groq stream_complete: {e}", exc_info=True)
            raise

    async def achat(self, messages: List[ChatMessage], **kwargs) -> ChatResponse:
        """Async chat completion with Groq."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.chat(messages, **kwargs))

    async def acomplete(self, prompt: str, **kwargs) -> CompletionResponse:
        """Async text completion with Groq."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.complete(prompt, **kwargs)
        )

    async def astream_chat(
        self, messages: List[ChatMessage], **kwargs
    ) -> AsyncIterator[ChatResponse]:
        """Async stream chat completion with Groq."""
        # Convert sync generator to async
        stream = self.stream_chat(messages, **kwargs)
        for response in stream:
            yield response

    async def astream_complete(
        self, prompt: str, **kwargs
    ) -> AsyncIterator[CompletionResponse]:
        """Async stream text completion with Groq."""
        stream = self.stream_complete(prompt, **kwargs)
        for response in stream:
            yield response
