"""The site footer: whose copyright it is, a line about the app, and its links.

Every page ends with it (DESIGN.md, "Every site has a legit footer"); the
``site_footer`` tag in ``templatetags/site_footer.py`` draws it. Set once by
the project template from its answers; edit freely.
"""

# The footer's copyright line: "© <this year> <holder>. All rights reserved."
COPYRIGHT_HOLDER = "Hugo Rodger-Brown"

# One line under the app's name, saying what it is. Empty for none.
TAGLINE = "Who's skiing where, for friends."

# The footer's links, in order: (label, URL name). A "#fragment" after the
# name links to a part of that page, e.g. ("Use with Claude", "public:home#mcp").
# Keep the terms and privacy notice: a site without them isn't legit.
LINKS: list[tuple[str, str]] = [
    ("About", "public:home"),
    ("Help", "public:help"),
    ("Use with Claude", "public:home#ask"),
    ("Terms", "public:terms"),
    ("Privacy", "public:privacy"),
]
