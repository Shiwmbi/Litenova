"""
Litenova Grid/List Performance and Floating Window Fix

Updates:
    app/pages/library_page.py
    app/widgets/book_card.py

Features:
    - Faster Grid/List switching
    - Reuses existing book cards
    - Reuses loaded cover images
    - Prevents detached book-card windows
    - Preserves Library features and settings

The original files are backed up before modification.
"""

import ast

from pathlib import Path
from shutil import copy2


# ============================================================
# PROJECT FILES
# ============================================================

ROOT = Path(__file__).resolve().parent

LIBRARY = (
    ROOT
    / "app"
    / "pages"
    / "library_page.py"
)

CARD = (
    ROOT
    / "app"
    / "widgets"
    / "book_card.py"
)

MARKER = "# LITENOVA_FAST_VIEW_SWITCH_V3"


# ============================================================
# REPLACE AN EXISTING LIBRARY METHOD
# ============================================================

def replace_method(source, name, replacement):

    tree = ast.parse(source)

    page = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "LibraryPage"
    )

    method = next(
        node
        for node in page.body
        if isinstance(node, ast.FunctionDef)
        and node.name == name
    )

    lines = source.splitlines(keepends=True)

    lines[
        method.lineno - 1:method.end_lineno
    ] = [
        replacement.rstrip() + "\n"
    ]

    return "".join(lines)


# ============================================================
# UPDATE LIBRARY PAGE
# ============================================================

