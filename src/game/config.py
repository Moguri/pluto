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

msaa_samples = p3d.ConfigVariableInt(
    name='msaa-samples',
    default_value=4,
    description='Number of samples for MSAA (0, 2, 4, 8, or 16)'
)

enable_shadows = p3d.ConfigVariableBool(
    name='enable-shadows',
    default_value=True,
    description='Enable shadow casting'
)

shadow_resolution = p3d.ConfigVariableInt(
    name='shadow-resolution',
    default_value=2048,
    description='Resolution for shadow casting map (powers of two preferred)'
)


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
