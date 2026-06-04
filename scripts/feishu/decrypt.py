"""飞书事件回调解密（官方算法：base64(iv + ciphertext)）。"""
from __future__ import annotations

import base64
import hashlib
import json

from Crypto.Cipher import AES


def _unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad = data[-1]
    if pad < 1 or pad > AES.block_size:
        raise ValueError("invalid padding")
    return data[:-pad]


def decrypt_event(encrypt_key: str, cipher_text: str) -> dict:
    """
    飞书官方解密：
    1. key = SHA256(encrypt_key)
    2. data = base64_decode(cipher_text)
    3. iv = data[:16], encrypted = data[16:]
    4. AES-256-CBC 解密 + PKCS7 unpad
    """
    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    enc = base64.b64decode(cipher_text)
    if len(enc) <= AES.block_size:
        raise ValueError("密文过短")
    iv = enc[: AES.block_size]
    encrypted = enc[AES.block_size :]
    plain = _unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(encrypted))
    return json.loads(plain.decode("utf-8"))
