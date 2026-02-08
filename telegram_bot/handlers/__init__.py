"""

В каком порядке импортируешь handler'ы в том порядке и проверяется условия.
Вызывается первый подходящий по условиям, так что в начале не должно быть чего то типо:

@bot.message_handler( )

поскольку у него нет условий, он подходит, а значит каждое сообшение будет
тригерить только этот handler

"""


from .ignore_users import *
from .discord_commands import *
from .tags import *
from .commands import *
from .statistics import *
from .callbacks import *
