"""(raiders) The per-game layer: one games/<id>/game.py per supported game, plain data read by nx2/game.py.

Each holds the same fields (tests/test_game_config.py checks them). A game's code that is not data (lift-time patches,
from T06) goes in modules beside its game.py, named by its LIFT_PATCHES.
"""
