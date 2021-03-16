"""Contains the BOTC Game class"""

import random
import datetime
import botutils
import globvars
import json
import pytz
import configparser
import discord
import sqlite3
from library import fancy
from .chrono import GameChrono
from .BOTCUtils import BOTCUtils
from .Category import Category
from .Phase import Phase
from .Player import Player
from .PlayerState import PlayerState
from .errors import GameError, TooFewPlayers, TooManyPlayers
from .Townsfolk import Townsfolk
from .Outsider import Outsider
from .Minion import Minion
from .Demon import Demon
from .gamemodes.troublebrewing.Saint import Saint
from .gamemodes.troublebrewing.Drunk import Drunk
from .gamemodes.troublebrewing._utils import TroubleBrewing
from .gamemodes.badmoonrising._utils import BadMoonRising
from .gamemodes.sectsandviolets._utils import SectsAndViolets
from .gamemodes.Gamemode import Gamemode
from .RoleGuide import RoleGuide
from .gameloops import master_game_loop, nomination_loop, base_day_loop, debate_timer
from models import GameMeta
from botc import StatusList, Team

Preferences = configparser.ConfigParser()
Preferences.read("preferences.INI")

CARD_NIGHT = Preferences["colors"]["CARD_NIGHT"]
CARD_NIGHT = int(CARD_NIGHT, 16)

CARD_DAWN = Preferences["colors"]["CARD_DAWN"]
CARD_DAWN = int(CARD_DAWN, 16)

CARD_DAY = Preferences["colors"]["CARD_DAY"]
CARD_DAY = int(CARD_DAY, 16)

TOWNSFOLK_COLOR = Preferences["colors"]["TOWNSFOLK_COLOR"]
DEMON_COLOR = Preferences["colors"]["DEMON_COLOR"]
TOWNSFOLK_COLOR = int(TOWNSFOLK_COLOR, 16)
DEMON_COLOR = int(DEMON_COLOR, 16)

Config = configparser.ConfigParser()
Config.read("config.INI")

SERVER_ID = Config["user"]["SERVER_ID"]
SERVER_ID = int(SERVER_ID)

DISABLE_DMS = Config["misc"].get("DISABLE_DMS", "").lower() == "true"

CONFLICTING_CMDS = [

   "cmd.gameplay"

]

random.seed(datetime.datetime.now())

with open('botc/game_text.json') as json_file:
    strings = json.load(json_file)
    nightfall = strings["gameplay"]["nightfall"]
    daybreak = strings["gameplay"]["daybreak"]
    dawn = strings["gameplay"]["dawn"]
    lobby_game_start = strings["gameplay"]["lobby_game_start"]
    lobby_game_closing = strings["gameplay"]["lobby_game_closing"]
    evilteammates = strings["gameplay"]["evilteammates"]
    copyrights_str = strings["misc"]["copyrights"]
    tb_lore = strings["gameplay"]["tb_lore"]
    bmr_lore = strings["gameplay"]["bmr_lore"] # TODO add bmr lore
    snv_lore = strings["gameplay"]["snv_lore"] # TODO add snv lore
    nightfall_image = strings["images"]["nightfall"]
    dawn_image = strings["images"]["dawn"]
    daybreak_image = strings["images"]["daybreak"]
    dove = strings["images"]["dove"]
    demon = strings["images"]["demon"]
    no_one_wins = strings["gameplay"]["no_one_wins"]
    good_wins = strings["gameplay"]["good_wins"]
    evil_wins = strings["gameplay"]["evil_wins"]
    role_reveal = strings["gameplay"]["role_reveal"]
    role_reveal_herring = strings["gameplay"]["role_reveal_herring"]
    storyteller_death = strings["lore"]["storyteller_death"]
    ego_role_reveal = strings["gameplay"]["ego_role_reveal"]
    ego_role_reveal_herring = strings["gameplay"]["ego_role_reveal_herring"]
    changed_role_reveal = strings["gameplay"]["changed_role_reveal"]


class Setup:
    """A class to facilitate role to player access"""

    DEMON_HEAD_EMOJI = botutils.BotEmoji.demonhead

    def __init__(self):

        self.demon = []
        self.minions = []
        self.townsfolks = []
        self.outsiders = []
        self.role_dict = {}  # {"recluse" : player_obj1, "undertaker" : player_obj2}

    def create(self, player_ob_list):

        for player in player_ob_list:
            self.role_dict.update({player.role.name.lower(): player})
            if player.role.category == Category.demon:
                self.demon.append(player)
            elif player.role.category == Category.minion:
                self.minions.append(player)
            elif player.role.category == Category.townsfolk:
                self.townsfolks.append(player)
            elif player.role.category == Category.outsider:
                self.outsiders.append(player)
        assert len(self.demon) == 1, "More than 1 demon found."

    def create_evil_team_string(self):
        """
        :demonhead: Your Evil team consists of:
        ```basic
        Oliver (460105234748801024) (demon)
        Johnny (159985870458322944) (minion)
        Michel (614109280508968980) (minion)
        ```
        """
        msg = Setup.DEMON_HEAD_EMOJI + " " + evilteammates + "```basic\n"
        for demon in self.demon:
            msg += f"{demon.user.display_name} ({demon.user.id}) (demon)"
            msg += "\n"
        for minion in self.minions:
            msg += f"{minion.user.display_name} ({minion.user.id}) (minion)"
            msg += "\n"
        msg += "```"
        return msg

    def clear(self):

        self.__init__()


