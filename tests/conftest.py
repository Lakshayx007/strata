import os

# Tests never touch a real database or network; a fixed salt keeps author hashes deterministic.
os.environ.setdefault("AUTHOR_HASH_SALT", "test-salt")
