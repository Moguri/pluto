from typing import (
    Mapping,
    TypeAlias,
)

import panda3d.core as p3d

from direct.showbase.DirectObject import DirectObject
from direct.showbase.ShowBase import ShowBase


class GameState:
    def __init__(self, base):
        super().__init__()
        self.events: DirectObject = DirectObject()
        self.root_node: p3d.NodePath[p3d.PandaNode] | None = p3d.NodePath('State Root')
        self.root_node2d: p3d.NodePath[p3d.PandaNode] | None = p3d.NodePath('State Root 2D')

        if base:
            self.root_node.reparent_to(base.render)
            self.root_node2d.reparent_to(base.render2d)

            def handle_fade(task):
                if base.transitions.fadeOutActive():
                    base.transitions.fadeIn()
                return task.done
            base.taskMgr.do_method_later(0, handle_fade, 'Fade In')

    def cleanup(self):
        self.events.ignoreAll()
        if self.root_node:
            self.root_node.remove_node()
            self.root_node = None
        if self.root_node2d:
            self.root_node2d.remove_node()
            self.root_node2d = None

    def update(self, _dt: float):
        pass


StatesDict: TypeAlias = Mapping[str, type[GameState]]


class GameStateManager:
    def __init__(self, showbase: ShowBase | None, states: StatesDict, initial_state_name: str):
        self.current_state: GameState | None = None
        self.previous_state_name: str = ''
        self.current_state_name: str = ''
        self.states = states
        self.base = showbase
        self.change(initial_state_name)

    def update(self, dt: float):
        if self.current_state:
            self.current_state.update(dt)

    def change(self, state_name: str):
        if state_name not in self.states:
            raise RuntimeError(f'Unknown state name: {state_name}')
        if self.current_state is None:
            self.previous_state_name = state_name
        else:
            self.previous_state_name = self.current_state_name
            self.current_state.cleanup()
        self.current_state_name = state_name
        self.current_state = self.states[state_name](self.base)

    def change_to_previous(self):
        self.change(self.previous_state_name)
