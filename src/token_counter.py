from typing import List
import tiktoken


class TokenCounter:
    """
    Tiktoken-based token counter for text analysis.

    Provides token counting functionality using the tiktoken library
    with GPT-4o encoding for accurate token estimation.
    """

    def __init__(self):
        """
        Initialize the token counter with GPT-4o encoding.

        Sets up the tiktoken encoder using the GPT-4o model encoding
        for consistent token counting across the application.
        """
        self.encoder = tiktoken.encoding_for_model("gpt-4o")

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text.

        Uses the configured tiktoken encoder to determine the exact
        number of tokens that would be used for the input text.

        Args:
            text (str): The text to count tokens for

        Returns:
            int: Number of tokens in the text
        """
        return len(self.encoder.encode(text))
