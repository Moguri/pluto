from lib import gamestates

class TestState(gamestates.GameState):
    pass

def test_gamesate_basic():
    gamestates.GameStateManager(None, {'test': TestState}, 'test')