def change_library(source):

    if MARKER in source:
        return source

    if "_activate_cached_view" in source:

        raise RuntimeError(
            "A different Grid/List cache fix is already "
            "installed. No files were changed."
        )

    # ========================================================
    # INITIALIZE THE CARD CACHE
    # ========================================================

    target = (
        "        self.cards = []\n\n"
        "        self._last_layout_width = 0"
    )

    if source.count(target) != 1:

        raise RuntimeError(
            "Cannot locate Library initialization. "
            "No files were changed."
        )

    source = source.replace(
        target,
        '''
        self.cards = []

        # LITENOVA_FAST_VIEW_SWITCH_V3

        self._view_cards = {
            "grid": None,
            "list": None,
        }

        self._visible_books = []

        self._visible_progress = {}

        self._layout_signature = None

        self._reflowing = False

        self._switching_view = False

        self._last_layout_width = 0''',
        1,
    )

    # ========================================================
    # GRID VIEW
    # ========================================================

    source = replace_method(
        source,
        "show_grid_view",
        '''
    def show_grid_view(self):

        if self.display_mode == "grid":
            return

        self.display_mode = "grid"

        self.preferences.setValue(
            "library_display_mode",
            "grid",
        )

        self.update_mode_buttons()

        self._activate_cached_view()
''',
    )

    # ========================================================
    # LIST VIEW
    # ========================================================

    source = replace_method(
        source,
        "show_list_view",
        '''
    def show_list_view(self):

        if self.display_mode == "list":
            return

        self.display_mode = "list"

        self.preferences.setValue(
            "library_display_mode",
            "list",
        )

        self.update_mode_buttons()

        self._activate_cached_view()
''',
    )

    # ========================================================
    # CACHE THE CURRENT BOOK DATA
    # ========================================================

    load_start = source.index(
        "    def load_books("
    )

    clear_call = source.index(
        "        self.clear_books()",
        load_start,
    )

    source = (
        source[:clear_call]
        + '''
        # Save the current books and reading progress.
        # Switching views will reuse this information.

        self._visible_books = books

        self._visible_progress = progress_by_id

'''
        + source[clear_call:]
    )

    # ========================================================
    # REPLACE THE OLD CARD CREATION LOOP
    # ========================================================

    load_start = source.index(
        "    def load_books("
    )

    create_heading = source.index(
        "        # CREATE NEW CARDS",
        load_start,
    )

    cards_start = source.index(
        "        for book in books:",
        create_heading,
    )

    count_heading = source.index(
        "        # BOOK COUNT",
        cards_start,
    )

    block_end = source.rfind(
        "        # ====================================================",
        cards_start,
        count_heading,
    )

    if block_end < cards_start:

        raise RuntimeError(
            "Cannot identify the card-creation block. "
            "No files were changed."
        )

    source = (
        source[:cards_start]
        + '''
        self.cards = self._create_view_cards(
            self.display_mode,
            cover_width,
        )

        self._view_cards[self.display_mode] = self.cards

        self._layout_signature = None

'''
        + source[block_end:]
    )

    # ========================================================
    # CLEAR OLD CARDS AND MANAGE THE VIEW CACHE
    # ========================================================

    source = replace_method(
        source,
        "clear_books",
        '''
    def clear_books(self):
        """
        Clear both cached views safely.

        All book cards remain children of the
        Library container during removal.
        """

        self._resize_timer.stop()

        self._layout_signature = None

        # Hide existing cards before changing the layout.

        for cards in self._view_cards.values():

            for card in cards or []:

                card.hide()

        # Remove widgets from the layout.

        while self.books_layout.count():

            item = self.books_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:

                widget.hide()

                if widget not in self.cards:

                    widget.deleteLater()

        # Schedule the previous cached cards for deletion.

        for cards in self._view_cards.values():

            for card in cards or []:

                card.deleteLater()

        self._view_cards = {
            "grid": None,
            "list": None,
        }

        self.cards = []

    # ========================================================
    # CREATE AND CACHE BOOK CARDS
    # ========================================================

    def _create_view_cards(self, mode, cover_width):
        """
        Create book cards for one display mode.

        Reuse decoded cover images when possible.

        Every card has an explicit Library parent,
        preventing it from becoming a separate window.
        """

        opposite = (
            "list"
            if mode == "grid"
            else "grid"
        )

        other = (
            self._view_cards.get(opposite)
            or []
        )

        covers = {
            card.book["id"]: card.original_cover
            for card in other
        }

        cards = []

        for book in self._visible_books:

            card = BookCard(
                book,
                mode=mode,
                cover_width=cover_width,
                progress=self._visible_progress.get(
                    book["id"],
                    0.0,
                ),
                show_progress=(
                    self.show_progress_box.isChecked()
                ),
                show_read_button=(
                    self.show_read_box.isChecked()
                ),
                parent=self.books_container,
                original_cover=covers.get(
                    book["id"]
                ),
            )

            # Do not display the card until it has
            # been added to the correct layout.

            card.hide()

            card.clicked.connect(
                self.book_open_requested.emit
            )

            card.edit_requested.connect(
                self.edit_book
            )

            card.move_requested.connect(
                self.move_book
            )

            card.remove_requested.connect(
                self.confirm_remove_book
            )

            cards.append(card)

        return cards

    # ========================================================
    # SWITCH BETWEEN CACHED VIEWS
    # ========================================================

    def _activate_cached_view(self):
        """
        Switch display modes without repeatedly
        loading books or decoding cover images.
        """

        if self._switching_view:
            return

        if not self._visible_books:

            self.load_books()

            return

        self._switching_view = True

        self._resize_timer.stop()

        scroll = (
            self.scroll_area
            .verticalScrollBar()
            .value()
        )

        # Pause painting while rearranging book cards.

        self.scroll_area.setUpdatesEnabled(False)

        try:

            # Hide the previous view.

            for card in self.cards:

                card.hide()

            # Remove previous layout entries.

            while self.books_layout.count():

                self.books_layout.takeAt(0)

            # Retrieve the cached cards for the new mode.

            desired = self._view_cards.get(
                self.display_mode
            )

            # Create the alternate mode only once.

            if desired is None:

                width = self.current_cover_width()

                desired = self._create_view_cards(
                    self.display_mode,
                    width,
                )

                self._view_cards[self.display_mode] = (
                    desired
                )

                if self.display_mode == "grid":

                    self._cards_cover_width = width

            self.cards = desired

            self._layout_signature = None

            self.reflow_cards()

        finally:

            self.scroll_area.setUpdatesEnabled(True)

            self._switching_view = False

        # Restore the previous scroll position.

        self.scroll_area.verticalScrollBar().setValue(
            scroll
        )
''',
    )

    # ========================================================
    # FAST AND SAFE CARD LAYOUT
    # ========================================================

    source = replace_method(
        source,
        "reflow_cards",
        '''
    def reflow_cards(self):
        """
        Rearrange book cards without detaching
        them from the Library container.

        Avoid repeated layout operations when
        the available dimensions have not changed.
        """

        if self._reflowing or not self.cards:
            return

        available = max(
            200,
            self.scroll_area.viewport().width() - 6,
        )

        # ====================================================
        # CALCULATE COLUMNS
        # ====================================================

        if self.display_mode == "list":

            columns = 1

        else:

            # Handle automatic grid resizing.

            if self.grid_slider.value() == 0:

                width = self.current_cover_width()

                if width != self._cards_cover_width:

                    previous = (
                        self._view_cards.get("grid")
                        or []
                    )

                    for card in previous:

                        card.hide()

                    while self.books_layout.count():

                        self.books_layout.takeAt(0)

                    self._cards_cover_width = width

                    # Rebuild only the grid cache.
                    # Reuse cover images from the list cache.

                    self.cards = self._create_view_cards(
                        "grid",
                        width,
                    )

                    self._view_cards["grid"] = self.cards

                    for card in previous:

                        card.deleteLater()

                    self._layout_signature = None

            card_width = self.cards[0].width()

            columns = max(
                1,
                (available + 22)
                // (card_width + 22),
            )

        # ====================================================
        # AVOID UNNECESSARY LAYOUT UPDATES
        # ====================================================

        signature = (
            self.display_mode,
            columns,
            (
                available
                if self.display_mode == "list"
                else 0
            ),
            id(self.cards),
        )

        if signature == self._layout_signature:
            return

        # ====================================================
        # UPDATE THE LAYOUT
        # ====================================================

        self._reflowing = True

        self.books_container.setUpdatesEnabled(False)

        try:

            # Hide cards while changing their positions.

            for card in self.cards:

                card.hide()

            while self.books_layout.count():

                self.books_layout.takeAt(0)

            # Add the cards to their correct positions.

            for index, card in enumerate(self.cards):

                if self.display_mode == "list":

                    card.setFixedWidth(
                        max(
                            200,
                            available - 8,
                        )
                    )

                self.books_layout.addWidget(
                    card,
                    index // columns,
                    index % columns,
                    Qt.AlignTop,
                )

            # Show cards after the layout is complete.

            for card in self.cards:

                card.show()

            self._layout_signature = signature

        finally:

            self.books_container.setUpdatesEnabled(True)

            self._reflowing = False
''',
    )

    # ========================================================
    # CHECK UPDATED LIBRARY CODE
    # ========================================================

    compile(
        source,
        str(LIBRARY),
        "exec",
    )

    return source


