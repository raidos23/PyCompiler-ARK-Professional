# How to Create a Theme (QSS) for PyCompiler Pro++

Quick Navigation
- [Overview](#overview)
- [Directory Structure](#directory-structure)
- [How the App Chooses a Theme](#how-the-app-chooses-a-theme)
- [QSS Basics](#qss-basics-crash-course)
- [Theme Principles](#prime-quality-theme-principles)
- [Coverage Checklist](#coverage-checklist-recommended-selectors)
- [Theme Skeleton](#theme-skeleton-starter-template)
- [Naming & Display Name](#naming-and-display-name)
- [Dark vs Light](#dark-vs-light-themes-recommendations)
- [Testing](#testing-your-theme)
- [Troubleshooting](#troubleshooting)
- [Accessibility & Quality](#accessibility-and-quality-tips)
- [Reusing/Extending](#reusing-and-extending-existing-themes)
- [Logo Considerations](#logo-considerations)
- [Comprehensive Example](#comprehensive-example-broad-coverage)

This guide explains, in depth, how the theming system of PyCompiler Pro++ works, where to put your theme files, how the app loads and applies them, and how to build a prime‑quality theme that covers virtually every Qt widget and state.

## Overview {#overview}

- Theme format: Qt Style Sheets (QSS), a CSS‑like language for Qt widgets.
- Theme location: place .qss files in the project-level folder: `themes/`
- Selection:
  - In the app UI, click the theme button to choose a theme by name.
  - If you choose "System", the app auto-selects a theme by detecting OS color scheme and scanning the `themes/` folder for a filename keyword containing `dark` or `light`.
- Application:
  - The app reads the `*.qss` file and applies it globally (QApplication.setStyleSheet).
  - The app detects if the applied QSS is dark via a heuristic, and updates the sidebar logo accordingly.
- Logging: on theme load, the app logs which theme was applied.

## Directory Structure {#directory-structure}

```
PyCompiler_ARK++_3.2.3/
├─ themes/
│  ├─ MyNewTheme.qss          # your theme file(s)
│  ├─ Techno2.qss             # example (shipped)
│  └─ ...
```

## How the App Chooses a Theme {#how-the-app-chooses-a-theme}

- Manual selection: The file you pick in the theme dialog (by its display name derived from the filename) is applied.
- System mode: The app detects OS color scheme, then scans `themes/` for a file whose filename contains `dark` or `light`. If none is found, it falls back to the first available theme.
- Dark detection: A heuristic checks typical background/`window`/`base` color declarations. If the average luminance is low, the theme is considered dark; this also influences the sidebar logo used.

## QSS Basics (Crash Course) {#qss-basics-crash-course}

Qt Style Sheets are similar to CSS with Qt‑specific selectors:
- Widget selectors: `QPushButton`, `QLabel`, `QLineEdit`, etc.
- Object names: `QPushButton#btn_build_all` (matches a specific widget by `objectName`).
- Subcontrols: `QComboBox::drop-down`, `QScrollBar::handle`, `QTabBar::close-button`, etc.
- Pseudo-states: `:hover`, `:pressed`, `:disabled`, `:checked`, `:focus`, `:selected`.
- Order matters: write more general rules first and override with more specific ones later.

Useful docs: https://doc.qt.io/qt-6/stylesheet-reference.html

## Prime-Quality Theme Principles {#prime-quality-theme-principles}

- Consistency: keep radii, borders, paddings, and typography consistent across widgets.
- Contrast: ensure accessible color contrast (AA/AAA when possible).
- Hierarchy: define a base background and layered surfaces; use subtle borders/shadows.
- States: always style hover, pressed, focus, checked, and disabled states for clarity.
- Coverage: ensure every commonly used widget and subcontrol has a baseline style.
- Performance: avoid unnecessary wildcards or deep overrides that affect all widgets when not needed.

## Coverage Checklist (Recommended Selectors) {#coverage-checklist-recommended-selectors}

Start with these blocks to reach comprehensive coverage:

- Base and surfaces
  - `QWidget` (base), `QFrame`, `QGroupBox`, `QTextEdit`, `QPlainTextEdit`
- Buttons and variants
  - `QPushButton` (default / flat / :hover / :pressed / :disabled)
  - Specific actions by id: `#btn_build_all`, `#btn_cancel_all`, etc.
  - `QCommandLinkButton`
- Inputs
  - `QLineEdit`, `QLineEdit[readOnly="true"]`, `QLineEdit::clear-button`
  - `QSpinBox`, `QDoubleSpinBox`, `QAbstractSpinBox::up/down-button`, `::up/down-arrow`
  - `QComboBox`, `QComboBox::drop-down`, `QComboBox::down-arrow`, popup view via `QComboBox QAbstractItemView`
- Lists, trees, tables
  - `QListWidget`, `QListView`, `QTreeView`, `QTableView`, `QTreeWidget`, `QTableWidget`
  - Selection states `:selected` and `::item`
  - Headers: `QHeaderView::section`, `::up-arrow`, `::down-arrow`
  - Table corner: `QTableCornerButton::section`
- Tabs
  - `QTabWidget::pane`, `QTabWidget::tab-bar`
  - `QTabBar::tab` (top/bottom/left/right), `:selected`, `:hover`
  - Embedded controls: `QTabBar::scroller`, `QTabBar QToolButton`, `QTabBar::close-button`
  - Corner widgets: `QTabWidget::left-corner`, `::right-corner`
- Scrollbars
  - `QScrollBar` (v/h), `::handle`, `::add-line`, `::sub-line`, page areas (`::add-page`, `::sub-page`)
  - `QAbstractScrollArea::corner`
- Sliders
  - `QSlider::groove`, `::handle`, `::sub-page`, disabled subcontrols.
- Menus and bars
  - `QMenu`, `QMenu::item`, `QMenu::separator`, `QMenu::indicator`, `QMenuBar`, `QMenuBar::item`
- Toolbars and dock widgets
  - `QToolBar`, `QToolBar::separator`, `QToolBar::handle`, `QToolButton`
  - `QDockWidget`, `QDockWidget::title`, `::close-button`, `::float-button`
- Dialogs and areas
  - `QDialog`, `QMessageBox`, `QProgressDialog`
  - `QFileDialog` (its internal views), `QColorDialog`, `QFontDialog`
  - `QScrollArea`, `QMdiArea`, `QMdiSubWindow`, `QStackedWidget`
- Misc
  - `QToolTip`, `QLCDNumber`, `QDial`, `QCalendarWidget`
  - `QGraphicsView` (background)
  - Links via `QLabel { link-color: ... }`

## Theme Skeleton (Starter Template) {#theme-skeleton-starter-template}

Copy this into a new file like `themes/MyNewTheme.qss` and adjust colors.

```css
/* MyNewTheme — Starter Template */
/* Palette */
/* bg: #161a20, surface: #1e2430, text: #eef2f8, accent: #4aa8ff */

/***** Base *****/
QWidget { background: #161a20; color: #eef2f8; font-size: 14px; }
QFrame, QTextEdit, QPlainTextEdit, QGroupBox {
  background: #1e2430; border: 1px solid rgba(255,255,255,0.10); border-radius: 10px;
}

/***** Buttons *****/
QPushButton {
  background: #232a3a; color: #eef2f8; border: 1px solid rgba(255,255,255,0.14);
  border-radius: 10px; padding: 8px 14px; font-weight: 600;
}
QPushButton:hover   { background: #273043; }
QPushButton:pressed { background: #20283a; }
QPushButton:disabled{ color: #9aa4b3; background: #1c2332; border-color: rgba(255,255,255,0.08); }
QPushButton:default { border: 1px solid #4aa8ff; }

/***** Inputs *****/
QLineEdit, QTextEdit, QPlainTextEdit { background: #192030; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; padding: 6px 10px; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border-color: #4aa8ff; }
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { width: 18px; border: none; background: transparent; }
QComboBox { background: #1d2433; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; padding: 6px 30px 6px 10px; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: #192030; border: 1px solid rgba(255,255,255,0.14); }

/***** Views *****/
QListWidget, QTreeView, QTableView { background: #192030; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; }
QHeaderView::section { background: #1f2636; border: 1px solid rgba(255,255,255,0.14); }
QTableCornerButton::section { background: #1f2636; border: 1px solid rgba(255,255,255,0.14); }

/***** Tabs *****/
QTabWidget::pane { border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; background: #192030; }
QTabBar::tab { background: transparent; border: none; padding: 8px 12px; color: #cfd7e2; }
QTabBar::tab:selected { color: #fff; border-bottom: 2px solid #4aa8ff; }
QTabBar::scroller { width: 24px; }
QTabBar QToolButton { background: #232a3a; border: 1px solid rgba(255,255,255,0.14); border-radius: 8px; }

/***** Scrollbars *****/
QScrollBar:vertical { width: 10px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.16); border-radius: 6px; }
QScrollBar:horizontal { height: 10px; }
QScrollBar::handle:horizontal { background: rgba(255,255,255,0.16); border-radius: 6px; }

/***** Menus & Bars *****/
QMenu     { background: #192030; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; }
QMenuBar  { background: #1e2430; border-bottom: 1px solid rgba(255,255,255,0.10); }
QToolBar  { background: #1e2430; border: 1px solid rgba(255,255,255,0.10); }

/***** Tooltips & Progress *****/
QToolTip { background: #1e2430; border: 1px solid rgba(255,255,255,0.18); border-radius: 8px; }
QProgressBar { background: #182034; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; }
QProgressBar::chunk { background: #4aa8ff; border-radius: 8px; }
```

## Naming and Display Name {#naming-and-display-name}

- The theme selector presents a display name computed from the file name: underscores and dashes are converted to spaces, then title‑cased.
- Example: `my_super-dark_theme.qss` appears as "My Super Dark Theme".

## Dark vs Light Themes (Recommendations) {#dark-vs-light-themes-recommendations}

- If you want "System" mode to pick your theme automatically:
  - Include `dark` or `light` in the file name.
  - Ensure your QSS includes a base background (e.g., `QWidget { background: #... }`) so the heuristic can detect darkness.

## Testing Your Theme {#testing-your-theme}

1. Place your `.qss` in `themes/`.
2. Start the app and open the theme dialog; select your theme.
3. Verify logs (bottom log panel) for a "Theme applied" message and the filename.
4. Navigate across all tabs and dialogs; test hover/pressed/disabled/focus states.
5. If a widget looks unthemed, add or adjust a selector for it in your QSS.

Tip: keep your QSS structured by sections (Base, Buttons, Inputs, Views, Tabs, Scrollbars, Menus, Toolbars, DockWidgets, Dialogs, Misc) for maintainability.

## Troubleshooting {#troubleshooting}

- No effect? Ensure the QSS compiles: a stray brace/semicolon can stop parsing. Test smaller chunks.
- A widget ignores styles? Some native platform widgets or properties might not be stylable; try an alternative subcontrol or parent selector.
- Specificity conflicts: declare general styles first, override with specific selectors later.
- Performance: avoid overly broad `* { ... }` rules and prefer per‑widget selectors.

## Accessibility and Quality Tips {#accessibility-and-quality-tips}

- Maintain a minimum contrast ratio of 4.5:1 for body text, 3:1 for UI elements and large text.
- Always provide visible `:focus` states for keyboard navigation.
- Keep padding and hit targets generous (at least 36–40px height for primary buttons).
- Use a consistent border radius (e.g., 8–12px) for a coherent visual language.

## Reusing and Extending Existing Themes {#reusing-and-extending-existing-themes}

- Start from an existing theme (e.g., `Techno2.qss`) and adjust the palette.
- Replace only the blocks you need; leave other coverage in place to retain comprehensive styling.

## Logo Considerations {#logo-considerations}

- The app switches the sidebar logo depending on the detected dark/light mode of the applied QSS.
- If you use custom branding, ensure your logo is readable on dark and light backgrounds.

---

## Comprehensive Example (Broad Coverage) {#comprehensive-example-broad-coverage}

Below is a single QSS file example designed to cover a very broad set of Qt widgets and subcontrols. Use it as a reference and adapt the palette to your brand.

```css
/* CompleteCoverage — Demonstration Theme (Broad Coverage) */
/* Palette: tune freely */
/* bg: #161a20, surface: #1e2533, text: #eef2f8, accent: #4aa8ff, danger: #ff6b6e */

/***** Base *****/
QWidget { background: #161a20; color: #eef2f8; font-family: 'Inter','Segoe UI','Roboto',sans-serif; font-size: 14px; }
QFrame, QGroupBox, QTextEdit, QPlainTextEdit { background: #1e2533; border: 1px solid rgba(255,255,255,0.10); border-radius: 10px; }
QGroupBox { margin-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #dbe2ec; }

/***** Labels & Links *****/
QLabel { color: #eef2f8; }
QLabel { link-color: #4aa8ff; }

/***** Buttons *****/
QPushButton {
  background: #242c3e; color: #eef2f8; border: 1px solid rgba(255,255,255,0.14);
  border-radius: 10px; padding: 8px 14px; font-weight: 600;
}
QPushButton:hover   { background: #293348; border-color: rgba(255,255,255,0.18); }
QPushButton:pressed { background: #21293a; border-color: rgba(255,255,255,0.16); }
QPushButton:disabled{ color: #99a5b8; background: #1b2231; border-color: rgba(255,255,255,0.08); }
QPushButton:default { border: 1px solid #4aa8ff; }
QPushButton:flat    { background: transparent; border: none; }
QPushButton:flat:hover { background: rgba(255,255,255,0.06); }

/***** CommandLinkButton *****/
QCommandLinkButton { background: #242c3e; color: #eef2f8; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; padding: 10px 14px; }
QCommandLinkButton:hover { background: #293348; }

/***** Inputs *****/
QLineEdit, QTextEdit, QPlainTextEdit {
  background: #1a2130; color: #eef2f8; border: 1px solid rgba(255,255,255,0.14);
  border-radius: 10px; padding: 6px 10px; selection-background-color: rgba(74,168,255,0.25);
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border-color: #4aa8ff; }
QLineEdit[readOnly="true"] { background: #192235; border-color: rgba(255,255,255,0.12); }
QLineEdit::clear-button { subcontrol-origin: padding; width: 16px; height: 16px; }

/***** SpinBoxes & Date/Time *****/
QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit {
  background: #1a2130; color: #eef2f8; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; padding: 6px 10px;
}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { width: 18px; border: none; background: transparent; }
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover { background: #202a3c; border-radius: 6px; }
QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow { width: 10px; height: 10px; }

/***** ComboBox *****/
QComboBox { background: #1d2435; color: #eef2f8; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; padding: 6px 30px 6px 10px; }
QComboBox:hover { border-color: rgba(255,255,255,0.18); }
QComboBox:focus  { border-color: #4aa8ff; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox::down-arrow { width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: #192030; color: #eef2f8; border: 1px solid rgba(255,255,255,0.14); selection-background-color: rgba(74,168,255,0.18); }

/***** Lists / Trees / Tables *****/
QListView, QListWidget, QTreeView, QTableView, QTreeWidget, QTableWidget {
  background: #192030; color: #eef2f8; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px;
}
QAbstractItemView { selection-background-color: rgba(74,168,255,0.18); selection-color: #eef2f8; alternate-background-color: #1d2739; }
QHeaderView::section { background: #20283a; color: #eef2f8; border: 1px solid rgba(255,255,255,0.14); padding: 6px 10px; }
QHeaderView::section:hover  { background: #243147; }
QHeaderView::section:pressed{ background: #202c40; }
QHeaderView::up-arrow, QHeaderView::down-arrow { width: 10px; height: 10px; margin: 0 6px; }
QTableCornerButton::section { background: #20283a; border: 1px solid rgba(255,255,255,0.14); }

/***** Tabs *****/
QTabWidget::pane { border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; background: #192030; padding: 6px; }
QTabWidget::tab-bar { alignment: left; }
QTabWidget::left-corner, QTabWidget::right-corner { background: transparent; margin: 0 6px; }
QTabBar::tab { background: transparent; border: none; color: #cfd7e2; padding: 8px 12px; margin: 0 6px; }
QTabBar::tab:selected { color: #fff; border-bottom: 2px solid #4aa8ff; }
QTabBar::tab:hover { color: #eef4ff; }
QTabBar::scroller { width: 24px; }
QTabBar QToolButton { background: #242c3e; border: 1px solid rgba(255,255,255,0.14); border-radius: 8px; padding: 4px 6px; }
QTabBar QToolButton:hover { background: #293348; }
QTabBar::close-button { image: none; background: #242c3e; border: 1px solid rgba(255,255,255,0.14); width: 14px; height: 14px; border-radius: 7px; margin-left: 6px; }

/***** Scrollbars *****/
QScrollBar:vertical   { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.16); border-radius: 6px; min-height: 24px; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: rgba(255,255,255,0.16); border-radius: 6px; min-width: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { height: 0px; width: 0px; }
QAbstractScrollArea::corner { background: #1e2533; border-left: 1px solid rgba(255,255,255,0.10); border-top: 1px solid rgba(255,255,255,0.10); }

/***** Sliders *****/
QSlider::groove:horizontal { height: 6px; background: #20283a; border-radius: 3px; }
QSlider::handle:horizontal { width: 18px; height: 18px; margin: -6px 0; border-radius: 9px; background: #4aa8ff; border: 1px solid rgba(255,255,255,0.20); }
QSlider::groove:vertical { width: 6px; background: #20283a; border-radius: 3px; }
QSlider::handle:vertical { width: 18px; height: 18px; margin: 0 -6px; border-radius: 9px; background: #4aa8ff; border: 1px solid rgba(255,255,255,0.20); }
QSlider::sub-page:horizontal, QSlider::add-page:vertical { background: #4aa8ff; border-radius: 3px; }
QSlider::handle:disabled { background: rgba(200,200,200,0.25); border: 1px solid rgba(255,255,255,0.10); }
QSlider::groove:disabled { background: #232b3a; }

/***** Menus & MenuBar *****/
QMenu     { background: #192030; color: #eef2f8; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; }
QMenu::item { padding: 8px 14px; }
QMenu::item:selected { background: #222b3b; }
QMenu::separator{ height: 1px; background: rgba(255,255,255,0.14); margin: 6px 8px; }
QMenu::indicator { width: 16px; height: 16px; border: 1px solid rgba(255,255,255,0.18); background: #1a2130; border-radius: 4px; }
QMenu::indicator:checked { background: #4aa8ff; border-color: #4aa8ff; }
QMenuBar  { background: #1e2533; color: #eef2f8; border-bottom: 1px solid rgba(255,255,255,0.10); }
QMenuBar::item { background: transparent; padding: 8px 12px; margin: 0 4px; border-radius: 8px; }
QMenuBar::item:selected { background: #222b3b; }

/***** Toolbars & DockWidgets *****/
QToolBar  { background: #1e2533; border: 1px solid rgba(255,255,255,0.10); padding: 6px; }
QToolBar::separator { background: rgba(255,255,255,0.14); width: 1px; margin: 6px; }
QToolBar::handle:horizontal{ width: 6px; }
QToolBar::handle:vertical  { height: 6px; }
QToolButton { background: #242c3e; color:#eef2f8; border:1px solid rgba(255,255,255,0.14); border-radius: 8px; padding: 6px 10px; }
QToolButton:hover { background: #293348; }
QDockWidget { border: 1px solid rgba(255,255,255,0.14); background: #1e2533; }
QDockWidget::title { text-align:left; padding: 6px 10px; background:#20283a; }
QDockWidget::close-button, QDockWidget::float-button { border:1px solid rgba(255,255,255,0.14); background:#242c3e; width:16px; height:16px; border-radius:4px; }

/***** Tooltips & Progress *****/
QToolTip { background: #1e2533; color:#eef2f8; border:1px solid rgba(255,255,255,0.18); padding: 8px 10px; border-radius: 8px; }
QProgressBar { background: #182034; color:#dbe2ec; border:1px solid rgba(255,255,255,0.14); border-radius:10px; text-align:center; }
QProgressBar::chunk { background: #4aa8ff; border-radius: 8px; }
QProgressBar[orientation="Vertical"] { background: #182034; }
QProgressBar[orientation="Vertical"]::chunk { background: #4aa8ff; margin: 2px; }

/***** StatusBar *****/
QStatusBar { color:#cfd7e2; background: #1e2533; border-top: 1px solid rgba(255,255,255,0.10); }
QStatusBar::item { border: none; }

/***** Dialogs & Areas *****/
QDialog, QMessageBox, QProgressDialog, QColorDialog, QFontDialog { background: #1e2533; }
QFileDialog QTreeView, QFileDialog QListView { background:#192030; border:1px solid rgba(255,255,255,0.14); border-radius:8px; }
QScrollArea { border: 1px solid rgba(255,255,255,0.10); border-radius: 10px; background: #1e2533; }
QMdiArea { background: #161a20; }
QMdiSubWindow { background: #1e2533; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; }
QMdiSubWindow::title { background: #20283a; color: #eef2f8; padding: 4px 8px; }
QStackedWidget { background: #1e2533; }

/***** Misc *****/
QCalendarWidget { background: #1e2533; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; }
QCalendarWidget QWidget#qt_calendar_navigationbar { background:#20283a; }
QDial { background: transparent; }
QLCDNumber { color: #4aa8ff; background: #192030; border: 1px solid rgba(255,255,255,0.14); border-radius: 8px; }
QGraphicsView { background: #161a20; border: 1px solid rgba(255,255,255,0.10); border-radius: 8px; }
QTextBrowser { background: #1e2533; color: #eef2f8; border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; }
```

With these guidelines, skeleton, and the comprehensive example above, you can craft a professional, fully covered Qt theme for PyCompiler Pro++ that styles common and rarely seen widgets, integrated subcontrols, and all major interaction states.
