from typing import (
    Mapping,
    TypeAlias,
)

import panda3d.core as p3d

from direct.showbase.DirectObject import DirectObject
from direct.showbase.ShowBase import ShowBase
from direct.showbase.Loader import Loader
from direct.task.TaskManagerGlobal import taskMgr as task_mgr


class GameState:
    def __init__(self, base: ShowBase | None) -> None:
        super().__init__()
        self.events: DirectObject = DirectObject()
        self.root_node: p3d.NodePath[p3d.PandaNode] = p3d.NodePath('State Root')
        self.root_node2d: p3d.NodePath[p3d.PandaNode] = p3d.NodePath('State Root 2D')
        self.resources: dict[str, p3d.NodePath] = {}

        if base:
            self.root_node.reparent_to(base.render)
            self.root_node2d.reparent_to(base.render2d)

    def cleanup(self) -> None:
        self.events.ignoreAll()
        self.root_node.remove_node()
        self.root_node2d.remove_node()

    async def load(self, loader: Loader) -> None:
        resources: dict[str, str] = getattr(self.__class__, 'RESOURCES', {})

        for name, filepath in resources.items():
            self.resources[name] = await loader.load_model(modelPath=filepath, blocking=False)

    def start(self) -> None:
        pass

    def update(self, _dt: float) -> None:
        pass


StatesDict: TypeAlias = Mapping[str, type[GameState]]


class GameStateManager:
    def __init__(self, showbase: ShowBase | None, states: StatesDict):
        self.current_state: GameState | None = None
        self.previous_state_name: str = ''
        self.current_state_name: str = ''
        self.states = states
        self.base = showbase
        self.task_mgr = task_mgr
        self.load_complete = False

    def update(self, dt: float) -> None:
        if self.current_state and self.load_complete:
            self.current_state.update(dt)

    def change(self, state_name: str, *args, **kwargs) -> None:
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

        self.current_state = self.states[state_name](self.base, *args, **kwargs)

        async def load_state(_task: p3d.AsyncTask) -> int:
            if not self.base:
                self.load_complete = True
                return p3d.AsyncTask.DS_done

            self.load_complete = False
            if self.base.win and not self.base.transitions.fadeOutActive():
                await self.base.transitions.fadeOut()
            if self.current_state is not None:
                await self.current_state.load(self.base.loader)
                self.current_state.start()
            if self.base.win:
                self.base.transitions.fadeIn()
            self.load_complete = True

            return p3d.AsyncTask.DS_done
        self.task_mgr.add(load_state)


    def change_to_previous(self) -> None:
        self.change(self.previous_state_name)
