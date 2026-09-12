"""

В каком порядке импортируешь handler'ы в том порядке и проверяется условия.
Вызывается первый подходящий по условиям, так что в начале не должно быть чего то типо:

@bot.message_handler( )

поскольку у него нет условий, он подходит, а значит каждое сообшение будет
тригерить только этот handler

"""


from .commands_not_from_group import *
from .photo_sorting import *

from .only_from_group import * #Этот хэндлер забирает на себя все сообщения не из группы, так что если надо не с группы, импорт хэндлера выше

from .photo_change_poll import *
from .ignore_users import *
from .discord_commands import *
from .tags import *
from .commands import *
from .statistics import *
from .callbacks import *