class GameLog:
    """Game log class"""

    def __init__(self, game_obj):
        self.setup = game_obj.setup
        self.sitting_order = game_obj.sitting_order
        self.gamemode = game_obj.gamemode.value

    def create_game_obj_log_str(self):
        """Create the game log string. The string looks like this:

        Game Start:
        ```asciidoc
        BoTC game started at 2020-06-19T19:50:04.657050-04:00, with 10 players, using the Trouble-Brewing edition.
        --------------------
        DEMON :: [Tester 1 (614109280508968980) is Imp]
        MINION :: [Tester 5 (235088799074484224) is Baron, Tester 3 (159985870458322944) is Spy]
        TOWNSFOLK :: [Tester 6 (172002275412279296) is Chef, Tester 4 (184405311681986560) is Monk, Xinverse
        (346426113285753875) is Slayer, Tester 7 (460105234748801024) is Librarian, Tester 2 (270904126974590976)
        is Investigator]
        OUTSIDER :: [Penguin (606332710911156778) is Saint, Temporary Bot (609674334247771236) is Butler]
        ```
        """

        Config = configparser.ConfigParser()
        Config.read("preferences.INI")

        TIMEZONE = Config["location"]["TIME_ZONE"]

        d = datetime.datetime.now()
        timezone = pytz.timezone(TIMEZONE)
        d_aware = timezone.localize(d)

        msg = "Game Start:```asciidoc\n"
        msg += f"BoTC game started at {d_aware.isoformat()}, with {len(self.sitting_order)} players, using the {self.gamemode} edition.\n"
        msg += "--------------------\n"

        msg += f"DEMON :: {str(self.setup.demon)}\n"
        msg += f"MINION :: {str(self.setup.minions)}\n"
        msg += f"TOWNSFOLK :: {str(self.setup.townsfolks)}\n"
        msg += f"OUTSIDER :: {str(self.setup.outsiders)}\n"

        msg += "```"

        return msg

    async def send_game_obj_log_str(self):
        """Log the game object"""
        msg = self.create_game_obj_log_str()
        await botutils.log(botutils.Level.info, msg)


