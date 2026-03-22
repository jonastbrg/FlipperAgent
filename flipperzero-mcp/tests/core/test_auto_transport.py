import pytest

from flipper_mcp.core.transport.auto import AutoTransport


class _StubTransport:
    """
    Minimal stub transport with a connect result.
    Used to monkeypatch USBTransport/WiFiTransport inside AutoTransport.
    """

    def __init__(self, config: dict, *, name: str, connect_ok: bool):
        self._config = config
        self._name = name
        self._connect_ok = connect_ok
        self._connected = False

    async def connect(self) -> bool:
        self._connected = bool(self._connect_ok)
        return self._connected

    async def disconnect(self) -> None:
        self._connected = False

    async def send(self, data: bytes) -> None:  # pragma: no cover
        raise NotImplementedError

    async def receive(self, timeout=None) -> bytes:  # pragma: no cover
        raise NotImplementedError

    async def is_connected(self) -> bool:
        return bool(self._connected)

    def get_name(self) -> str:
        return self._name


@pytest.mark.asyncio
async def test_auto_prefers_usb_even_if_wifi_configured(monkeypatch):
    from flipper_mcp.core.transport import auto as auto_mod

    def _usb(_cfg: dict):
        return _StubTransport(_cfg, name="USB", connect_ok=True)

    def _wifi(_cfg: dict):
        return _StubTransport(_cfg, name="WiFi", connect_ok=True)

    monkeypatch.setattr(auto_mod, "USBTransport", _usb)
    monkeypatch.setattr(auto_mod, "WiFiTransport", _wifi)

    t = AutoTransport({"usb": {}, "wifi": {"host": "192.168.1.100", "port": 8080}})
    assert await t.connect() is True
    assert t.get_name() == "USB"
    assert await t.is_connected() is True


@pytest.mark.asyncio
async def test_auto_falls_back_to_wifi_when_usb_fails_and_wifi_configured(monkeypatch):
    from flipper_mcp.core.transport import auto as auto_mod

    def _usb(_cfg: dict):
        return _StubTransport(_cfg, name="USB", connect_ok=False)

    def _wifi(_cfg: dict):
        return _StubTransport(_cfg, name="WiFi", connect_ok=True)

    monkeypatch.setattr(auto_mod, "USBTransport", _usb)
    monkeypatch.setattr(auto_mod, "WiFiTransport", _wifi)

    t = AutoTransport({"usb": {}, "wifi": {"host": "192.168.1.100", "port": 8080}})
    assert await t.connect() is True
    assert t.get_name() == "WiFi"


@pytest.mark.asyncio
async def test_auto_does_not_try_wifi_when_host_not_set(monkeypatch):
    from flipper_mcp.core.transport import auto as auto_mod

    def _usb(_cfg: dict):
        return _StubTransport(_cfg, name="USB", connect_ok=False)

    def _wifi(_cfg: dict):  # pragma: no cover
        raise AssertionError("WiFiTransport should not be constructed when host is not set")

    monkeypatch.setattr(auto_mod, "USBTransport", _usb)
    monkeypatch.setattr(auto_mod, "WiFiTransport", _wifi)

    t = AutoTransport({"usb": {}, "wifi": {"port": 8080}})
    assert await t.connect() is False
    assert t.get_name() == "Auto"
    assert await t.is_connected() is False



