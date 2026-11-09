"""Central handlers router.

Combines all sub-routers into one main router.
This keeps bot.py clean and makes adding new features easy.
"""

from aiogram import Router

from ratemypic.handlers.edit import router as edit_router
from ratemypic.handlers.menu import router as menu_router
from ratemypic.handlers.posts import router as posts_router
from ratemypic.handlers.rating import router as rating_router
from ratemypic.handlers.registration import router as registration_router

router = Router()

# The command router comes first so /edit and /cancel work during any flow.
# Rating comes before menu so "menu:rate" reaches its handler.
router.include_router(edit_router)
router.include_router(registration_router)
router.include_router(rating_router)
router.include_router(menu_router)
router.include_router(posts_router)
