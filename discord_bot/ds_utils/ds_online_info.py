from ..bot import bot
from config import DISCORD_CHANNEL_ID
from utils.logger import logger

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
async def get_online_info():
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        return "Ошибка: канал не найден"
    guild = channel.guild
    info_list = []
    for vc in guild.voice_channels:
        if vc.members:
            members_names = [f"{m.display_name}{' [В эфире🖥️]' if m.voice.self_stream else ''}" for m in vc.members]
            info_list.append(f"🔊 `{vc.name}`\n ```ini\n{'\n'.join(members_names)}\n```")
    if info_list:
        return '\n\n'.join(info_list)
    else:
        return "`Дискорд пустой`"