# ============================================================
# UPDATE BOOK CARD
# ============================================================

def change_card(source):

    # Already supports cached cover images.

    if "original_cover=None," in source:
        return source

    header = (
        "        show_read_button=True, parent=None,\n"
    )

    previous = (
        "        self.original_cover = self.load_original_cover()"
    )

    if (
        source.count(header) != 1
        or source.count(previous) != 1
    ):

        raise RuntimeError(
            "BookCard structure differs from the "
            "uploaded version. No files were changed."
        )

    # Allow the Library to supply an existing pixmap.

    source = source.replace(
        header,
        (
            "        show_read_button=True, "
            "parent=None, original_cover=None,\n"
        ),
        1,
    )

    # Reuse the cover when an existing one is available.

    source = source.replace(
        previous,
        '''
        self.original_cover = (
            original_cover
            if original_cover is not None
            else self.load_original_cover()
        )''',
        1,
    )

    # Check updated BookCard code.

    compile(
        source,
        str(CARD),
        "exec",
    )

    return source


# ============================================================
# APPLY THE FIX
# ============================================================

def main():

    # ========================================================
    # CHECK PROJECT FILES
    # ========================================================

    if not LIBRARY.is_file() or not CARD.is_file():

        raise SystemExit(
            "Place this script beside main.py "
            "in your Litenova project folder."
        )

    # ========================================================
    # READ CURRENT FILES
    # ========================================================

    old_library = LIBRARY.read_text(
        encoding="utf-8-sig"
    )

    old_card = CARD.read_text(
        encoding="utf-8-sig"
    )

    # ========================================================
    # PREPARE BOTH UPDATED FILES
    # ========================================================

    new_library = change_library(
        old_library
    )

    new_card = change_card(
        old_card
    )

    if (
        new_library == old_library
        and new_card == old_card
    ):

        print(
            "This fix is already installed."
        )

        return

    # ========================================================
    # BACK UP AND SAVE
    # ========================================================

    for path, old, new in (
        (
            LIBRARY,
            old_library,
            new_library,
        ),
        (
            CARD,
            old_card,
            new_card,
        ),
    ):

        if new == old:
            continue

        backup = path.with_name(
            path.name + ".before_fast_switch.bak"
        )

        if not backup.exists():

            copy2(
                path,
                backup,
            )

        path.write_text(
            new,
            encoding="utf-8",
        )

        print(
            "Updated:",
            path.relative_to(ROOT),
        )

    print(
        "Done. Run: python main.py"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()