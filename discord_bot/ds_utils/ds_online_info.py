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

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
async def get_active_channels():
    """Возвращает список голосовых каналов с активными участниками"""
    active_channels = [] 
    for guild in bot.guilds: 
        for voice_channel in guild.voice_channels:  
            if len(voice_channel.members) > 0:
                active_channels.append({
                    'name': f"{guild.name}: {voice_channel.name}",
                    'id': voice_channel.id
                })  
    return active_channels

# Discord loop initialized!
# Developer zone 1251165685615427715
# Chil zone 848516385914617856
# Game zone 850430933643427860
# View zone 1363199548146585652
# Для Следящих и выше 766735044353196062
# Для помошников и выше 766735164545171526
# Для ГА и ЗГА 766735720387051530
# Тет-а-тет 1346985357069123704
# Гостевая 1339314394839912491