[06092026]

Confirmed. The error is literally: the input length exceeds the context length. bge-m3's 8,192-token limit, and Chinese tokenizes inefficiently (≈1 token per char in worst case).

