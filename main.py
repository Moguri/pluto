import sys

from direct.showbase.ShowBase import ShowBase
import panda3d.core as p3d
import pman.shim

from lib.gamestates import GameStateManager

from game import gamestates


p3d.load_prc_file_data(
    '',
    'window-title Panda3D Game\n'
)

STATES = {
    'Main': gamestates.Main,
}


class GameApp(ShowBase):
    def __init__(self):
        pman.shim.init(self)
        ShowBase.__init__(self)

        self.gamestates = GameStateManager(self, STATES, 'Main')
        self.accept('escape', sys.exit)


def main():
    app = GameApp()
    app.run()

if __name__ == '__main__':
    main()
