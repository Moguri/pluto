import sys

from direct.showbase.ShowBase import ShowBase
import panda3d.core as p3d

import eventmapper
import pman.shim
import simplepbr

from lib.gamestates import GameStateManager

from game import gamestates


p3d.load_prc_file_data(
    '',
    'window-title Panda3D Game\n'
    'win-fixed-size true\n'
    'win-size 1280 720\n'
    'event-map-item-quit escape q\n'
    'event-map-item-move-forward raw-w\n'
    'event-map-item-move-backward raw-s\n'
    'event-map-item-move-left raw-a\n'
    'event-map-item-move-right raw-d\n'
)

STATES = {
    'Main': gamestates.Main,
}


class GameApp(ShowBase):
    def __init__(self):
        pman.shim.init(self)
        ShowBase.__init__(self)

        simplepbr.init()

        self.disable_mouse()

        self.gamestates = GameStateManager(self, STATES, 'Main')
        self.event_mapper = eventmapper.EventMapper()
        self.accept('quit', sys.exit)

        def update_states(task):
            clock = p3d.ClockObject.get_global_clock()
            self.gamestates.update(clock.get_dt())
            return task.cont

        self.task_mgr.add(update_states, 'Update Game State')


def main():
    app = GameApp()
    app.run()

if __name__ == '__main__':
    main()
