"""The utf8-byte-v1 tokenizer shared by the proposed Rust contract."""

BOS, EOS, PAD = 256, 257, 258
VOCAB_SIZE = 259


def encode(text: str) -> list[int]:
    return list(text.encode("utf-8"))


def decode(tokens: list[int]) -> str:
    if any(type(t) is not int or not 0 <= t < VOCAB_SIZE for t in tokens):
        raise ValueError("Token IDs must be integers in [0, 259)")
    return bytes(t for t in tokens if t < 256).decode("utf-8", errors="replace")
