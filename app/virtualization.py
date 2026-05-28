from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.backends import default_backend
import re,json

KEY = b"32-bytes-secret-key-123456789012"
NONCE = b"\x00" * 16  # deterministic

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = 62

def base62_encode(data: bytes) -> str:
  num = int.from_bytes(data, "big")
  if num == 0: return ALPHABET[0]

  out = []
  while num:
    num, rem = divmod(num, BASE)
    out.append(ALPHABET[rem])

  return "".join(reversed(out))

def base62_decode(s: str) -> bytes:
  num = 0
  for c in s: num = num * BASE + ALPHABET.index(c)

  length = (num.bit_length() + 7) // 8
  return num.to_bytes(length, "big")

def encode(label: str,key:bytes) -> str:
  cipher = Cipher(
    algorithms.ChaCha20(key, NONCE),
    mode=None,
    backend=default_backend()
  )
  enc = cipher.encryptor()
  ct = enc.update(label.encode())
  return base62_encode(ct)

def decode(token: str,key:bytes) -> str:
  try:
    raw = base62_decode(token)
    cipher = Cipher(
      algorithms.ChaCha20(KEY, NONCE),
      mode=None,
      backend=default_backend()
    )
    dec = cipher.decryptor()
    out = dec.update(raw).decode()
    return out
  except UnicodeDecodeError: raise ValueError(f"key is not match!")
  except ValueError: raise ValueError("Key Size is not same!")

def add_prefix(token:str): return f"[\\{token}/]"

def get_token(key:bytes):
  text = f"""
    Lorem Ipsum is simply dummy text of the printing and typesetting industry.
    Lorem Ipsum has been the industry's standard dummy text ever since the 1500s,
    when an unknown printer took a galley of type and [\\HOUxOnvDMIvnBxJy/] it to make a type specimen book.
    It has survived not only five scrambled, but also the leap into electronic typesetting,
    remaining essentially [\\HOUxOnvDMIvnBxJy/]. It was popularised in the 1960s with the release of Letraset sheets containing Lorem Ipsum passages,
    and more recently with desktop publishing software like Aldus PageMaker including versions of Lorem Ipsum.
    hello world and this is from and this and he be before [\\HOUxOnvDMIvnBxJy/] 
  """
  pattern = r"\[\\([A-Za-z0-9]+)\/\]"

  matches = re.findall(pattern, text)
  if not matches: raise ValueError("Not Matching ...")
  outs = {}
  data = set(matches)
  for d in data: text = text.replace(f"[\\{d}/]",decode(d,key))

  return text

if __name__ == "__main__":
  text = "TH-01-Z01-D1"
  token = encode(text,KEY)
  print(get_token(KEY))

