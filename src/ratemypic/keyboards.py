"""Telegram inline button keyboards.

This file only contains helper functions that create clickable buttons for users.
"""

from typing import Literal
from .i18n import t, SUPPORTED_LANGUAGES

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


ButtonStyle = Literal["primary", "success", "danger"]


def button(
    text: str,
    callback_data: str,
    style: ButtonStyle = "primary",
) -> InlineKeyboardButton:
    """Create a consistently styled inline button."""
    return InlineKeyboardButton(text=text, callback_data=callback_data, style=style)


def language_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Buttons for selecting preferred language, fully localized."""
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, code in enumerate(SUPPORTED_LANGUAGES.keys(), start=1):
        row.append(button(text=t(f"button.language.{code}", lang=lang), callback_data=f"lang:{code}"))
        if idx % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def terms_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Buttons for accepting or declining the Terms of Service."""
    buttons = [
        [
            button(text=t("terms.accept_button", lang=lang), callback_data="terms:accept", style="success"),
            button(text=t("terms.decline_button", lang=lang), callback_data="terms:decline", style="danger"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def location_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Button allowing the user to skip the optional location question."""
    buttons = [
        [
            button(text=t("button.skip_location", lang=lang), callback_data="loc:skip"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def main_menu_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Main menu buttons shown to registered users."""
    buttons = [
        [
            button(text=t("menu.profile", lang=lang), callback_data="menu:feedback"),
        ],
        [
            button(text=t("menu.rate", lang=lang), callback_data="menu:rate", style="success"),
        ],
        [
            button(text=t("menu.edit", lang=lang), callback_data="edit:home"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_home_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Main choices in the account edit area."""
    buttons = [
        [button(text=t("edit.profile", lang=lang), callback_data="edit:profile")],
        [button(text=t("edit.posts", lang=lang), callback_data="edit:posts:0")],
        [button(text=t("edit.delete_account", lang=lang), callback_data="edit:account:delete", style="danger")],
        [button(text=t("button.main_menu", lang=lang), callback_data="menu:back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_edit_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Choices for editing the user's profile fields."""
    buttons = [
        [button(text=t("edit.change_name", lang=lang), callback_data="edit:profile:name")],
        [button(text=t("edit.change_age", lang=lang), callback_data="edit:profile:age")],
        [button(text=t("edit.change_location", lang=lang), callback_data="edit:profile:location")],
        [button(text=t("edit.change_language", lang=lang), callback_data="edit:profile:language")],
        [button(text=t("edit.clear_location", lang=lang), callback_data="edit:profile:location:clear", style="danger")],
        [button(text=t("button.edit_menu", lang=lang), callback_data="edit:home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_posts_keyboard(
    posts: list[tuple[int, str]],
    offset: int,
    has_next: bool,
    lang: str = "en",
) -> InlineKeyboardMarkup:
    """Post choices and pagination controls for the edit area."""
    buttons = [
        [button(text=caption[:40], callback_data=f"edit:item:{post_id}")]
        for post_id, caption in posts
    ]
    navigation = []
    if offset > 0:
        navigation.append(
            button(
                text=t("button.previous", lang=lang),
                callback_data=f"edit:posts:{max(0, offset - 10)}",
            )
        )
    if has_next:
        navigation.append(
            button(
                text=t("button.next", lang=lang),
                callback_data=f"edit:posts:{offset + 10}",
            )
        )
    if navigation:
        buttons.append(navigation)
    buttons.append([button(text=t("button.edit_menu", lang=lang), callback_data="edit:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_post_keyboard(post_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    """Actions available for one of the user's posts."""
    buttons = [
        [button(text=t("edit.caption", lang=lang), callback_data=f"edit:post:caption:{post_id}")],
        [button(text=t("edit.photos", lang=lang), callback_data=f"edit:post:photo:{post_id}")],
        [button(text=t("edit.delete_post", lang=lang), callback_data=f"edit:post:delete:{post_id}", style="danger")],
        [button(text=t("button.my_posts", lang=lang), callback_data="edit:posts:0")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_post_photo_keyboard(post_id: int, photo_count: int, lang: str = "en") -> InlineKeyboardMarkup:
    """Let the owner choose which existing photo to replace."""
    buttons = [
        [button(
            text=t("edit.replace_photo", lang=lang, number=photo_number),
            callback_data=f"edit:post:photo:{post_id}:{photo_number}",
        )]
        for photo_number in range(1, photo_count + 1)
    ]
    buttons.append([
        button(text=t("button.back_to_post", lang=lang), callback_data=f"edit:item:{post_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_keyboard(confirm_data: str, cancel_data: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Confirmation buttons for irreversible deletions."""
    buttons = [[
        button(text=t("button.yes_delete", lang=lang), callback_data=confirm_data, style="danger"),
        button(text=t("button.cancel", lang=lang), callback_data=cancel_data),
    ]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def empty_posts_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Buttons shown when user has no posts yet."""
    buttons = [
        [
            button(text=t("button.post_photo", lang=lang), callback_data="post:create", style="success"),
        ],
        [
            button(text=t("button.main_menu", lang=lang), callback_data="menu:back"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def posts_list_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Buttons shown below the list of user's posts."""
    buttons = [
        [
            button(text=t("button.add_photo", lang=lang), callback_data="post:create", style="success"),
        ],
        [
            button(text=t("button.main_menu", lang=lang), callback_data="menu:back"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_post_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Button to cancel post creation."""
    buttons = [
        [
            button(text=t("button.cancel", lang=lang), callback_data="post:cancel", style="danger"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def post_photo_count_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Let the user choose how many photos to include in a post."""
    buttons = [[
        button(text=t("post.photo_count", lang=lang, count=1), callback_data="post:count:1"),
        button(text=t("post.photo_count", lang=lang, count=2), callback_data="post:count:2"),
        button(text=t("post.photo_count", lang=lang, count=3), callback_data="post:count:3"),
    ]]
    buttons.append([
        button(text=t("button.cancel", lang=lang), callback_data="post:cancel", style="danger")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def star_rating_keyboard(post_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    """Rating buttons (5 to 1), 8 social emoji reactions, and navigation."""
    buttons = [
        # Row 1: Core rating scale 5 to 1
        [
            button(text="5 ⭐", callback_data=f"rate:{post_id}:5", style="success"),
            button(text="4 ⭐", callback_data=f"rate:{post_id}:4", style="success"),
            button(text="3 ⭐", callback_data=f"rate:{post_id}:3"),
            button(text="2 ⭐", callback_data=f"rate:{post_id}:2", style="danger"),
            button(text="1 ⭐", callback_data=f"rate:{post_id}:1", style="danger"),
        ],
        # Row 2: Social reactions part 1 (4 emojis)
        [
            button(text="😭", callback_data=f"react:{post_id}:😭"),
            button(text="🤣", callback_data=f"react:{post_id}:🤣"),
            button(text="☠️", callback_data=f"react:{post_id}:☠️"),
            button(text="😍", callback_data=f"react:{post_id}:😍"),
        ],
        # Row 3: Social reactions part 2 (4 emojis)
        [
            button(text="💩", callback_data=f"react:{post_id}:💩"),
            button(text="🍑", callback_data=f"react:{post_id}:🍑"),
            button(text="🍌", callback_data=f"react:{post_id}:🍌"),
            button(text="🔥", callback_data=f"react:{post_id}:🔥"),
        ],
        # Row 4: Comments
        [
            button(
                text=t("rating.show_comments", lang=lang),
                callback_data=f"comments:{post_id}:0",
                style="primary",
            ),
        ],
        # Row 5: Main Menu
        [
            button(text=t("button.main_menu", lang=lang), callback_data="menu:back"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def post_comments_keyboard(
    post_id: int,
    offset: int,
    has_previous: bool,
    has_next: bool,
    lang: str = "en",
) -> InlineKeyboardMarkup:
    """Buttons for moving through a post's comment pages."""
    buttons = []
    navigation_row = []

    if has_previous:
        navigation_row.append(
            button(
                text=t("button.previous", lang=lang),
                callback_data=f"comments:{post_id}:{max(0, offset - 5)}",
            )
        )
    if has_next:
        navigation_row.append(
            button(
                text=t("button.next", lang=lang),
                callback_data=f"comments:{post_id}:{offset + 5}",
            )
        )
    if navigation_row:
        buttons.append(navigation_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def skip_comment_keyboard(post_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    """Button to skip adding an optional comment after rating."""
    buttons = [
        [
            button(text=t("rating.skip_comment", lang=lang), callback_data=f"skipcomment:{post_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def no_more_posts_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Shown when the user has rated all available posts."""
    buttons = [
        [
            button(text=t("button.main_menu", lang=lang), callback_data="menu:back"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
