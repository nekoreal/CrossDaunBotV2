from ..bot import get_bot
from config import DISCORD_CHANNEL_ID
from ..handlers import get_invites

bot = get_bot()

async def get_invite_link():
    INVITES = get_invites()
    inv = await bot.get_channel(DISCORD_CHANNEL_ID).create_invite(max_age=0, max_uses=0, unique=True)
    INVITES.append(inv)
    return f"`Server`: [Приглос в дс]({inv.url})"
