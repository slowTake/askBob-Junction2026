"""Tokens one question used, added up over the model requests it took. Pure.

Input tokens come in three kinds, priced differently: read from the provider's prompt
cache, written to it, and neither. `input_tokens` is the "neither" part for every provider.
"""

from dataclasses import asdict, dataclass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    requests: int = 0
    # Requests the provider re-ran on another model after a refusal. Their tokens are
    # billed at that model's price, so the question's cost is not one model's price.
    fallback_requests: int = 0

    def add(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        fallback: bool = False,
    ) -> None:
        """Count one model request."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cache_read_tokens += cache_read_tokens
        self.cache_write_tokens += cache_write_tokens
        self.requests += 1
        self.fallback_requests += fallback

    @property
    def total_input_tokens(self) -> int:
        """Everything the model read, cached or not."""
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    def as_dict(self) -> dict[str, int]:
        return asdict(self)
