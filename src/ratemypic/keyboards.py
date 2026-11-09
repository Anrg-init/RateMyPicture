"""Telegram inline button keyboards.

This file only contains helper functions that create clickable buttons for users.
"""

from typing import Literal

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


ButtonStyle = Literal["primary", "success", "danger"]


def button(
    text: str,
    callback_data: str,
    style: ButtonStyle = "primary",
) -> InlineKeyboardButton:
    """Create a consistently styled inline button."""
    return InlineKeyboardButton(text=text, callback_data=callback_data, style=style)


def language_keyboard() -> InlineKeyboardMarkup:
    """Buttons for selecting preferred language."""
    buttons = [
        [
            button(text="🇬🇧 English", callback_data="lang:en"),
            button(text="🇷🇺 Русский", callback_data="lang:ru"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def terms_keyboard() -> InlineKeyboardMarkup:
    """Buttons for accepting or declining the Terms of Service."""
    buttons = [
        [
            button(text="✅ I Agree", callback_data="terms:accept", style="success"),
            button(text="❌ Decline", callback_data="terms:decline", style="danger"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def location_keyboard() -> InlineKeyboardMarkup:
    """Button allowing the user to skip the optional location question."""
    buttons = [
        [
            button(text="⏩ Skip location", callback_data="loc:skip"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu buttons shown to registered users."""
    buttons = [
        [
            button(text="📊 My Profile", callback_data="menu:feedback"),
        ],
        [
            button(text="⭐ Rate Photos", callback_data="menu:rate", style="success"),
        ],
        [
            button(text="✏️ Edit Profile & Posts", callback_data="edit:home"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_home_keyboard() -> InlineKeyboardMarkup:
    """Main choices in the account edit area."""
    buttons = [
        [button(text="👤 Edit Profile", callback_data="edit:profile")],
        [button(text="📸 Edit My Posts", callback_data="edit:posts:0")],
        [button(text="🗑 Delete Account", callback_data="edit:account:delete", style="danger")],
        [button(text="🏠 Main Menu", callback_data="menu:back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_edit_keyboard() -> InlineKeyboardMarkup:
    """Choices for editing the user's profile fields."""
    buttons = [
        [button(text="✏️ Change Name", callback_data="edit:profile:name")],
        [button(text="🎂 Change Age", callback_data="edit:profile:age")],
        [button(text="📍 Change Location", callback_data="edit:profile:location")],
        [button(text="Clear Location", callback_data="edit:profile:location:clear", style="danger")],
        [button(text="⬅️ Edit Menu", callback_data="edit:home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_posts_keyboard(
    posts: list[tuple[int, str]],
    offset: int,
    has_next: bool,
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
                text="⬅️ Previous",
                callback_data=f"edit:posts:{max(0, offset - 10)}",
            )
        )
    if has_next:
        navigation.append(
            button(
                text="Next ➡️",
                callback_data=f"edit:posts:{offset + 10}",
            )
        )
    if navigation:
        buttons.append(navigation)
    buttons.append([button(text="⬅️ Edit Menu", callback_data="edit:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_post_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Actions available for one of the user's posts."""
    buttons = [
        [button(text="✏️ Edit Caption", callback_data=f"edit:post:caption:{post_id}")],
        [button(text="🖼 Manage Photos", callback_data=f"edit:post:photo:{post_id}")],
        [button(text="🗑 Delete Post", callback_data=f"edit:post:delete:{post_id}", style="danger")],
        [button(text="⬅️ My Posts", callback_data="edit:posts:0")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_post_photo_keyboard(post_id: int, photo_count: int) -> InlineKeyboardMarkup:
    """Let the owner choose which existing photo to replace."""
    buttons = [
        [button(
            text=f"Replace photo {photo_number}",
            callback_data=f"edit:post:photo:{post_id}:{photo_number}",
        )]
        for photo_number in range(1, photo_count + 1)
    ]
    buttons.append([
        button(text="⬅️ Back to Post", callback_data=f"edit:item:{post_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_keyboard(confirm_data: str, cancel_data: str) -> InlineKeyboardMarkup:
    """Confirmation buttons for irreversible deletions."""
    buttons = [[
        button(text="🗑 Yes, delete", callback_data=confirm_data, style="danger"),
        button(text="Cancel", callback_data=cancel_data),
    ]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def empty_posts_keyboard() -> InlineKeyboardMarkup:
    """Buttons shown when user has no posts yet."""
    buttons = [
        [
            button(text="📸 Post a Photo", callback_data="post:create", style="success"),
        ],
        [
            button(text="🏠 Main Menu", callback_data="menu:back"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def posts_list_keyboard() -> InlineKeyboardMarkup:
    """Buttons shown below the list of user's posts."""
    buttons = [
        [
            button(text="➕ Add Another Photo", callback_data="post:create", style="success"),
        ],
        [
            button(text="🏠 Main Menu", callback_data="menu:back"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_post_keyboard() -> InlineKeyboardMarkup:
    """Button to cancel post creation."""
    buttons = [
        [
            button(text="❌ Cancel", callback_data="post:cancel", style="danger"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def post_photo_count_keyboard() -> InlineKeyboardMarkup:
    """Let the user choose how many photos to include in a post."""
    buttons = [[
        button(text="1 photo", callback_data="post:count:1"),
        button(text="2 photos", callback_data="post:count:2"),
        button(text="3 photos", callback_data="post:count:3"),
    ]]
    buttons.append([
        button(text="❌ Cancel", callback_data="post:cancel", style="danger")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def star_rating_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Rating buttons and a link to the post's comments."""
    buttons = [
        [
            button(text="1 · 😭🙈", callback_data=f"rate:{post_id}:1", style="danger"),
            button(text="2 · 😕😿", callback_data=f"rate:{post_id}:2", style="danger"),
            button(text="3 · 😽🤔", callback_data=f"rate:{post_id}:3"),
            button(text="4 · 🙌😼", callback_data=f"rate:{post_id}:4", style="success"),
            button(text="5 · 🙀🤩", callback_data=f"rate:{post_id}:5", style="success"),
        ],
        [
            button(
                text="💬 Show comments",
                callback_data=f"comments:{post_id}:0",
                style="primary",
            ),
        ],
        [
            button(text="🏠 Main Menu", callback_data="menu:back"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def post_comments_keyboard(
    post_id: int,
    offset: int,
    has_previous: bool,
    has_next: bool,
) -> InlineKeyboardMarkup:
    """Buttons for moving through a post's comment pages."""
    buttons = []
    navigation_row = []

    if has_previous:
        navigation_row.append(
            button(
                text="⬅️ Previous",
                callback_data=f"comments:{post_id}:{max(0, offset - 5)}",
            )
        )
    if has_next:
        navigation_row.append(
            button(
                text="Next ➡️",
                callback_data=f"comments:{post_id}:{offset + 5}",
            )
        )
    if navigation_row:
        buttons.append(navigation_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def skip_comment_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Button to skip adding an optional comment after rating."""
    buttons = [
        [
            button(text="⏩ Skip Comment", callback_data=f"skipcomment:{post_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def no_more_posts_keyboard() -> InlineKeyboardMarkup:
    """Shown when the user has rated all available posts."""
    buttons = [
        [
            button(text="🏠 Main Menu", callback_data="menu:back"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
