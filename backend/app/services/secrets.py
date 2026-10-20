import json
import os
import stat

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings


class SecretsError(Exception):
    pass


def _key() -> bytes:
    env = os.environ.get("SECRETS_KEY", "").strip()
    if env:
        return env.encode()
    path = get_settings().data_dir / "secrets.key"
    if path.exists():
        return path.read_bytes().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key)
    return key


def encrypt(values: dict) -> str:
    if not values:
        return ""
    return Fernet(_key()).encrypt(json.dumps(values).encode()).decode()


def decrypt(token: str) -> dict:
    if not token:
        return {}
    try:
        return json.loads(Fernet(_key()).decrypt(token.encode()))
    except (InvalidToken, ValueError):
        raise SecretsError("No se pudieron descifrar las credenciales guardadas: la clave de cifrado cambió.")
