from discord.ext import commands

from utils.logger import logger
import requests
import discord
from telegram_bot.senders import send_telegram_message, send_telegram_photo
from config import DISCORD_GUILD_ID, BOT_USERNAME,INVITE_ROLE, DISCORD_CHANNEL_ID
import threading
from utils.mini_utils import run_in_thread
from telegram_bot.senders import send_verify_msg

bot: commands.Bot | None  = None
INVITES:list[discord.Invite] = []

def get_invites():
    return INVITES

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def register_handlers(local_bot: commands.Bot ):
    global bot
    bot = local_bot

    bot.add_command(tg)
    bot.event(on_member_join) 

async def on_member_join(member:discord.Member):
    global INVITES
    not_bot_url= True
    # nowinvites = {inv.code: inv for inv in await bot.get_guild(DISCORD_GUILD_ID).invites()}
    # for i in INVITES:
    #     if nowinvites.get(i.code).uses != i.uses:
    #         if nowinvites.get(i.code).inviter!=BOT_USERNAME:
    #             currentinv:discord.Invite = await  bot.fetch_invite(i.code)
    #             await currentinv.delete(reason=f"Было использовано {member.name}")
    #             role = member.guild.get_role(INVITE_ROLE)
    #             if role:
    #                 await member.add_roles(role)
    #                 await bot.get_channel(DISCORD_CHANNEL_ID).send(f"Новый пидор в дискорде <@{member.id}> по приглашению бота")
    #                 threading.Thread(target=send_telegram_message, args=("Server", f"Новый пидор в дискорде `{member.name}` по приглашению бота")).start()
    #                 not_bot_url=False
    #         break
    # INVITES = await bot.get_guild(DISCORD_GUILD_ID).invites()

    if not_bot_url:
        run_in_thread(send_verify_msg, member.id, member.name)
        

@commands.command(name="tg")
@commands.has_role("telegram")
async def tg(ctx):
    if ctx.message.author.bot:
        return
    message_text = ctx.message.content[4:].strip()
    author = ctx.message.author
    if message_text:
        send_telegram_message(author, message_text)

    for attachment in ctx.message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"): 
            photo_bytes = requests.get(attachment.url).content
            send_telegram_photo(author, photo_bytes)
    await ctx.message.add_reaction('✅')
@tg.error
async def tg_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.message.add_reaction('❌')
