from dataclasses import (
    dataclass,
    field,
    InitVar,
)
import sys

from direct.showbase.ShowBase import ShowBase
import panda3d.core as p3d

import eventmapper
import pman.shim
import simplepbr

from lib.gamestates import GameStateManager, StatesDict
from lib.networking import (
    NetworkManager,
    NetRole,
)

from game import gamestates
from game.network_messages import (
    PlayerInputMsg,
    PlayerUpdateMsg,
)


p3d.load_prc_file_data(
    '',
    'window-title Panda3D Game\n'
    'win-fixed-size true\n'
    'win-size 1280 720\n'
    'event-map-item-quit escape q\n'
    'event-map-item-move-up raw-w\n'
    'event-map-item-move-down raw-s\n'
    'event-map-item-move-left raw-a\n'
    'event-map-item-move-right raw-d\n'
)

CLIENT_STATES = {
    'Main': gamestates.MainClient,
}

SERVER_STATES = {
    'Main': gamestates.MainServer,
}


@dataclass
class NetworkGameStateManager:
    showbase: InitVar[ShowBase]
    client_states: InitVar[StatesDict]
    server_states: InitVar[StatesDict]
    network: NetworkManager
    client_gsm: GameStateManager | None = field(init=False)
    server_gsm: GameStateManager | None = field(init=False)

    def __post_init__(
            self,
            showbase: ShowBase,
            client_states: StatesDict,
            server_states: StatesDict,
    ) -> None:
        netrole = self.network.net_role
        if netrole == NetRole.DUAL or netrole == NetRole.CLIENT:
            self.client_gsm = GameStateManager(showbase, client_states)
        if netrole == NetRole.DUAL or netrole == NetRole.SERVER:
            self.server_gsm = GameStateManager(showbase, server_states)

    def _handle_messages(self, gsm: GameStateManager, netrole: NetRole):
        msgfunc = getattr(gsm.current_state, 'handle_messages', None)
        if msgfunc:
            msgfunc(self.network.get_messages(netrole))
        else:
            print(f'{gsm.current_state.__class__.__name__} is missing handle_messages')

    def update(self, dt: float):
        if self.client_gsm:
            self._handle_messages(self.client_gsm, NetRole.CLIENT)
            self.client_gsm.update(dt)
        if self.server_gsm:
            self._handle_messages(self.server_gsm, NetRole.SERVER)
            self.server_gsm.update(dt)

    def change(self, state_name: str):
        if self.client_gsm:
            self.client_gsm.change(state_name, network=self.network)
        if self.server_gsm:
            self.server_gsm.change(state_name, network=self.network)
            self.server_gsm.current_state.root_node.detach_node()
            self.server_gsm.current_state.root_node2d.detach_node()

    def change_to_previous(self):
        if self.client_gsm:
            self.client_gsm.change_to_previous()
        if self.server_gsm:
            self.server_gsm.change_to_previous()


class GameApp(ShowBase):
    def __init__(self):
        pman.shim.init(self)
        ShowBase.__init__(self)

        simplepbr.init()

        self.disable_mouse()

        self.network = NetworkManager(net_role=NetRole.DUAL)
        self.network.register_message_types(
            PlayerInputMsg,
            PlayerUpdateMsg,
        )

        self.gamestates = NetworkGameStateManager(
            self,
            CLIENT_STATES,
            SERVER_STATES,
            self.network,
        )
        self.gamestates.change('Main')

        self.event_mapper = eventmapper.EventMapper()
        self.accept('quit', sys.exit)

        def update_states(task):
            clock = p3d.ClockObject.get_global_clock()
            self.network.update()
            self.gamestates.update(clock.get_dt())
            return task.cont

        self.task_mgr.add(update_states, 'Update Game State')


def main():
    app = GameApp()
    app.run()

if __name__ == '__main__':
    main()
