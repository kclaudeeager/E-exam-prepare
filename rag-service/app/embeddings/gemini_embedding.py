"""Custom Gemini embedding function for LlamaIndex."""

import os
import logging
from typing import List, Optional
from google import genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class GeminiEmbeddingFunction:
    """
    Custom embedding function for LlamaIndex using Google Gemini.
    Converts text documents to embedding vectors using Gemini's embedding model.
    """

    def __init__(
        self,
        api_key: str = None,
        model_name: str = "models/embedding-001",
    ):
        """
        Initialize Gemini embedding function.

        Args:
            api_key: Google API key (uses GOOGLE_API_KEY env var if not provided)
            model_name: Name of the Gemini embedding model
        """
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable not set. "
                "Please set it to use GeminiEmbeddingFunction."
            )

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
        logger.info(
            f"Initialized GeminiEmbeddingFunction with model: {self.model_name}"
        )

    def __call__(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for input texts (LlamaIndex compatible).

        Args:
            texts: List of text documents to embed

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If embedding generation fails
        """
        try:
            if not texts or len(texts) == 0:
                logger.warning("Empty input provided to embedding function")
                return []

            logger.debug(f"Generating embeddings for {len(texts)} documents")

            # Generate embeddings for all documents at once
            response = self.client.models.embed_content(
                model=self.model_name, contents=texts
            )

            # Extract embedding vectors from response
            embeddings = [list(e.values) for e in response.embeddings]

            logger.debug(f"Successfully generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}", exc_info=True)
            raise ValueError(f"Failed to generate embeddings: {str(e)}")

    def get_text_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text (LlamaIndex compatible).

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        embeddings = self.__call__([text])
        return embeddings[0] if embeddings else []

    def get_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a query (LlamaIndex compatible).

        Args:
            query: Query text to embed

        Returns:
            Embedding vector
        """
        return self.get_text_embedding(query)

