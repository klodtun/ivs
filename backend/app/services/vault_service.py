import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.config import settings


class VaultService:
    def __init__(self):
        self._fernet = self._create_fernet(settings.VAULT_KEY)

    def _create_fernet(self, key: str) -> Fernet:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"ivs-vault-salt-v1",
            iterations=480000,
        )
        derived = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        return Fernet(derived)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def mask_value(self, value: str) -> str:
        if len(value) <= 8:
            return "****"
        return value[:4] + "*" * (len(value) - 8) + value[-4:]

    def build_env_dict(self, vault_keys: list) -> dict:
        env = {}
        for vk in vault_keys:
            env_name = f"{vk.provider.upper()}_{vk.name.upper().replace(' ', '_')}"
            env[env_name] = self.decrypt(vk.encrypted_value)
        return env


vault_service = VaultService()
