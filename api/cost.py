"""Model pricing configuration and token cost calculator."""

from typing import Final

# Pricing in USD per 1 Million tokens (input, output)
MODEL_PRICE_TABLE: Final[dict[str, tuple[float, float]]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "openai/gpt-oss-20b": (0.08, 0.30),
    "qwen/qwen3.8-27b": (0.10, 0.40),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "mock-logistics-v1": (0.05, 0.20),
}

DEFAULT_PRICING: Final[tuple[float, float]] = (0.15, 0.60)


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute the estimated USD cost based on token counts and model price card."""
    clean_model = model.split(":")[-1].strip().lower()
    in_price, out_price = MODEL_PRICE_TABLE.get(clean_model, DEFAULT_PRICING)

    in_cost = (input_tokens / 1_000_000.0) * in_price
    out_cost = (output_tokens / 1_000_000.0) * out_price
    return round(in_cost + out_cost, 6)

