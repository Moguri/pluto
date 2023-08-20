from dataclasses import (
    dataclass,
    field,
    InitVar,
)

from typing import (
    Iterable,
    Protocol,
)

import panda3d.core as p3d
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.PyDatagramIterator import PyDatagramIterator


class NetworkTransport(Protocol):
    def start_server(self, port: int) -> None: ...
    def start_client(self, host: str, port: int) -> None: ...
    def update(self) -> None: ...
    def get_messages(self) -> Iterable[bytes]: ...
    def send(self, message: bytes, connection_id: int | None = None) -> None: ...


@dataclass(kw_only=True)
class PandaNetworkTransport(NetworkTransport):
    num_threads: InitVar[int] = 0

    _manager: p3d.QueuedConnectionManager = field(init=False)
    _listener: p3d.QueuedConnectionListener | None = field(init=False, default=None)
    _reader: p3d.QueuedConnectionReader | None = field(init=False)
    _writer: p3d.ConnectionWriter = field(init=False)
    _is_started: bool = field(init=False, default=False)
    _connections: list[p3d.Connection] = field(init=False, default_factory=list)

    def __post_init__(self, num_threads) -> None:
        self._manager = p3d.QueuedConnectionManager()
        self._writer = p3d.ConnectionWriter(self._manager, num_threads)
        self._reader = p3d.QueuedConnectionReader(self._manager, num_threads)
        self._listener = p3d.QueuedConnectionListener(self._manager, num_threads)

    def start_server(self, port: int) -> None:
        if self._is_started:
            raise RuntimeError('Cannot start as server: already started')

        conn = self._manager.open_TCP_server_rendezvous(port, 100)
        self._listener.add_connection(conn)

        self._is_started = True
        print('Server started and waiting for connections')

    def start_client(self, host: str, port: int) -> None:
        if self._is_started:
            raise RuntimeError('Cannot start as client: already started')

        conn = self._manager.open_TCP_client_connection(host, port, 3000)

        if conn:
            conn.set_no_delay(True)
            self._connections.append(conn)
            self._reader.add_connection(conn)
            self._is_started = True
            print(f'Client connected to server: {conn.get_address()}')
        else:
            raise RuntimeError(f'Failed to connect to server at {host}:{port}')

    def update(self) -> None:
        if not self._listener.new_connection_available():
            return

        new_conn_ptr = p3d.PointerToConnection()

        while self._listener.get_new_connection(new_conn_ptr):
            new_conn = new_conn_ptr.p()
            new_conn.set_no_delay(True)
            print(f'Server received a new connection: {new_conn.get_address()}')
            self._connections.append(new_conn)
            self._reader.add_connection(new_conn)

    def get_messages(self) -> Iterable[bytes]:
        if not self._reader:
            return []

        messages: list[p3d.NetDatagram] = []
        while self._reader.data_available():
            datagram = p3d.NetDatagram()
            if self._reader.get_data(datagram):
                msg = PyDatagramIterator(datagram)
                messages.append(msg.get_blob())

        return messages

    def send(self, message: bytes, connection_id: int | None = None) -> None:
        connections = self._connections
        if connection_id is not None:
            connections = [self._connections[connection_id]]
        datagram = PyDatagram()
        datagram.add_blob(message)
        for conn in connections:
            self._writer.send(datagram, conn)
