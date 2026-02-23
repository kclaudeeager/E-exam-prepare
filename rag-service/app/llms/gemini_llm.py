"""Custom Google Gemini LLM implementation for LlamaIndex.

Multiprocessing-safe with thread-local client storage and error handling.
Supports both chat and text completion modes.
"""

import os
import logging
import time
from typing import Optional, List, AsyncIterator, Any, Dict
from threading import local

from google import genai
from google.genai import types
from google.genai.errors import ServerError

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

# Thread-local storage for clients - each thread/process gets its own client
_thread_local = local()


class GoogleGeminiLLM(LLM):
    """
    Custom LLM implementation for Google Gemini.
    Thread-safe and multiprocessing-safe with lazy initialization.
    Includes rate limiting and error handling.

    Features:
        - Thread-local client storage for multiprocessing safety
        - Automatic retry with exponential backoff on server errors
        - Support for system prompts
        - Streaming and non-streaming modes
        - Async support via thread pool executor
    """

    # Define Pydantic model fields
    model_name: str = Field(default="gemini-2.0-flash")
    api_key: Optional[str] = None
    temperature: float = 0.1
    max_tokens: Optional[int] = None
    max_retries: int = 3
    retry_delay: float = 2.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.0-flash",
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        **kwargs,
    ):
        """
        Initialize GoogleGeminiLLM.

        Args:
            api_key: Google API key (uses GOOGLE_API_KEY env var if not provided)
            model_name: Name of the Gemini model to use
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum output tokens
            max_retries: Number of retries on server errors
            retry_delay: Delay between retries in seconds
        """
        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.environ.get("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not provided and not found in environment"
            )

        # Initialize the parent class with proper fields
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
            retry_delay=retry_delay,
            **kwargs,
        )

        # Store API key for client initialization
        self._api_key = api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        logger.info(
            f"Initialized GoogleGeminiLLM with model: {self.model_name}, "
            f"temperature: {self.temperature}, max_tokens: {self.max_tokens}"
        )

    @property
    def client(self) -> genai.Client:
        """
        Get a thread/process-local Gemini client.
        Each worker process gets its own independent client instance.
        """
        import threading

        thread_id = threading.get_ident()
        process_id = os.getpid()
        thread_key = f"gemini_client_{process_id}_{thread_id}_{id(self)}"

        if not hasattr(_thread_local, thread_key):
            # Create a new client for this thread/process
            client = genai.Client(api_key=self._api_key)
            setattr(_thread_local, thread_key, client)
            logger.debug(
                f"Created new Gemini client for process {process_id}, thread {thread_id}"
            )

        return getattr(_thread_local, thread_key)

    def __getstate__(self) -> Dict[str, Any]:
        """Custom pickling for multiprocessing."""
        state = self.__dict__.copy()
        # Don't pickle thread-local storage, it will be recreated
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Custom unpickling for multiprocessing."""
        self.__dict__.update(state)
        # Thread-local storage will be recreated when client property is accessed

    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata."""
        return LLMMetadata(
            model_name=self.model_name,
            context_window=32768,  # Gemini context window
            num_output=self.max_tokens or 2048,
            is_chat_model=True,
            is_function_calling_model=True,
            model_kwargs={
                "temperature": self.temperature,
            },
        )

    def _convert_messages_to_gemini_contents(
        self, messages: List[ChatMessage]
    ) -> List[types.Content]:
        """Convert LlamaIndex ChatMessage to Gemini Contents."""
        contents = []

        for msg in messages:
            role = "user" if msg.role == MessageRole.USER else "model"
            content_text = str(msg.content) if msg.content else ""
            if content_text.strip():  # Only add non-empty content
                contents.append(
                    types.Content(
                        role=role, parts=[types.Part.from_text(text=content_text)]
                    )
                )

        return contents

    def _create_gemini_config(
        self, system_prompt: Optional[str] = None
    ) -> types.GenerateContentConfig:
        """Create Gemini configuration."""
        config = types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )

        if system_prompt:
            config.system_instruction = system_prompt

        return config

    def _retry_with_backoff(self, func, *args, **kwargs):
        """Retry function with exponential backoff."""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except ServerError as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)  # Exponential backoff
                    logger.warning(
                        f"Server error (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed after {self.max_retries} attempts: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise
        return None

    def chat(self, messages: List[ChatMessage], **kwargs) -> ChatResponse:
        """Chat completion with Gemini with retry logic."""
        try:
            # Extract system prompt if present
            system_prompt = None
            if messages and messages[0].role == MessageRole.SYSTEM:
                system_prompt = str(messages[0].content)
                messages = messages[1:]  # Remove system message from chat

            # Convert messages to Gemini format
            contents = self._convert_messages_to_gemini_contents(messages)

            if not contents:
                # Return empty response if no content
                return ChatResponse(
                    message=ChatMessage(role=MessageRole.ASSISTANT, content=""),
                    raw={},
                )

            # Create config
            config = self._create_gemini_config(system_prompt)

            # Generate response with retry logic
            def make_request():
                return self.client.models.generate_content(
                    model=self.model_name, contents=contents, config=config
                )

            response = self._retry_with_backoff(make_request)

            # Extract text from response
            if (
                response
                and response.candidates
                and response.candidates[0].content
            ):
                response_text = response.candidates[0].content.parts[0].text
            else:
                response_text = ""

            # Create ChatResponse
            return ChatResponse(
                message=ChatMessage(role=MessageRole.ASSISTANT, content=response_text),
                raw=response.__dict__ if hasattr(response, "__dict__") else str(response),
            )

        except Exception as e:
            logger.error(f"Error in Gemini chat: {e}", exc_info=True)
            # Return empty response instead of raising to allow pipeline to continue
            return ChatResponse(
                message=ChatMessage(role=MessageRole.ASSISTANT, content=""),
                raw={"error": str(e)},
            )

    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        """Text completion with Gemini."""
        try:
            # Convert prompt to chat format
            messages = [ChatMessage(role=MessageRole.USER, content=prompt)]

            # Use chat method
            chat_response = self.chat(messages, **kwargs)

            # Convert to CompletionResponse
            return CompletionResponse(
                text=str(chat_response.message.content), raw=chat_response.raw
            )

        except Exception as e:
            logger.error(f"Error in Gemini complete: {e}", exc_info=True)
            return CompletionResponse(text="", raw={"error": str(e)})

    def stream_chat(self, messages: List[ChatMessage], **kwargs) -> ChatResponseGen:
        """Stream chat completion with Gemini."""
        try:
            # Extract system prompt if present
            system_prompt = None
            if messages and messages[0].role == MessageRole.SYSTEM:
                system_prompt = str(messages[0].content)
                messages = messages[1:]  # Remove system message

            # Convert messages to Gemini format
            contents = self._convert_messages_to_gemini_contents(messages)

            # Create config
            config = self._create_gemini_config(system_prompt)

            # Generate stream using thread-local client
            stream = self.client.models.generate_content_stream(
                model=self.model_name, contents=contents, config=config
            )

            # Process stream
            collected_text = ""

            def response_generator():
                nonlocal collected_text

                for chunk in stream:
                    if chunk.text:
                        collected_text += chunk.text
                        yield ChatResponse(
                            message=ChatMessage(
                                role=MessageRole.ASSISTANT, content=collected_text
                            ),
                            delta=chunk.text,
                            raw=(
                                chunk.__dict__
                                if hasattr(chunk, "__dict__")
                                else str(chunk)
                            ),
                        )

            return response_generator()

        except Exception as e:
            logger.error(f"Error in Gemini stream_chat: {e}", exc_info=True)
            raise

    def stream_complete(self, prompt: str, **kwargs) -> CompletionResponseGen:
        """Stream text completion with Gemini."""
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
            logger.error(f"Error in Gemini stream_complete: {e}", exc_info=True)
            raise

    async def achat(self, messages: List[ChatMessage], **kwargs) -> ChatResponse:
        """Async chat completion with Gemini."""
        # Gemini client doesn't have async support in current version
        # So we'll run sync version in thread pool
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.chat(messages, **kwargs))

    async def acomplete(self, prompt: str, **kwargs) -> CompletionResponse:
        """Async text completion with Gemini."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.complete(prompt, **kwargs)
        )

    async def astream_chat(
        self, messages: List[ChatMessage], **kwargs
    ) -> AsyncIterator[ChatResponse]:
        """Async stream chat completion with Gemini."""
        # Convert sync generator to async
        stream = self.stream_chat(messages, **kwargs)
        for response in stream:
            yield response

    async def astream_complete(
        self, prompt: str, **kwargs
    ) -> AsyncIterator[CompletionResponse]:
        """Async stream text completion with Gemini."""
        stream = self.stream_complete(prompt, **kwargs)
        for response in stream:
            yield response
