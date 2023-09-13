import panda3d.core as p3d

GAME_DEFAULTS = '''
window-title Pluto Game
win-size 1280 720
'''

INPUT_DEFAULTS = '''
event-map-item-quit escape q
event-map-item-move-up raw-w
event-map-item-move-down raw-s
event-map-item-move-left raw-a
event-map-item-move-right raw-d
event-map-item-fire mouse1
'''

def load():
    p3d.load_prc_file_data(
        'Game Defaults',
        GAME_DEFAULTS
    )
    p3d.load_prc_file_data(
        'Input Defaults',
        INPUT_DEFAULTS
    )

    user_config_path = p3d.Filename.expand_from('$MAIN_DIR/config.prc')
    if user_config_path.exists():
        p3d.load_prc_file(user_config_path)
