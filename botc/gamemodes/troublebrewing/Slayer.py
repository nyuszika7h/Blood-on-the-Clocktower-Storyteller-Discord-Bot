"""Contains the Slayer Character class"""

import json 
from botc import Townsfolk, Character
from botc.BOTCUtils import GameLogic
from ._utils import TroubleBrewing, TBRole

with open('botc/gamemodes/troublebrewing/character_text.json') as json_file: 
    character_text = json.load(json_file)[TBRole.slayer.value.lower()]   


class Slayer(Townsfolk, TroubleBrewing, Character):
    """Slayer: Once per game, during the day, publicly choose a player: if they are the Demon, they die.

    ===== SLAYER ===== 

    true_self = slayer
    ego_self = slayer
    social_self = slayer

    commands:
    - slay <player>

    initialize setup? -> NO
    initialize role? -> NO

    ----- First night
    START:
    override first night instruction? -> NO  # default is to send instruction string only

    ----- Regular night
    START:
    override regular night instruction -> NO  # default is to send nothing
    """

    def __init__(self):
        
        Character.__init__(self)
        TroubleBrewing.__init__(self)
        Townsfolk.__init__(self)

        self._desc_string = character_text["description"]
        self._examp_string = character_text["examples"]
        self._instr_string = character_text["instruction"]
        self._lore_string = character_text["lore"]
        self._brief_string = character_text["brief"]
        self._action = character_text["action"]
        
        self._art_link = "http://bloodontheclocktower.com/wiki/images/2/2f/Slayer_Token.png"
        self._wiki_link = "http://bloodontheclocktower.com/wiki/Slayer"

        self._role_enum = TBRole.slayer
        self._emoji = "<:slayer:722687329050820648>"

    def create_n1_instr_str(self):
        """Create the instruction field on the opening dm card"""

        # First line is the character instruction string
        msg = f"{self.emoji} {self.instruction}"
        addendum = character_text["n1_addendum"]
        
        # Some characters have a line of addendum
        if addendum:
            with open("botutils/bot_text.json") as json_file:
                bot_text = json.load(json_file)
                scroll_emoji = bot_text["esthetics"]["scroll"]
            msg += f"\n{scroll_emoji} {addendum}"
            
        return msg
    
    @GameLogic.changes_not_allowed
    @GameLogic.unique_ability
    @GameLogic.requires_one_target
    async def register_slay(self, player, targets):
        """Slay command"""
        pass

