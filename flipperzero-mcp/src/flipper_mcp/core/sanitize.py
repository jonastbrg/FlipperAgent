"""Input sanitization for CLI commands sent to Flipper Zero."""
import re

# Characters that could enable CLI injection
_DANGEROUS_CHARS = re.compile(r'[;&|`$(){}\[\]\\<>!#]')

# Maximum CLI command length (Flipper buffer limit)
MAX_CLI_LENGTH = 512


def sanitize_cli_input(command: str) -> str:
    """Strip dangerous characters from CLI command input.

    Removes shell metacharacters that could enable command injection
    on the Flipper CLI. Also enforces max length.

    Args:
        command: Raw CLI command string
    Returns:
        Sanitized command string
    Raises:
        ValueError: If command is empty after sanitization or too long
    """
    cleaned = _DANGEROUS_CHARS.sub('', command)
    cleaned = cleaned.strip()
    if not cleaned:
        raise ValueError("CLI command is empty after sanitization")
    if len(cleaned) > MAX_CLI_LENGTH:
        raise ValueError(f"CLI command exceeds {MAX_CLI_LENGTH} chars")
    return cleaned


def sanitize_args_for_log(arguments: dict) -> dict:
    """Sanitize tool arguments for audit logging.

    Truncates long values and redacts potential secrets.
    """
    sanitized = {}
    for key, value in arguments.items():
        if isinstance(value, str):
            # Redact anything that looks like a key/token
            if any(s in key.lower() for s in ('key', 'token', 'secret', 'password')):
                sanitized[key] = '[REDACTED]'
            elif len(value) > 200:
                sanitized[key] = value[:200] + '...'
            else:
                sanitized[key] = value
        else:
            sanitized[key] = value
    return sanitized