class Game(GameMeta):
    """BoTC Game class"""

    MIN_PLAYERS = 5
    MAX_PLAYERS = 15

    def __init__(self, gamemode = Gamemode.trouble_brewing):

        self._gamemode = gamemode  # default gamemode will always be trouble brewing

        self._member_obj_list = []  # list object - list of discord member objects
        self._player_obj_list = []  # list object - list of player objects
        self._sitting_order = tuple()  # tuple object (for immutability)
        self._chrono = GameChrono()
        self._setup = Setup()
        self.gameloop = master_game_loop
        self.winners = None  # botc.Team object
        self.invalidated = False  # Don't count in win rates due to modkill/frole/player leaving guild

        if DISABLE_DMS:
            # Also don't count game in win rates if dms are disabled.
            # This shouldn't be a problem considering DISABLE_DMS is a testing flag,
            # but it would be unfair to count the game if the players do not know what
            # character they are or when to act.
            self.invalidated = True

        # Temporary day data
        self.chopping_block = None  # ChoppingBlock object
        self.today_executed_player = None  # Player object
        self.day_start_time = None  # datetime()
        self.nomination_iteration_date = tuple()  # tuple(datetime() for start time, duration in secs)

        # Temporary night data
        self.night_deaths = []  # List of player objects
        self.night_start_time = None  # datetime()

        # Temporary dawn data
        self.dawn_start_time = None  # datetime()

    @property
    def nb_players(self):
        return len(self._player_obj_list)

    @property
    def gamemode(self):
        return self._gamemode

    @property
    def member_obj_list(self):
        return self._member_obj_list

    @property
    def player_obj_list(self):
        return self._player_obj_list

    @property
    def sitting_order(self):
        return self._sitting_order

    @property
    def current_phase(self):
        return self._chrono.phase

    @property
    def current_cycle(self):
        return self._chrono.cycle

    @property
    def setup(self):
        return self._setup

    def is_idle(self):
        return self.current_phase == Phase.idle

    def is_day(self):
        return self.current_phase == Phase.day

    def is_dawn(self):
        return self.current_phase == Phase.dawn

    def is_night(self):
        return self.current_phase == Phase.night

    def init_temporary_day_data(self):
        """Initialize temporary day data. To be called at the start of the day"""
        # Temporary day data
        self.chopping_block = None  # ChoppingBlock object
        self.today_executed_player = None  # Player object
        self.day_start_time = None  # datetime()
        self.nomination_iteration_date = tuple()  # tuple(datetime() for start time, duration in secs)

    def init_temporary_night_data(self):
        """Initialize temporary night data. To be called at the start of the night"""
        # Temporary night data
        self.night_deaths = []  # List of player objects
        self.night_start_time = None  # datetime()

    def init_temporary_dawn_data(self):
        """Initialize temporary dawn data. To be called at the start of the dawn"""
        # Temporary dawn data
        self.dawn_start_time = None  # datetime()

    def create_sitting_order_stats_string(self):
        """Create a stats board:

        Sitting Order:
        ```css
        Chris (232456937349834784) [DEAD]
        John (233426113285745785) [ALIVE]
        Anna (266015398221479937) [ALIVE]
        Fred (3447492102843678721) [ALIVE]
        ```
        """

        msg = "\n\n**Players**: ```css\n"
        for player in self.sitting_order:
            if player.is_alive():
                line = f"{player.user.display_name} ({player.user.id}) [alive]\n"
            elif player.is_dead():
                if player.has_vote():
                    line = f"{player.user.display_name} ({player.user.id}) [dead] {botutils.BotEmoji.skull} {botutils.BotEmoji.vote}\n"
                else:
                    line = f"{player.user.display_name} ({player.user.id}) [dead] {botutils.BotEmoji.skull}\n"
            else:
                line = f"{player.user.display_name} ({player.user.id}) [quit] {botutils.BotEmoji.fquit}\n"
            msg += line
        msg += "```"
        return msg

    def register_players(self, id_list):
        """Register the players.
        Must be implemented.
        """

        for user_id in id_list:
            member_obj = botutils.get_member_obj(user_id)
            if member_obj:
                self._member_obj_list.append(member_obj)
            else:
                raise GameError("Member not found, invalid user ID")

    async def send_lobby_welcome_message(self):
        """Send the welcome message in lobby"""

        # Trouble Brewing Edition
        if self.gamemode == Gamemode.trouble_brewing:
            embed = discord.Embed(
               description = tb_lore
            )
            # Using the Saint() object to access some URL's
            embed.set_thumbnail(url = TroubleBrewing()._gm_art_link)
            embed.set_author(name = "𝕿𝖗𝖔𝖚𝖇𝖑𝖊 𝕭𝖗𝖊𝖜𝖎𝖓𝖌 - 𝕭𝖑𝖔𝖔𝖉 𝖔𝖓 𝖙𝖍𝖊 𝕮𝖑𝖔𝖈𝖐𝖙𝖔𝖜𝖊𝖗 (𝕭𝖔𝕿𝕮)",
                             icon_url = Saint()._botc_logo_link)
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text = copyrights_str)

            pings = " ".join([player.user.mention for player in self.sitting_order])
            msg = lobby_game_start.format(pings, "𝕿𝖗𝖔𝖚𝖇𝖑𝖊 𝕭𝖗𝖊𝖜𝖎𝖓𝖌", self.nb_players)

            await botutils.send_lobby(msg, embed=embed)
        
        # Bad Moon Rising edition
        elif self.gamemode == Gamemode.bad_moon_rising:
            embed = discord.Embed(
               description = bmr_lore
            )
            # Using the Saint() object to access some URL's
            embed.set_thumbnail(url = BadMoonRising()._gm_art_link)
            embed.set_author(name = "𝕭𝖆𝖉 𝕸𝖔𝖔𝖓 𝕽𝖎𝖘𝖎𝖓𝖌 - 𝕭𝖑𝖔𝖔𝖉 𝖔𝖓 𝖙𝖍𝖊 𝕮𝖑𝖔𝖈𝖐𝖙𝖔𝖜𝖊𝖗 (𝕭𝖔𝕿𝕮)",
                             icon_url = Saint()._botc_logo_link)
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text = copyrights_str)

            pings = " ".join([player.user.mention for player in self.sitting_order])
            msg = lobby_game_start.format(pings, "𝕭𝖆𝖉 𝕸𝖔𝖔𝖓 𝕽𝖎𝖘𝖎𝖓𝖌", self.nb_players)

            await botutils.send_lobby(msg, embed=embed)

        # Sects And Violets edition
        elif self.gamemode == Gamemode.sects_and_violets:
            embed = discord.Embed(
               description = snv_lore
            )
            # Using the Saint() object to access some URL's
            embed.set_thumbnail(url = SectsAndViolets()._gm_art_link)
            embed.set_author(name = "𝕾𝖊𝖈𝖙𝖘 𝖆𝖓𝖉 𝖁𝖎𝖔𝖑𝖊𝖙𝖘 - 𝕭𝖑𝖔𝖔𝖉 𝖔𝖓 𝖙𝖍𝖊 𝕮𝖑𝖔𝖈𝖐𝖙𝖔𝖜𝖊𝖗 (𝕭𝖔𝕿𝕮)",
                             icon_url = Saint()._botc_logo_link)
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text = copyrights_str)

            pings = " ".join([player.user.mention for player in self.sitting_order])
            msg = lobby_game_start.format(pings, "𝕾𝖊𝖈𝖙𝖘 𝖆𝖓𝖉 𝖁𝖎𝖔𝖑𝖊𝖙𝖘", self.nb_players)

            await botutils.send_lobby(msg, embed=embed)

    async def send_lobby_closing_message(self, win_con_reason = ""):
        """Send the closing message in lobby"""

        from botc import Team

        gamemode = fancy.bold(self.gamemode.value)

        with sqlite3.connect("data.sqlite3") as db:
            player_count = len(self.sitting_order)

            # ----- The good team wins -----
            if self.winners == Team.good:

                if not self.invalidated:
                    db.execute('UPDATE gamestats SET total_games = total_games + 1 WHERE players = ?', (player_count,))
                    db.execute('UPDATE gamestats SET good_wins = good_wins + 1 WHERE players = ?', (player_count,))
                # Revealing the role list
                role_list_str = ""
                for player in self.sitting_order:

                    # The player is a drunk, we use the special reveal short string
                    if player.role.true_self.name == Drunk().name:
                        if player.has_status_effect(StatusList.red_herring):
                            message = ego_role_reveal_herring
                        else:
                            message = ego_role_reveal

                        short = message.format(
                           botutils.BotEmoji.trophy_animated if player.role.true_self.is_good() else "---",
                           player.user.mention,
                           player.role.true_self.emoji,
                           player.role.true_self.name,
                           player.role.ego_self.name
                        )

                    # The player is a minion who became imp
                    elif player.old_role is not None:
                        short = changed_role_reveal.format(
                           botutils.BotEmoji.trophy_animated if player.role.true_self.is_good() else "---",
                           player.user.mention,
                           player.role.true_self.emoji,
                           player.role.true_self.name,
                           player.old_role.true_self.emoji,
                           player.old_role.true_self.name,
                        )

                    # The player is not a drunk, we use the default reveal short string
                    else:
                        if player.has_status_effect(StatusList.red_herring):
                            message = role_reveal_herring
                        else:
                            message = role_reveal

                        short = message.format(
                           botutils.BotEmoji.trophy_animated if player.role.true_self.is_good() else "---",
                           player.user.mention,
                           player.role.true_self.emoji,
                           player.role.true_self.name
                        )

                    role_list_str += short
                    role_list_str += "\n"

                    if not self.invalidated:
                        db.execute('INSERT OR IGNORE INTO playerstats (user_id) VALUES (?)', (player.user.id,))
                        db.execute('UPDATE playerstats SET games = games + 1 WHERE user_id = ?', (player.user.id,))
                        if player.role.true_self.is_good():
                            db.execute('UPDATE playerstats SET wins = wins + 1 WHERE user_id = ?', (player.user.id,))
                            db.execute('UPDATE playerstats SET good_games = good_games + 1 WHERE user_id = ?', (player.user.id,))
                            db.execute('UPDATE playerstats SET good_wins = good_wins + 1 WHERE user_id = ?', (player.user.id,))
                        else:
                            db.execute('UPDATE playerstats SET evil_games = evil_games + 1 WHERE user_id = ?', (player.user.id,))

                # The embed
                embed = discord.Embed(
                   title = good_wins,
                   description = role_list_str,
                   color = TOWNSFOLK_COLOR
                )
                embed.set_author(
                   name = "{} - 𝕭𝖑𝖔𝖔𝖉 𝖔𝖓 𝖙𝖍𝖊 𝕮𝖑𝖔𝖈𝖐𝖙𝖔𝖜𝖊𝖗 (𝕭𝖔𝕿𝕮)".format(gamemode),
                   icon_url = Saint()._botc_logo_link
                )
                embed.set_thumbnail(url = dove)

            # ----- The evil team wins -----
            elif self.winners == Team.evil:

                if not self.invalidated:
                    db.execute('UPDATE gamestats SET total_games = total_games + 1 WHERE players = ?', (player_count,))
                    db.execute('UPDATE gamestats SET evil_wins = evil_wins + 1 WHERE players = ?', (player_count,))

                # Revealing the role list
                role_list_str = ""
                for player in self.sitting_order:

                    # The player is a drunk, we use the special reveal short string
                    if player.role.true_self.name == Drunk().name:
                        if player.has_status_effect(StatusList.red_herring):
                            message = ego_role_reveal_herring
                        else:
                            message = ego_role_reveal

                        short = message.format(
                           botutils.BotEmoji.trophy_animated if player.role.true_self.is_evil() else "---",
                           player.user.mention,
                           player.role.true_self.emoji,
                           player.role.true_self.name,
                           player.role.ego_self.name
                        )

                    # The player is a minion who became imp
                    elif player.old_role is not None:
                        short = changed_role_reveal.format(
                           botutils.BotEmoji.trophy_animated if player.role.true_self.is_evil() else "---",
                           player.user.mention,
                           player.role.true_self.emoji,
                           player.role.true_self.name,
                           player.old_role.true_self.emoji,
                           player.old_role.true_self.name,
                        )

                    # The player is not a drunk, we use the default reveal short string
                    else:
                        if player.has_status_effect(StatusList.red_herring):
                            message = role_reveal_herring
                        else:
                            message = role_reveal

                        short = message.format(
                           botutils.BotEmoji.trophy_animated if player.role.true_self.is_evil() else "---",
                           player.user.mention,
                           player.role.true_self.emoji,
                           player.role.true_self.name
                        )

                    role_list_str += short
                    role_list_str += "\n"

                    if not self.invalidated:
                        db.execute('INSERT OR IGNORE INTO playerstats (user_id) VALUES (?)', (player.user.id,))
                        db.execute('UPDATE playerstats SET games = games + 1 WHERE user_id = ?', (player.user.id,))
                        if player.role.true_self.is_evil():
                            db.execute('UPDATE playerstats SET wins = wins + 1 WHERE user_id = ?', (player.user.id,))
                            db.execute('UPDATE playerstats SET evil_games = evil_games + 1 WHERE user_id = ?', (player.user.id,))
                            db.execute('UPDATE playerstats SET evil_wins = evil_wins + 1 WHERE user_id = ?', (player.user.id,))
                        else:
                            db.execute('UPDATE playerstats SET good_games = good_games + 1 WHERE user_id = ?', (player.user.id,))

                # The embed
                embed = discord.Embed(
                   title = evil_wins,
                   description = role_list_str,
                   color = DEMON_COLOR
                )
                embed.set_author(
                   name = "{} - 𝕭𝖑𝖔𝖔𝖉 𝖔𝖓 𝖙𝖍𝖊 𝕮𝖑𝖔𝖈𝖐𝖙𝖔𝖜𝖊𝖗 (𝕭𝖔𝕿𝕮)".format(gamemode),
                   icon_url = Saint()._botc_logo_link
                )
                embed.set_thumbnail(url = demon)

            # ----- No one wins -----
            else:
                # Revealing the role list
                role_list_str = ""
                for player in self.sitting_order:

                    # The player is a drunk, we use the special reveal short string
                    if player.role.true_self.name == Drunk().name:
                        if player.has_status_effect(StatusList.red_herring):
                            message = ego_role_reveal_herring
                        else:
                            message = ego_role_reveal

                        short = message.format(
                           "",
                           player.user.mention,
                           player.role.true_self.emoji,
                           player.role.true_self.name,
                           player.role.ego_self.name
                        )

                    # The player is a minion who became imp
                    elif player.old_role is not None:
                        short = changed_role_reveal.format(
                           "",
                           player.user.mention,
                           player.role.true_self.emoji,
                           player.role.true_self.name,
                           player.old_role.true_self.emoji,
                           player.old_role.true_self.name,
                        )

                    # The player is not a drunk, we use the default reveal short string
                    else:
                        if player.has_status_effect(StatusList.red_herring):
                            message = role_reveal_herring
                        else:
                            message = role_reveal

                        short = message.format(
                           "",
                           player.user.mention,
                           player.role.true_self.emoji,
                           player.role.true_self.name
                        )

                    role_list_str += short
                    role_list_str += "\n"

                # The embed
                embed = discord.Embed(
                   title = no_one_wins,
                   description = role_list_str
                )
                embed.set_author(
                   name = "{} - 𝕭𝖑𝖔𝖔𝖉 𝖔𝖓 𝖙𝖍𝖊 𝕮𝖑𝖔𝖈𝖐𝖙𝖔𝖜𝖊𝖗 (𝕭𝖔𝕿𝕮)".format(gamemode),
                   icon_url = Saint()._botc_logo_link
                )

            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text = copyrights_str)

            pings = " ".join([player.user.mention for player in self.sitting_order])
            msg = lobby_game_closing.format(pings, gamemode, self.nb_players)

            await botutils.send_lobby(msg, embed=embed)

    async def start_game(self):
        """Start the game.
        Must be implemented.
        """

        # Cancel the timer
        if botutils.start_votes_timer.is_running():
            botutils.start_votes_timer.cancel()
        # Register the players in game
        self.register_players(globvars.master_state.pregame)
        # Generate the setup (role list)
        setup = self.generate_role_set()
        # Give each player a role
        self.distribute_roles(setup, self.member_obj_list)
        # Freeze the sitting
        self.generate_frozen_sitting()
        # Initialize the setup object
        self.setup.clear()
        self.setup.create(self.player_obj_list)
        # Initialize each role to set flags as needed, etc.
        for player in self._player_obj_list:
            player.role.exec_init_role(self.setup)
        # Send the lobby welcome message
        await self.send_lobby_welcome_message()
        # Lock the lobby channel
        await botutils.lock_lobby()
        # Send the opening dm to all players
        for player in self._player_obj_list:
            await player.role.ego_self.send_opening_dm_embed(player.user)
        # Log the game data
        await GameLog(self).send_game_obj_log_str()
        # Unload conflicting commands
        for extension in CONFLICTING_CMDS:
            globvars.client.unload_extension(extension)
        # Load game related commands
        if self.gamemode == Gamemode.trouble_brewing:
            globvars.client.load_extension("botc.commands.abilities.tb")
        elif self.gamemode == Gamemode.bad_moon_rising:
            globvars.client.load_extension("botc.commands.abilities.bmr")
        elif self.gamemode == Gamemode.sects_and_violets:
            globvars.client.load_extension("botc.commands.abilities.snv")
        
        globvars.client.load_extension("botc.commands.townhall")
        globvars.client.load_extension("botc.commands.debug")
        # Start the game loop
        self.gameloop.start(self)

    async def compute_dawn_ability_interactions(self):
        """Order of Action
        1. Ravenkeeper
        """

        await self.remove_left_guild_players()

        if self.gamemode == Gamemode.trouble_brewing:

            from botc.gamemodes.troublebrewing._utils import TBRole

            order = [

               TBRole.ravenkeeper

            ]

            for character_enum in order:
                list_of_characters = BOTCUtils.get_players_from_role_name(character_enum)
                for character in list_of_characters:
                    await character.role.ego_self.process_dawn_ability(character)

        elif self.gamemode == Gamemode.trouble_brewing:
            pass

        elif self.gamemode == Gamemode.sects_and_violets:
            pass

    async def compute_night_ability_interactions(self):
        """
        Prompt all players to complete their night actions, according to night order for the selected gamemode
        """

        await self.remove_left_guild_players()

        if self.gamemode == Gamemode.trouble_brewing:
            """Order of Action (First Night)
            1. poisoner
            2. washerwoman
            3. librarian
            4. investigator
            5. chef
            6. empath
            7. fortune teller
            8. butler
            9. spy

            Order of Action (All Other Nights)
            1. poisoner
            2. monk
            3. scarlet woman
            4. imp
            5. ravenkeeper
            6. empath
            7. fortune teller
            8. butler
            9. undertaker
            10. spy
            """

            from botc.gamemodes.troublebrewing._utils import TBRole

            night_1_order = [

               TBRole.poisoner,
               TBRole.washerwoman,
               TBRole.librarian,
               TBRole.investigator,
               TBRole.chef,
               TBRole.empath,
               TBRole.fortuneteller,
               TBRole.butler,
               TBRole.spy

            ]

            night_regular_order = [

               TBRole.poisoner,      # Poison
               TBRole.monk,          # Protect
               TBRole.scarletwoman,  # Let her know of any demon promotion
               TBRole.soldier,       # Add the safe from demon status effect if not droisoned
               TBRole.imp,           # Save the kill target
               TBRole.empath,
               TBRole.fortuneteller,
               TBRole.butler,
               TBRole.undertaker,    # Send the executed player's role
               TBRole.spy

            ]

        elif self.gamemode == Gamemode.bad_moon_rising:
            """Order of Action (First Night)
            1. lunatic
            2. sailor
            3. courtier
            4. godfather
            5. devil's advocate
            6. pukka    
            7. grandmother
            8. chambermaid

            Order of Action (All Other Nights)
            1. sailor
            2. courtier
            3. innkeeper
            4. gambler
            5. devil's advocate
            6. lunatic
            7. exorcist
            8. zombuul
            9. pukka
            10. shabaloth
            11. po
            12. assasin
            13. godfather
            14. gossip
            15. professor
            16. tinker
            17. moonchild
            18. grandmother
            19. chambermaid
            """

            from botc.gamemodes.badmoonrising._utils import BMRRole

            night_1_order = [
                BMRRole.lunatic,
                BMRRole.sailor,
                BMRRole.courtier,
                BMRRole.godfather,
                BMRRole.devilsadvocate,
                BMRRole.pukka,
                BMRRole.grandmother,
                BMRRole.chambermaid
            ]

            night_regular_order = [
                BMRRole.sailor,
                BMRRole.courtier,
                BMRRole.innkeeper,
                BMRRole.gambler,
                BMRRole.devilsadvocate,
                BMRRole.lunatic,
                BMRRole.exorcist,
                BMRRole.zombuul,
                BMRRole.pukka,
                BMRRole.shabaloth,
                BMRRole.po,
                BMRRole.assassin,
                BMRRole.godfather,
                BMRRole.gossip,
                BMRRole.professor,
                BMRRole.tinker,
                BMRRole.moonchild,
                BMRRole.grandmother,
                BMRRole.chambermaid
            ]

        elif self.gamemode == Gamemode.sects_and_violets:
            """Order of Action (First Night)
            1. philosopher
            2. snake charmer
            3. evil twin
            4. witch
            5. cerenovus
            6. clockmaker
            7. dreamer
            8. seamstress
            9. mathematician

            Order of Action (All Other Nights)
            1. philosopher
            2. snake charmer
            3. witch
            4. cerenovus
            5. pit-hag
            6. fang gu
            7. no dashii
            8. vortox
            9. vigormortis
            10. barber
            11. sweetheart
            12. sage
            13. dreamer
            14. flowergirl
            15. town crier
            16. oracle
            17. seamstress
            18. juggler
            19. mathematician
            """

            from botc.gamemodes.sectsandviolets._utils import SnVRole

            night_1_order = [
                SnVRole.philosopher,
                SnVRole.snakecharmer,
                SnVRole.eviltwin,
                SnVRole.witch,
                SnVRole.cerenovus,
                SnVRole.clockmaker,
                SnVRole.dreamer,
                SnVRole.seamstress,
                SnVRole.mathematician
            ]

            night_regular_order = [
                SnVRole.philosopher,
                SnVRole.snakecharmer,
                SnVRole.witch,
                SnVRole.cerenovus,
                SnVRole.pithag,
                SnVRole.fanggu,
                SnVRole.nodashii,
                SnVRole.vortox,
                SnVRole.vigormortis,
                SnVRole.barber,
                SnVRole.sweetheart,
                SnVRole.sage,
                SnVRole.dreamer,
                SnVRole.flowergirl,
                SnVRole.towncrier,
                SnVRole.oracle,
                SnVRole.seamstress,
                SnVRole.juggler,
                SnVRole.mathematician
            ]

        else:
            raise GameError("Gamemode is not one of available BoTC editions.")

        # Night 1 order
        if self._chrono.is_night_1():
            for character_enum in night_1_order:
                list_of_characters = BOTCUtils.get_players_from_role_name(character_enum)
                for character in list_of_characters:
                    await character.role.ego_self.process_night_ability(character)

        # Regular night order
        else:
            for character_enum in night_regular_order:
                list_of_characters = BOTCUtils.get_players_from_role_name(character_enum)
                for character in list_of_characters:
                    await character.role.ego_self.process_night_ability(character)

    def has_received_all_expected_dawn_actions(self):
        """Check if all players with expected dawn actions have submitted them"""
        for player in self.sitting_order:
            if not player.role.true_self.has_finished_dawn_action(player):
                return False
        return True

    def has_received_all_expected_night_actions(self):
        """Check if all players with expected night actions have submitted them"""
        for player in self.sitting_order:
            if not player.role.true_self.has_finished_night_action(player):
                return False
        return True

    @property
    def nb_alive_players(self):
        """Return the number of alive players (apparently alive state)"""
        count = 0
        for player in self.sitting_order:
            if player.is_apparently_alive():
                count += 1
        return count

    @property
    def list_alive_players(self):
        """Return the list of alive players (truly alive state)"""
        return [player for player in self.sitting_order if player.is_alive()]

    async def check_winning_conditions(self):
        """Check if the game has reached the winning conditons. Promote new demons or
        end the game is necessary.
        """

        # Less than or equal to 2 alive players. Winning condition is definitely triggered.
        if self.nb_alive_players <= 2:

            # There are still alive demons. The game is over with Evil win.
            if BOTCUtils.has_alive_demons():
                self.winners = Team.evil
                self.gameloop.cancel()

            # There is no alive demon. The game is over with Good win.
            else:
                self.winners = Team.good
                self.gameloop.cancel()

        # More than 2 players still alive.
        else:

            # There are still alive demons.
            if BOTCUtils.has_alive_demons():
                # There is at least one alive good player. The game continues.
                alives = self.list_alive_players
                for player in alives:
                    if player.role.true_self.is_good():
                        return
                # The remaining players are all evil. The demon can't be nominated, and evil wins.
                else:
                    self.winners = Team.evil
                    self.gameloop.cancel()

            # There is no alive demon. The game is over with Good win.
            else:
                self.winners = Team.good
                self.gameloop.cancel()

    async def end_game(self):
        """End the game, compute winners etc.
        Must be implemented.
        """
        # Send the lobby game conclusion message
        await self.send_lobby_closing_message()
        # Remove roles
        await botutils.remove_all_alive_dead_roles_after_game()
        # Unload extensions
        if self.gamemode == Gamemode.trouble_brewing:
            globvars.client.unload_extension("botc.commands.abilities.tb")
        elif self.gamemode == Gamemode.bad_moon_rising:
            globvars.client.unload_extension("botc.commands.abilities.bmr")
        elif self.gamemode == Gamemode.sects_and_violets:
            globvars.client.unload_extension("botc.commands.abilities.snv")
        
        globvars.client.unload_extension("botc.commands.townhall")
        globvars.client.unload_extension("botc.commands.debug")
        # Load conflicting commands
        for extension in CONFLICTING_CMDS:
            globvars.client.load_extension(extension)
        # Log the game
        await botutils.log(botutils.Level.info, "Game finished")
        # Stop various loops from running
        from botc.gameloops import nomination_loop, base_day_loop
        # Stop the nomination loop if it is running
        if nomination_loop.is_running():
            nomination_loop.cancel()
        # Stop the base day loop if it is running
        if base_day_loop.is_running():
            base_day_loop.cancel()
        # Stop the debate timer loop if it is running
        if debate_timer.is_running():
            debate_timer.cancel()
        # Clear the game object
        self.__init__(self._gamemode)
        globvars.master_state.game = None
        # Unlock the lobby channel
        await botutils.unlock_lobby()
        # Update the global state
        botutils.update_state_machine()

    async def make_nightfall(self):
        """Transition the game into night phase"""

        # Initialize the temporary night data set
        self.init_temporary_night_data()

        # Store the starting time
        self.night_start_time = datetime.datetime.now()

        # Initialize the master switches at the start of a phase
        import botc.switches
        botc.switches.init_switches()

        # Stop all tasks of the day phase
        if nomination_loop.is_running():
            nomination_loop.cancel()
        if base_day_loop.is_running():
            base_day_loop.cancel()
        if debate_timer.is_running():
            debate_timer.cancel()

        # Move the chrono forward by one phase
        self._chrono.next()

        # Prepare the phase announcement message
        embed = discord.Embed(
           description = botutils.BotEmoji.moon + " " + nightfall,
           color = CARD_NIGHT
        )
        embed.set_footer(text = copyrights_str)
        embed.set_image(url = nightfall_image)
        embed.timestamp = datetime.datetime.utcnow()
        await botutils.send_lobby(message = "", embed = embed)

        # Reset the nomination data for the previous day phase
        for player in self.sitting_order:
            player.reset_nomination()

    async def make_dawn(self):
        """Transition the game into dawn/interlude phase"""

        # Initalize the temporary dawn data
        self.init_temporary_dawn_data()

        # Store the starting time
        self.dawn_start_time = datetime.datetime.now()

        # Initialize the master switches at the start of a phase
        import botc.switches
        botc.switches.init_switches()

        # Move the chrono forward by one phase
        self._chrono.next()

        # Prepare the phase announcement message
        embed = discord.Embed(
           description = botutils.BotEmoji.sunrise + " " + dawn,
           color = CARD_DAWN
        )
        embed.set_footer(text = copyrights_str)
        embed.set_image(url = dawn_image)
        embed.timestamp = datetime.datetime.utcnow()
        await botutils.send_lobby(message = "", embed = embed)

    async def make_daybreak(self):
        """Transition the game into day phase"""

        # Initialize the temporary day data set
        self.init_temporary_day_data()

        # Store the starting time
        self.day_start_time = datetime.datetime.now()

        # Initialize the master switches at the start of a phase
        import botc.switches
        botc.switches.init_switches()

        # Move the chrono forward by one phase
        self._chrono.next()

        # Prepare the phase announcement message
        # Night 1 end is Storyteller death
        if self._chrono.cycle == 1 and self._chrono.phase == Phase.day:
            final_death_message = storyteller_death

        # Not night 1 end, we look at the death list
        else:

            night_deaths_names = [player.game_nametag for player in self.night_deaths]
            night_deaths_names = list(set(night_deaths_names))

            if len(night_deaths_names) == 0:
                death_messages = strings["lore"]["night_death"]["zero"]["outputs"]
                death_weights = strings["lore"]["night_death"]["zero"]["weights"]
                death_msg = random.choices(
                      death_messages,
                      weights = death_weights
                )
                final_death_message = death_msg[0]

            elif len(night_deaths_names) == 1:
                death_messages = strings["lore"]["night_death"]["singular"]["outputs"]
                death_weights = strings["lore"]["night_death"]["singular"]["weights"]
                death_msg = random.choices(
                      death_messages,
                      weights = death_weights
                )
                final_death_message = death_msg[0]
                final_death_message = final_death_message.format(
                   botutils.BotEmoji.murder,
                   night_deaths_names[0]
                )

            else:
                death_messages = strings["lore"]["night_death"]["plural"]["outputs"]
                death_weights = strings["lore"]["night_death"]["plural"]["weights"]
                death_msg = random.choices(
                      death_messages,
                      weights = death_weights
                )
                final_death_message = death_msg[0]
                final_death_message = final_death_message.format(
                   botutils.BotEmoji.murder,
                   ", ".join(night_deaths_names)
                )

        embed = discord.Embed(
           description = botutils.BotEmoji.sun + " " + daybreak + " " + final_death_message,
           color = CARD_DAY
        )
        embed.set_footer(text = copyrights_str)
        embed.set_image(url = daybreak_image)
        embed.timestamp = datetime.datetime.utcnow()

        await botutils.send_lobby(message = "", embed = embed)

    def generate_role_set(self):
        """Generate a list of roles according to the number of players"""

        num_player = len(self._member_obj_list)

        # Incorrect number of players
        if num_player > self.MAX_PLAYERS:
            raise TooManyPlayers("Must be 15 players or less.")

        elif num_player < self.MIN_PLAYERS:
            raise TooFewPlayers("Must be 5 players or more.")

        # Correct number of players
        else:
            role_guide = RoleGuide(num_player)
            nb_townsfolk = role_guide.nb_townsfolks
            nb_outsider = role_guide.nb_outsiders
            nb_minion = role_guide.nb_minions
            nb_demon = role_guide.nb_demons

            # Trouble brewing mode
            if self.gamemode == Gamemode.trouble_brewing:
                selected_gamemode = TroubleBrewing

            # Bad moon rising mode
            elif self.gamemode == Gamemode.bad_moon_rising:
                selected_gamemode = BadMoonRising

            # Sects and violets mode
            elif self.gamemode == Gamemode.sects_and_violets:
                selected_gamemode = SectsAndViolets

            else:
                raise GameError("Gamemode is not one of available BoTC editions.")

            townsfolk_all = BOTCUtils.get_role_list(selected_gamemode, Townsfolk)
            outsider_all = BOTCUtils.get_role_list(selected_gamemode, Outsider)
            minion_all = BOTCUtils.get_role_list(selected_gamemode, Minion)
            demon_all = BOTCUtils.get_role_list(selected_gamemode, Demon)

            ret_townsfolk = random.sample(townsfolk_all, nb_townsfolk)
            ret_outsider = random.sample(outsider_all, nb_outsider)
            ret_minion = random.sample(minion_all, nb_minion)
            ret_demon = random.sample(demon_all, nb_demon)

            final_townsfolk = ret_townsfolk.copy()
            final_outsider = ret_outsider.copy()
            final_minion = ret_minion.copy()
            final_demon = ret_demon.copy()

            prelim = ret_townsfolk + ret_outsider + ret_minion + ret_demon          
            for role in prelim:
                setup_next = role.exec_init_setup(final_townsfolk, final_outsider, final_minion, final_demon)
                final_townsfolk = setup_next[0]
                final_outsider = setup_next[1]
                final_minion = setup_next[2]
                final_demon = setup_next[3]

            setup = final_townsfolk + final_outsider + final_minion + final_demon
            random.shuffle(setup)

            return setup

    def distribute_roles(self, role_obj_list, member_obj_list):
        """Distribute the roles to the players"""

        if len(role_obj_list) != len(member_obj_list):
            raise GameError("Number of players not matching number of roles generated")

        else:
            ret = []
            for member in member_obj_list:
                role_obj = role_obj_list.pop()
                player_obj = Player(member, role_obj)
                ret.append(player_obj)

        self._player_obj_list = ret

    def generate_frozen_sitting(self):
        """Freeze the sittings of the table around the game table"""

        random.shuffle(self.player_obj_list)
        self._sitting_order = tuple(self._player_obj_list)
        globvars.logging.info(f"Sitting Order {str(self._sitting_order)}")

    def __repr__(self):
        return "Blood on the Clocktower"

    async def remove_left_guild_players(self):
        for member in self.member_obj_list:
            fetched_member = globvars.client.get_guild(SERVER_ID).get_member(int(member.id))
            if fetched_member == None: #player left guild
                self.invalidated = True
                for player in self._player_obj_list:
                    if player.user == member: #discord.py implements equality check between users and members

                        #We can't call player.exec_real_death() because we would then try to give a role to a nonexistent player
                        player.ghost_vote = 0
                        player._state_obj = PlayerState.dead
                        player._apparent_state_obj = PlayerState.dead

                        break
        await self.check_winning_conditions()
