from typing import (
    Mapping,
    TypeAlias,
)

import panda3d.core as p3d

from direct.showbase.DirectObject import DirectObject
from direct.showbase.ShowBase import ShowBase
from direct.task.TaskManagerGlobal import taskMgr as task_mgr


class GameState:
    def __init__(self, base) -> None:
        super().__init__()
        self.events: DirectObject = DirectObject()
        self.root_node: p3d.NodePath[p3d.PandaNode] | None = p3d.NodePath('State Root')
        self.root_node2d: p3d.NodePath[p3d.PandaNode] | None = p3d.NodePath('State Root 2D')
        self.resources: dict[str, p3d.NodePath] = {}

        if base:
            self.root_node.reparent_to(base.render)
            self.root_node2d.reparent_to(base.render2d)

    def cleanup(self) -> None:
        self.events.ignoreAll()
        if self.root_node:
            self.root_node.remove_node()
            self.root_node = None
        if self.root_node2d:
            self.root_node2d.remove_node()
            self.root_node2d = None

    async def load(self, loader) -> None:
        resources = getattr(self.__class__, 'RESOURCES', {})

        for name, filepath in resources.items():
            self.resources[name] = await loader.load_model(filepath, blocking=False)

    def start(self) -> None:
        pass

    def update(self, _dt: float) -> None:
        pass


StatesDict: TypeAlias = Mapping[str, type[GameState]]


class GameStateManager:
    def __init__(self, showbase: ShowBase | None, states: StatesDict, initial_state_name: str):
        self.current_state: GameState | None = None
        self.previous_state_name: str = ''
        self.current_state_name: str = ''
        self.states = states
        self.base = showbase
        self.task_mgr = task_mgr
        self.change(initial_state_name)

    def update(self, dt: float):
        if self.current_state:
            self.current_state.update(dt)

    def change(self, state_name: str):
        if state_name not in self.states:
            raise RuntimeError(f'Unknown state name: {state_name}')
        if self.current_state is None:
            if self.base:
                self.base.transitions.fadeOut(0)
            self.previous_state_name = state_name
        else:
            self.previous_state_name = self.current_state_name
            self.current_state.cleanup()
        self.current_state_name = state_name

        self.current_state = self.states[state_name](self.base)

        async def load_state(task):
            if self.base and not self.base.transitions.fadeOutActive():
                await self.base.transitions.fadeOut()
            await self.current_state.load(self.base.loader)
            self.current_state.start()
            if self.base:
                self.base.transitions.fadeIn()

            return task.done
        self.task_mgr.add(load_state)


    def change_to_previous(self):
        self.change(self.previous_state_name)
