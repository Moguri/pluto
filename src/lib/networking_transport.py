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
    def get_new_connections(self) -> Iterable[int]: ...
    def get_disconnects(self) -> Iterable[int]: ...
    def get_messages(self) -> Iterable[tuple[int, bytes]]: ...
    def send(self, message: bytes, connection_id: int | None = None) -> None: ...


@dataclass(kw_only=True)
class PandaNetworkTransport(NetworkTransport):
    num_threads: InitVar[int] = 0

    _manager: p3d.QueuedConnectionManager = field(init=False)
    _listener: p3d.QueuedConnectionListener = field(init=False)
    _reader: p3d.QueuedConnectionReader = field(init=False)
    _writer: p3d.ConnectionWriter = field(init=False)
    _is_started: bool = field(init=False, default=False)
    _connections: dict[int, p3d.Connection] = field(init=False, default_factory=dict)
    _next_id: int = field(init=False, default=0)

    def __post_init__(self, num_threads: int) -> None:
        self._manager = p3d.QueuedConnectionManager()
        self._writer = p3d.ConnectionWriter(self._manager, num_threads)
        self._reader = p3d.QueuedConnectionReader(self._manager, num_threads)
        self._listener = p3d.QueuedConnectionListener(self._manager, num_threads)

    def start_server(self, port: int) -> None:
        if self._is_started:
            raise RuntimeError('Cannot start as server: already started')

        conn = self._manager.open_TCP_server_rendezvous(port, 100)
        if conn is None:
            raise RuntimeError('Failed to open listen connection. Is the address already in use?')
        self._listener.add_connection(conn)

        self._is_started = True
        print('Server started and waiting for connections')

    def start_client(self, host: str, port: int) -> None:
        if self._is_started:
            raise RuntimeError('Cannot start as client: already started')

        conn = self._manager.open_TCP_client_connection(host, port, 3000)

        if conn:
            conn.set_no_delay(True)
            self._connections[self._next_id] = conn
            self._next_id += 1
            self._reader.add_connection(conn)
            self._is_started = True
            print(f'Client connected to server: {conn.get_address()}')
        else:
            raise RuntimeError(f'Failed to connect to server at {host}:{port}')

    def get_new_connections(self) -> Iterable[int]:
        conn_ptr = p3d.PointerToConnection()
        new_conn_ids = []

        while self._listener.new_connection_available():
            self._listener.get_new_connection(conn_ptr)
            new_conn = conn_ptr.p()
            new_conn.set_no_delay(True)
            print(f'Server received a new connection: {new_conn.get_address()}')
            new_conn_ids.append(self._next_id)
            self._connections[self._next_id] = new_conn
            self._next_id += 1
            self._reader.add_connection(new_conn)

        return new_conn_ids

    def get_disconnects(self) -> Iterable[int]:
        conn_ptr = p3d.PointerToConnection()
        dc_conn_ids = []

        try:
            while self._manager.reset_connection_available():
                self._manager.get_reset_connection(conn_ptr)
                rst_conn = conn_ptr.p()
                conn_id = list(self._connections.keys())[
                    list(self._connections.values()).index(rst_conn)
                ]
                dc_conn_ids.append(conn_id)
                self._manager.close_connection(rst_conn)
                del self._connections[conn_id]
                print(f'Connection disconnected: {conn_id}')
        except AssertionError:
            pass

        return dc_conn_ids

    def get_messages(self) -> Iterable[tuple[int, bytes]]:
        if not self._reader:
            return []

        messages: list[tuple[int, bytes]] = []
        while self._reader.data_available():
            datagram = p3d.NetDatagram()
            if self._reader.get_data(datagram):
                msg = PyDatagramIterator(datagram)
                conn = datagram.get_connection()
                connectionid = list(self._connections.keys())[
                    list(self._connections.values()).index(conn)
                ]
                messages.append((connectionid, msg.get_blob()))

        return messages

    def send(self, message: bytes, connection_id: int | None = None) -> None:
        connections = self._connections.values()
        if connection_id is not None:
            connections = [self._connections[connection_id]]
        datagram = PyDatagram()
        datagram.add_blob(message)
        for conn in connections:
            self._writer.send(datagram, conn)
