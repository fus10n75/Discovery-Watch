"""Shared visual language for the main interface and discovery popups."""

from tkinter import ttk


THEME_VERSION = '1.0'
THEME = {
    'background':'#0b0f12',
    'surface':'#101418',
    'panel':'#1a2026',
    'panel_alt':'#202830',
    'border':'#303a44',
    'orange':'#ff8c1a',
    'orange_hover':'#ffad55',
    'cyan':'#75d7f0',
    'text':'#f4f6f8',
    'muted':'#aeb8c2',
    'subtle':'#7f8b96',
    'success':'#25a244',
    'warning':'#d49a20',
    'review':'#ffd166',
    'danger':'#c53b3b',
    'selection_text':'#101418',
    'trough':'#29323a',
}

THEMED_STYLES = (
    'TFrame','Header.TFrame','Card.TFrame','TLabel','Header.TLabel','Card.TLabel',
    'Title.TLabel','Section.TLabel',
    'CardTitle.TLabel','CardValue.TLabel','Status.TLabel','System.TLabel',
    'TButton','Accent.TButton','Danger.TButton','TCheckbutton','TRadiobutton',
    'TEntry','TCombobox','TSpinbox','TLabelframe','TLabelframe.Label',
    'Card.TLabelframe','Card.TLabelframe.Label','TNotebook','TNotebook.Tab',
    'Treeview','Treeview.Heading','TScrollbar','TPanedwindow','TSeparator',
)


def apply_app_theme(root,style=None):
    """Apply the popup-inspired graphite theme using portable ttk options."""
    style=style or ttk.Style(root)
    try:
        if 'clam' in style.theme_names():
            style.theme_use('clam')
    except Exception:
        pass
    c=THEME
    root.configure(background=c['background'])
    for pattern,value in (
        ('*Text.background',c['surface']),('*Text.foreground',c['text']),
        ('*Text.insertBackground',c['text']),('*Text.selectBackground',c['orange']),
        ('*Text.selectForeground',c['selection_text']),('*Text.highlightBackground',c['border']),
        ('*Text.highlightColor',c['cyan']),('*Canvas.background',c['background']),
        ('*Listbox.background',c['surface']),('*Listbox.foreground',c['text']),
        ('*Listbox.selectBackground',c['orange']),('*Listbox.selectForeground',c['selection_text'])):
        root.option_add(pattern,value)

    style.configure('.',background=c['background'],foreground=c['text'],
                    bordercolor=c['border'],darkcolor=c['border'],lightcolor=c['border'],
                    troughcolor=c['trough'],focuscolor=c['orange'])
    style.configure('TFrame',background=c['background'])
    style.configure('Header.TFrame',background=c['surface'])
    style.configure('Card.TFrame',background=c['surface'])
    style.configure('TLabel',background=c['background'],foreground=c['text'])
    style.configure('Header.TLabel',background=c['surface'],foreground=c['muted'])
    style.configure('Card.TLabel',background=c['surface'],foreground=c['text'])
    style.configure('Title.TLabel',background=c['surface'],foreground=c['orange'],
                    font=('TkDefaultFont',16,'bold'))
    style.configure('Section.TLabel',background=c['background'],foreground=c['cyan'],
                    font=('TkDefaultFont',11,'bold'))
    style.configure('CardTitle.TLabel',background=c['surface'],foreground=c['orange'],font=('TkDefaultFont',9,'bold'))
    style.configure('CardValue.TLabel',background=c['surface'],foreground=c['text'],font=('TkDefaultFont',13,'bold'))
    style.configure('Status.TLabel',foreground=c['muted'])
    style.configure('System.TLabel',foreground=c['cyan'],font=('TkDefaultFont',10,'bold'))

    style.configure('TButton',background=c['panel_alt'],foreground=c['text'],
                    bordercolor=c['border'],padding=(10,6),relief='flat')
    style.map('TButton',background=[('active',c['border']),('pressed',c['surface'])],
              foreground=[('disabled',c['subtle'])])
    style.configure('Accent.TButton',background=c['orange'],foreground=c['selection_text'],
                    font=('TkDefaultFont',9,'bold'),bordercolor=c['orange'])
    style.map('Accent.TButton',background=[('active',c['orange_hover']),('pressed',c['orange'])])
    style.configure('Danger.TButton',background=c['danger'],foreground=c['text'],bordercolor=c['danger'])
    style.map('Danger.TButton',background=[('active','#df5757'),('pressed','#a92f2f')])

    for name in ('TCheckbutton','TRadiobutton'):
        style.configure(name,background=c['background'],foreground=c['text'],padding=3)
        style.map(name,background=[('active',c['background'])],foreground=[('disabled',c['subtle'])])
    for name in ('TEntry','TCombobox','TSpinbox'):
        style.configure(name,fieldbackground=c['surface'],background=c['panel_alt'],
                        foreground=c['text'],insertcolor=c['text'],bordercolor=c['border'],
                        arrowcolor=c['cyan'],padding=5)
        style.map(name,fieldbackground=[('readonly',c['surface']),('disabled',c['panel'])],
                  foreground=[('disabled',c['subtle'])],bordercolor=[('focus',c['orange'])])

    style.configure('TLabelframe',background=c['surface'],bordercolor=c['border'],
                    relief='solid',borderwidth=1)
    style.configure('TLabelframe.Label',background=c['background'],foreground=c['orange'],
                    font=('TkDefaultFont',9,'bold'))
    style.configure('Card.TLabelframe',background=c['surface'],bordercolor=c['border'])
    style.configure('Card.TLabelframe.Label',background=c['background'],foreground=c['orange'],
                    font=('TkDefaultFont',9,'bold'))

    style.configure('TNotebook',background=c['background'],borderwidth=0,tabmargins=(0,4,0,0))
    style.configure('TNotebook.Tab',background=c['surface'],foreground=c['muted'],
                    padding=(16,8),borderwidth=0)
    style.map('TNotebook.Tab',background=[('selected',c['panel_alt']),('active',c['panel'])],
              foreground=[('selected',c['orange']),('active',c['text'])])

    style.configure('Treeview',background=c['surface'],fieldbackground=c['surface'],
                    foreground=c['text'],bordercolor=c['border'],rowheight=28,relief='flat')
    style.map('Treeview',background=[('selected',c['orange'])],
              foreground=[('selected',c['selection_text'])])
    style.configure('Treeview.Heading',background=c['panel_alt'],foreground=c['cyan'],
                    bordercolor=c['border'],font=('TkDefaultFont',9,'bold'),padding=(7,6),relief='flat')
    style.map('Treeview.Heading',background=[('active',c['border'])],foreground=[('active',c['text'])])
    style.configure('TScrollbar',background=c['panel_alt'],troughcolor=c['surface'],
                    bordercolor=c['background'],arrowcolor=c['cyan'])
    style.map('TScrollbar',background=[('active',c['border'])])
    style.configure('TPanedwindow',background=c['background'],sashwidth=8)
    style.configure('TSeparator',background=c['border'])
    return style


def style_toplevel(window):
    """Give user-requested child windows the same dark base surface."""
    window.configure(background=THEME['background'])
    return window
