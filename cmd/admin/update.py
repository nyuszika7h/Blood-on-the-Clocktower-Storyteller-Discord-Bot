"""Contains the update command cog"""

import json
import os
import subprocess
import sys
import traceback

from discord.ext import commands

import botutils
import globvars

with open("botutils/bot_text.json") as json_file:
    language = json.load(json_file)

error_str = language["system"]["error"]


class Update(commands.Cog, name = language["system"]["admin_cog"]):
    """Update command"""

    def __init__(self, client):
        self.client = client

    def cog_check(self, ctx):
        return botutils.check_if_admin(ctx)

    # ---------- UPDATE command ----------------------------------------
    @commands.command(
        pass_context = True,
        name = "update",
        hidden = False,
        brief = language["doc"]["update"]["brief"],
        help = language["doc"]["update"]["help"],
        description = language["doc"]["update"]["description"]
    )
    async def update(self, ctx):
        """Update command"""

        p = subprocess.run(["git", "-C", os.path.dirname(sys.argv[0]), "pull", "--stat", "--ff-only"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        await ctx.send(botutils.create_code_block(p.stdout.decode("utf-8")))

        if p.returncode != 0:
            await ctx.send(language["cmd"]["update_exitcode"].format(p.returncode))
            return

        if b"Already up to date" in p.stdout:
            return

        if globvars.master_state.game:
            await ctx.send(language["cmd"]["frestart_confirm"].format(ctx.author.mention, botutils.BotEmoji.cross))
            return

        await ctx.send(language["cmd"]["frestart"].format(ctx.author.mention, botutils.BotEmoji.success))
        os.execl(sys.executable, sys.executable, *sys.argv)

    @update.error
    async def update_error(self, ctx, error):
        """Update command error handling"""
        if isinstance(error, commands.CheckFailure):
            return
        else:
            try:
                raise error
            except Exception:
                await ctx.send(error_str)
                await botutils.log(botutils.Level.error, traceback.format_exc())
