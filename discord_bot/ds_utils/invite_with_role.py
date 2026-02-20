from ..bot import get_bot
from config import DISCORD_CHANNEL_ID, DISCORD_GUILD_ID,INVITE_ROLE
from ..handlers import get_invites
from utils.logger import logger

bot = get_bot()

async def get_invite_link():
    INVITES = get_invites()
    inv = await bot.get_channel(DISCORD_CHANNEL_ID).create_invite(max_age=0, max_uses=0, unique=True)
    INVITES.append(inv)
    return f"`Server`: [Приглос в дс]({inv.url})"

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
async def verify_role(user_id): 
    guild = bot.get_guild(DISCORD_GUILD_ID) 
    if not guild:
        print("Ошибка: Сервер не найден")
        return
 
    member = await guild.fetch_member(user_id) 
    role = guild.get_role(INVITE_ROLE) 
    if role and member:
        await member.add_roles(role) 
        await bot.get_channel(DISCORD_CHANNEL_ID).send(f"Новый пидор в дискорде <@{user_id}>. Иди ебашь на завод")  