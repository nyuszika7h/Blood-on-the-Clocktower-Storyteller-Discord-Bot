"""Contains the GameChooser class"""

from botc.gamemodes.Gamemode import Gamemode

class GameChooser:
    """A class to faciliate gamemode choosing and voting"""

    from botc.Game import Game
    
    _default_game = Game()

    _tb_game = Game(Gamemode.trouble_brewing)
    _bmr_game = Game(Gamemode.bad_moon_rising)
    _snv_game = Game(Gamemode.sects_and_violets)

    selected_gamemode = Gamemode.trouble_brewing

    @property
    def default_game(self):
        return self._default_game
    
    def get_selected_game(self):
        if self.selected_gamemode == Gamemode.trouble_brewing:
            return self. _tb_game
        elif self.selected_gamemode == Gamemode.bad_moon_rising:
            return self._bmr_game
        elif self.selected_gamemode == Gamemode.sects_and_violets:
            return self._snv_game
        else:
            return self._default_game
