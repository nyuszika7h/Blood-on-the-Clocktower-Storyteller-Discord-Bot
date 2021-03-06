"""Contains the Soldier Character class"""

import json 
from botc import Townsfolk, Character, NonRecurringAction, SafetyFromDemon, \
    Storyteller
from ._utils import TroubleBrewing, TBRole
import botutils

with open('botc/gamemodes/troublebrewing/character_text.json') as json_file: 
    character_text = json.load(json_file)[TBRole.soldier.value.lower()]

with open('botc/emojis.json') as json_file:
    emojis = json.load(json_file)


class Soldier(Townsfolk, TroubleBrewing, Character, NonRecurringAction):
    """Soldier: You are safe from the Demon.

    ===== SOLDIER ===== 

    true_self = soldier
    ego_self = soldier
    social_self = soldier

    commands:
    - None

    initialize setup? -> NO
    initialize role? -> NO

    ----- First night
    START:
    override first night instruction? -> NO  # default is to send instruction string only

    ----- Regular night
    START:
    override regular night instruction? -> NO  # default is to send nothing
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
                            
        self._art_link = "https://bloodontheclocktower.com/wiki/images/9/9e/Soldier_Token.png"
        self._art_link_cropped = "https://imgur.com/IkJqfHH.png"
        self._wiki_link = "https://bloodontheclocktower.com/wiki/Soldier"

        self._role_enum = TBRole.soldier
        self._emoji = emojis["troublebrewing"]["soldier"]

    def create_n1_instr_str(self):
        """Create the instruction field on the opening dm card"""

        # First line is the character instruction string
        msg = f"{self.emoji} {self.instruction}"
        addendum = character_text["n1_addendum"]
        
        # Some characters have a line of addendum
        if addendum:
            scroll_emoji = botutils.BotEmoji.scroll
            msg += f"\n{scroll_emoji} {addendum}"
            
        return msg
    
    async def process_night_ability(self, player):
        """Process night actions for the soldier character.
        @player : the Soldier player (Player object)
        """

        if not player.is_droisoned() and player.is_alive():
            player.add_status_effect(SafetyFromDemon(Storyteller(), player, 2))
