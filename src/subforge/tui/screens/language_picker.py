"""Searchable ISO 639-1 language picker (PRD §16).

Type to filter the catalog (matches code or English name), ↑/↓ to move the
highlight, Enter/Tab to select, Esc to cancel. Focus stays on the search box
so typing keeps filtering — arrow/Tab keys are routed at the screen level.
"""

from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList

from subforge.tui.screens.languages import ISO_LANGUAGES, resolve_language


class LanguagePickerScreen(ModalScreen[str | None]):
    """Dismisses with an ISO code (or None on cancel)."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
    ]

    AUTO_FOCUS = "Input"

    def __init__(
        self,
        title: str,
        current: str = "",
        languages: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self.picker_title = title
        self.current = current.lower()
        self.languages = languages if languages is not None else ISO_LANGUAGES
        self.result: str | None = None
        self._applied_query: str = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[b]{self.picker_title}[/b]")
            yield Input(
                placeholder="type to filter — e.g. 'id', 'en', 'ja'…",
                id="lang-search",
                value=self.current,
            )
            yield OptionList(id="lang-list")
            yield Label("[dim]type filter · ↑↓ move · Enter select · Esc cancel[/dim]")

    def on_mount(self) -> None:
        self._refresh(self.current)

    # ---- filtering ---------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "lang-search":
            self._refresh(event.value.strip().lower())

    def _refresh(self, query: str) -> None:
        try:
            option_list = self.query_one("#lang-list", OptionList)
        except NoMatches:
            return  # pre-mount unit seam
        option_list.clear_options()
        if query:
            exact = [(c, n) for c, n in self.languages if c.lower() == query]
            rest = [
                (c, n)
                for c, n in self.languages
                if c.lower() != query and (c.lower().startswith(query) or query in n.lower())
            ]
            matches = exact + rest
        else:
            matches = list(self.languages)
        for code, name in matches:
            option_list.add_option(f"{code}  —  {name}")
        # Empty search shows the catalog but selects nothing — Enter means
        # "choose nothing" (callers map that to auto-detect/default).
        option_list.highlighted = 0 if (matches and query) else None
        self._applied_query = query

    def _selected_code(self) -> str | None:
        option_list = self.query_one("#lang-list", OptionList)
        if option_list.highlighted is None or option_list.option_count == 0:
            return None
        prompt = str(option_list.get_option_at_index(option_list.highlighted).prompt)
        return prompt.split("  —  ")[0]

    def _move(self, delta: int) -> None:
        option_list = self.query_one("#lang-list", OptionList)
        count = option_list.option_count
        if count == 0:
            return
        current = option_list.highlighted
        if current is None:
            option_list.highlighted = 0 if delta > 0 else count - 1
        else:
            option_list.highlighted = min(count - 1, max(0, current + delta))

    # ---- key routing -------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            event.stop()
            self._move(-1)
        elif event.key == "down":
            event.stop()
            self._move(1)
        elif event.key == "tab":
            event.stop()
            self._select()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "lang-search":
            return
        raw = event.input.value.strip().lower()
        # If the list hasn't caught up with the current query (the change event
        # is still queued, e.g. programmatic value set + immediate submit), sync
        # it first so the highlighted option matches what the user typed.
        if self._applied_query != raw:
            self._refresh(raw)
        code = self._selected_code() or resolve_language(raw)
        # Empty selection is a deliberate "no code" (auto-detect/default).
        self.result = code or None
        self.dismiss(self.result)

    def _select(self) -> None:
        code = self._selected_code()
        if code is not None:
            self.result = code
            self.dismiss(code)

    def action_cancel(self) -> None:
        self.dismiss(None)
