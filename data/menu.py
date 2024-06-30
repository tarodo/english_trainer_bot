from dataclasses import dataclass, field


@dataclass
class BotMenu:
    prefix: str
    buttons: list[tuple[str, str]] = field(default_factory=list)
    number: int = 2


main_bot_menu = BotMenu(
    prefix="main",
    buttons=[
        ("📚 Учить слова", "words"),
        ("📝 Статистика", "stats"),
        ("🔧 Настройки", "settings"),
    ],
)