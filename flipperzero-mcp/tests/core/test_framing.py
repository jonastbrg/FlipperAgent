import struct

import pytest

from flipper_mcp.core.transport.base import FlipperTransport
from flipper_mcp.core.protobuf_rpc import ProtobufRPC
from flipper_mcp.core.protobuf_gen import flipper_pb2, system_pb2


class FakeTransport(FlipperTransport):
    """
    Deterministic fake transport that returns queued byte chunks from receive().
    """

    def __init__(self, chunks: list[bytes] | None = None):
        super().__init__({})
        self._chunks = list(chunks or [])
        self.sent = bytearray()

    async def connect(self) -> bool:
        self.connected = True
        return True

    async def disconnect(self) -> None:
        self.connected = False

    async def send(self, data: bytes) -> None:
        self.sent.extend(data)

    async def receive(self, timeout=None) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    async def is_connected(self) -> bool:
        return self.connected


def _frame(payload: bytes) -> bytes:
    # Nanopb-delimited framing: [varint length][payload]
    return ProtobufRPC._encode_varint(len(payload)) + payload


@pytest.mark.asyncio
async def test_receive_exact_handles_coalesced_reads():
    # Two frames coalesced into a single read.
    data = b"abcdef"
    t = FakeTransport([data])

    out1 = await t.receive_exact(2, timeout=0.01)
    out2 = await t.receive_exact(4, timeout=0.01)

    assert out1 == b"ab"
    assert out2 == b"cdef"


@pytest.mark.asyncio
async def test_receive_exact_handles_split_reads():
    # One logical payload split across multiple reads.
    t = FakeTransport([b"a", b"bcd", b"e"])
    out = await t.receive_exact(5, timeout=0.01)
    assert out == b"abcde"


@pytest.mark.asyncio
async def test_protobufrpc_receives_framed_main_message_with_split_prefix_and_payload():
    # Build a minimal response Main(system_ping_response)
    resp = flipper_pb2.Main()
    resp.command_id = 1
    resp.has_next = False
    resp.system_ping_response.CopyFrom(system_pb2.PingResponse(data=b"pong"))
    payload = resp.SerializeToString()
    framed = _frame(payload)

    # Split across multiple chunks, including splitting the varint length prefix.
    chunks = [framed[:1], framed[1:3], framed[3:6], framed[6:]]
    t = FakeTransport(chunks)
    rpc = ProtobufRPC(t)

    msg = await rpc._receive_main_message(timeout=0.01)
    assert msg is not None
    assert msg.HasField("system_ping_response")
    assert msg.system_ping_response.data == b"pong"


