"""Paleta visual compartilhada do Dublaskizon."""
from __future__ import annotations

from typing import Any


# Todos os papéis de botão têm quatro atributos Tk. Assim, botões criados por
# módulos diferentes continuam com o mesmo contraste ao alternar o tema.
BUTTON_PALETTES: dict[str, dict[str, dict[str, str]]] = {
    "claro": {
        "primary": {"bg": "#2563EB", "activebackground": "#1D4ED8", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "secondary": {"bg": "#475569", "activebackground": "#334155", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "neutral": {"bg": "#64748B", "activebackground": "#475569", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "success": {"bg": "#15803D", "activebackground": "#166534", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "warning": {"bg": "#B45309", "activebackground": "#92400E", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "danger": {"bg": "#B91C1C", "activebackground": "#991B1B", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "accent": {"bg": "#7C3AED", "activebackground": "#6D28D9", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "teal": {"bg": "#0F766E", "activebackground": "#115E59", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "highlight": {"bg": "#D97706", "activebackground": "#B45309", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "tab_active": {"bg": "#1D4ED8", "activebackground": "#1E40AF", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "tab_inactive": {"bg": "#64748B", "activebackground": "#475569", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "tab_primary_active": {"bg": "#2563EB", "activebackground": "#1D4ED8", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "tab_primary_inactive": {"bg": "#DBEAFE", "activebackground": "#BFDBFE", "fg": "#1E3A8A", "activeforeground": "#1E3A8A"},
        "tab_accent_active": {"bg": "#2563EB", "activebackground": "#1D4ED8", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "tab_accent_inactive": {"bg": "#DBEAFE", "activebackground": "#BFDBFE", "fg": "#1E3A8A", "activeforeground": "#1E3A8A"},
        "tab_warning_active": {"bg": "#2563EB", "activebackground": "#1D4ED8", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "tab_warning_inactive": {"bg": "#DBEAFE", "activebackground": "#BFDBFE", "fg": "#1E3A8A", "activeforeground": "#1E3A8A"},
        "tab_orange_active": {"bg": "#2563EB", "activebackground": "#1D4ED8", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "tab_orange_inactive": {"bg": "#DBEAFE", "activebackground": "#BFDBFE", "fg": "#1E3A8A", "activeforeground": "#1E3A8A"},
        "tab_teal_active": {"bg": "#2563EB", "activebackground": "#1D4ED8", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "tab_teal_inactive": {"bg": "#DBEAFE", "activebackground": "#BFDBFE", "fg": "#1E3A8A", "activeforeground": "#1E3A8A"},
    },
    "medio": {
        "primary": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "secondary": {"bg": "#64748B", "activebackground": "#94A3B8", "fg": "#FFFFFF", "activeforeground": "#0F172A"},
        "neutral": {"bg": "#718096", "activebackground": "#94A3B8", "fg": "#FFFFFF", "activeforeground": "#0F172A"},
        "success": {"bg": "#4ADE80", "activebackground": "#22C55E", "fg": "#052E16", "activeforeground": "#052E16"},
        "warning": {"bg": "#FBBF24", "activebackground": "#F59E0B", "fg": "#451A03", "activeforeground": "#451A03"},
        "danger": {"bg": "#F87171", "activebackground": "#EF4444", "fg": "#450A0A", "activeforeground": "#450A0A"},
        "accent": {"bg": "#A78BFA", "activebackground": "#8B5CF6", "fg": "#1E1B4B", "activeforeground": "#1E1B4B"},
        "teal": {"bg": "#2DD4BF", "activebackground": "#14B8A6", "fg": "#042F2E", "activeforeground": "#042F2E"},
        "highlight": {"bg": "#F59E0B", "activebackground": "#D97706", "fg": "#451A03", "activeforeground": "#451A03"},
        "tab_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_inactive": {"bg": "#718096", "activebackground": "#94A3B8", "fg": "#FFFFFF", "activeforeground": "#0F172A"},
        "tab_primary_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_primary_inactive": {"bg": "#475569", "activebackground": "#64748B", "fg": "#F8FAFC", "activeforeground": "#F8FAFC"},
        "tab_accent_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_accent_inactive": {"bg": "#475569", "activebackground": "#64748B", "fg": "#F8FAFC", "activeforeground": "#F8FAFC"},
        "tab_warning_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_warning_inactive": {"bg": "#475569", "activebackground": "#64748B", "fg": "#F8FAFC", "activeforeground": "#F8FAFC"},
        "tab_orange_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_orange_inactive": {"bg": "#475569", "activebackground": "#64748B", "fg": "#F8FAFC", "activeforeground": "#F8FAFC"},
        "tab_teal_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_teal_inactive": {"bg": "#475569", "activebackground": "#64748B", "fg": "#F8FAFC", "activeforeground": "#F8FAFC"},
    },
    "escuro": {
        "primary": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "secondary": {"bg": "#94A3B8", "activebackground": "#64748B", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "neutral": {"bg": "#64748B", "activebackground": "#475569", "fg": "#FFFFFF", "activeforeground": "#FFFFFF"},
        "success": {"bg": "#4ADE80", "activebackground": "#22C55E", "fg": "#052E16", "activeforeground": "#052E16"},
        "warning": {"bg": "#FBBF24", "activebackground": "#F59E0B", "fg": "#451A03", "activeforeground": "#451A03"},
        "danger": {"bg": "#F87171", "activebackground": "#EF4444", "fg": "#450A0A", "activeforeground": "#450A0A"},
        "accent": {"bg": "#A78BFA", "activebackground": "#8B5CF6", "fg": "#1E1B4B", "activeforeground": "#1E1B4B"},
        "teal": {"bg": "#2DD4BF", "activebackground": "#14B8A6", "fg": "#042F2E", "activeforeground": "#042F2E"},
        "highlight": {"bg": "#F59E0B", "activebackground": "#D97706", "fg": "#451A03", "activeforeground": "#451A03"},
        "tab_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_inactive": {"bg": "#52627A", "activebackground": "#718096", "fg": "#F8FAFC", "activeforeground": "#0F172A"},
        "tab_primary_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_primary_inactive": {"bg": "#35445A", "activebackground": "#52627A", "fg": "#F8FAFC", "activeforeground": "#F8FAFC"},
        "tab_accent_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_accent_inactive": {"bg": "#35445A", "activebackground": "#52627A", "fg": "#F8FAFC", "activeforeground": "#F8FAFC"},
        "tab_warning_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_warning_inactive": {"bg": "#35445A", "activebackground": "#52627A", "fg": "#F8FAFC", "activeforeground": "#F8FAFC"},
        "tab_orange_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_orange_inactive": {"bg": "#35445A", "activebackground": "#52627A", "fg": "#F8FAFC", "activeforeground": "#F8FAFC"},
        "tab_teal_active": {"bg": "#60A5FA", "activebackground": "#3B82F6", "fg": "#0F172A", "activeforeground": "#0F172A"},
        "tab_teal_inactive": {"bg": "#35445A", "activebackground": "#52627A", "fg": "#F8FAFC", "activeforeground": "#F8FAFC"},
    },
}

SURFACE_COLORS: dict[str, dict[str, str]] = {
    "claro": {
        "progress_track": "#DBEAFE", "progress_clone": "#2563EB", "progress_dub": "#7C3AED",
        "portuguese": "#E8F5E9", "other_translation": "#F0FDFA", "original": "#F2F2F2", "transcribed": "#EEF6F5", "history": "#F8FAFC",
    },
    "medio": {
        "progress_track": "#526174", "progress_clone": "#60A5FA", "progress_dub": "#A78BFA",
        "portuguese": "#304F3A", "other_translation": "#2C4B4D", "original": "#515A67", "transcribed": "#405A5A", "history": "#44515E",
    },
    "escuro": {
        "progress_track": "#35445A", "progress_clone": "#60A5FA", "progress_dub": "#A78BFA",
        "portuguese": "#183321", "other_translation": "#17383A", "original": "#3A4555", "transcribed": "#2A4444", "history": "#2D3A4B",
    },
}

LEGACY_BUTTON_ROLES: dict[str, str] = {
    "#2563EB": "primary", "#93C5FD": "tab_inactive", "#C4B5FD": "tab_inactive", "#8B5CF6": "accent",
    "#7C3AED": "accent", "#F97316": "warning", "#FDBA74": "tab_inactive", "#14B8A6": "teal",
    "#5EEAD4": "tab_inactive", "#F59E0B": "warning", "#FCD34D": "tab_inactive", "#0F766E": "teal",
    "#16A34A": "success", "#DC2626": "danger", "#C00000": "danger", "#D97706": "warning",
    "#64748B": "neutral", "#475569": "secondary", "#6B7280": "neutral", "#CBD5E1": "secondary",
    "#334155": "secondary", "#F2C94C": "highlight", "#2F75B5": "primary", "#9B7BC5": "accent",
    "#3A7D44": "success", "#EA580C": "warning",
}


def resolve_theme_mode(theme: dict[str, Any] | None) -> str:
    theme = theme or {}
    explicit = str(theme.get("mode", "")).lower()
    if explicit in BUTTON_PALETTES:
        return explicit
    root = str(theme.get("root", "")).upper()
    if root == "#F5F6FA":
        return "claro"
    if root == "#334155":
        return "medio"
    return "escuro"


def button_palette(theme: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    theme = theme or {}
    supplied = theme.get("buttons")
    return supplied if isinstance(supplied, dict) else BUTTON_PALETTES[resolve_theme_mode(theme)]


def button_style(theme: dict[str, Any] | None, role: str = "neutral") -> dict[str, str]:
    palette = button_palette(theme)
    return dict(palette.get(role, palette.get("neutral", BUTTON_PALETTES["claro"]["neutral"])))


def surface_color(theme: dict[str, Any] | None, role: str, fallback: str) -> str:
    supplied = (theme or {}).get(role)
    if isinstance(supplied, str):
        return supplied
    return SURFACE_COLORS.get(resolve_theme_mode(theme), SURFACE_COLORS["claro"]).get(role, fallback)


def configure_ttk_button_styles(style: Any, theme: dict[str, Any] | None) -> None:
    """Configura estilos ttk coloridos para ambientes que ainda usem ttk.Button."""
    for name, role in (("TButton", "secondary"), ("Secondary.TButton", "secondary"), ("Primary.TButton", "primary"), ("Success.TButton", "success"), ("Warning.TButton", "warning"), ("Danger.TButton", "danger"), ("Accent.TButton", "accent"), ("Teal.TButton", "teal")):
        colors = button_style(theme, role)
        style.configure(name, background=colors["bg"], foreground=colors["fg"], borderwidth=0, relief="flat", padding=(10, 6))
        style.map(name, background=[("active", colors["activebackground"]), ("pressed", colors["activebackground"]), ("disabled", (theme or {}).get("surface", "#FFFFFF"))], foreground=[("active", colors["activeforeground"]), ("pressed", colors["activeforeground"]), ("disabled", (theme or {}).get("muted", "#64748B"))])


def apply_button_style(widget: Any, theme: dict[str, Any] | None, role: str | None = None) -> Any:
    """Aplica uma cor temática a um botão Tk e memoriza seu papel semântico."""
    if role is None:
        role = getattr(widget, "_dublaskizon_button_role", None)
    if role is None:
        try:
            role = LEGACY_BUTTON_ROLES.get(str(widget.cget("bg")), "neutral")
        except Exception:
            role = "neutral"
    setattr(widget, "_dublaskizon_button_role", role)
    widget.configure(**button_style(theme, role))
    return widget


def apply_button_style_to_tree(widget: Any, theme: dict[str, Any] | None) -> None:
    """Atualiza todos os botões Tk descendentes do widget informado."""
    try:
        if widget.winfo_class() == "Button":
            apply_button_style(widget, theme)
    except Exception:
        pass
    try:
        for child in widget.winfo_children():
            apply_button_style_to_tree(child, theme)
    except Exception:
        pass
