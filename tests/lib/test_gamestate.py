from lib import gamestates

class TestState(gamestates.GameState):
    pass

def test_gamesate_basic():
    gsm = gamestates.GameStateManager(None, {'test': TestState})
    gsm.change('test')
