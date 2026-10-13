# -*- coding: utf-8 -*-
"""Standalone Elite Dangerous journal discovery monitor. Python 3.9+, standard library only."""
import csv
import base64
import html
import json
import hashlib
import os
import platform
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections import Counter, deque
from contextlib import closing
from datetime import datetime, timezone, timedelta
import sqlite3
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from discovery_watch_core.config import *


from discovery_watch_core.detection import (
    alert_level, classify, detect_anomalies, discovery_facts, finding_type,
    is_planetary_mining_signal, stratum_findings, surface_signal_findings,
    surface_signal_observations,
)
from discovery_watch_core.exploration_criteria import EXPLORATION_CRITERIA
from discovery_watch_core.intelligence import (
    SETTINGS_BEHAVIOUR, finding_policy, policy_explanation,
    popup_delivery_allowed, validate_policy_registry,
)




from discovery_watch_core.preferences import *


def bundled_resource(*parts):
    """Return a source-tree or PyInstaller-bundled application resource."""
    base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def application_icon_paths():
    """Return the cross-platform window icon and Windows executable icon."""
    root=('assets','icons')
    return (bundled_resource(*root,'discovery-watch.png'),
            bundled_resource(*root,'discovery-watch.ico'))


def ensure_linux_ui_scaling(root,environment=None):
    """Prevent bundled Tk builds from rendering undersized text on Linux."""
    if platform.system()!='Linux': return None
    environment=os.environ if environment is None else environment
    try: current=float(root.tk.call('tk','scaling'))
    except (tk.TclError,TypeError,ValueError): current=1.0
    requested=environment.get('DISCOVERY_WATCH_UI_SCALE','').strip()
    try: target=float(requested) if requested else max(current,96.0/72.0)
    except ValueError: target=max(current,96.0/72.0)
    target=max(0.75,min(4.0,target))
    try: root.tk.call('tk','scaling',target)
    except tk.TclError: return current
    return target














































def windows_work_area_to_tk(area,tk_scaling):
    """Convert Win32 physical monitor coordinates into Tk logical coordinates."""
    try: scale=float(tk_scaling)/(96.0/72.0)
    except (TypeError,ValueError,ZeroDivisionError): scale=1.0
    if not 0.5<=scale<=4.0: scale=1.0
    return tuple(int(round(value/scale)) for value in area)


_WINDOWS_MONITOR_INFO_TYPE=None


def _windows_monitor_info_type():
    """Return one shared ctypes type so cached Win32 signatures stay valid."""
    global _WINDOWS_MONITOR_INFO_TYPE
    if _WINDOWS_MONITOR_INFO_TYPE is None:
        import ctypes
        from ctypes import wintypes
        class MONITORINFO(ctypes.Structure):
            _fields_=(('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),
                      ('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD))
        _WINDOWS_MONITOR_INFO_TYPE=MONITORINFO
    return _WINDOWS_MONITOR_INFO_TYPE


def popup_position(area,width,height,system_name=None,choice=None):
    """Return a safely clamped popup position in Tk screen coordinates."""
    left,top,right,bottom=area
    available_width=max(1,right-left)
    available_height=max(1,bottom-top)
    width=max(1,min(int(width),available_width))
    height=max(1,min(int(height),available_height))
    system_name=platform.system() if system_name is None else system_name
    if choice is None and system_name=='Windows':
        # Centring leaves generous room on both sides when Windows and Tk report
        # slightly different logical coordinates under display scaling.
        x=left+(available_width-width)//2
    elif choice is None:
        x=right-width-POPUP_RIGHT_MARGIN
    else:
        horizontal='left' if 'left' in choice.casefold() else 'right'
        x=left+POPUP_EDGE_MARGIN if horizontal=='left' else right-width-POPUP_EDGE_MARGIN
    if choice and choice.casefold()=='centre':
        x=left+(available_width-width)//2; y=top+(available_height-height)//2
    elif choice and 'bottom' in choice.casefold():
        y=bottom-height-POPUP_EDGE_MARGIN
    else:
        y=top+POPUP_TOP_MARGIN
    maximum_x=max(left,right-width-POPUP_EDGE_MARGIN)
    maximum_y=max(top,bottom-height-POPUP_EDGE_MARGIN)
    return (min(max(left+POPUP_EDGE_MARGIN,x),maximum_x),
            min(max(top+POPUP_EDGE_MARGIN,y),maximum_y))


def popup_work_area(widget,choice):
    """Return (left, top, right, bottom) for the selected monitor's usable area."""
    if platform.system()=='Windows':
        # Tk already reports the primary display in the same logical coordinate
        # system used by Toplevel.geometry. This avoids mixed-DPI Win32 values.
        if choice=='primary':
            return 0,0,widget.winfo_screenwidth(),widget.winfo_screenheight()
        try:
            import ctypes
            from ctypes import wintypes
            MONITORINFO=_windows_monitor_info_type()
            user32=ctypes.windll.user32
            user32.MonitorFromPoint.argtypes=(wintypes.POINT,wintypes.DWORD)
            user32.MonitorFromPoint.restype=ctypes.c_void_p
            user32.MonitorFromWindow.argtypes=(wintypes.HWND,wintypes.DWORD)
            user32.MonitorFromWindow.restype=ctypes.c_void_p
            user32.GetMonitorInfoW.argtypes=(ctypes.c_void_p,ctypes.POINTER(MONITORINFO))
            user32.GetMonitorInfoW.restype=wintypes.BOOL
            user32.GetCursorPos.argtypes=(ctypes.POINTER(wintypes.POINT),)
            user32.GetCursorPos.restype=wintypes.BOOL
            if choice=='application':
                monitor=user32.MonitorFromWindow(widget.winfo_id(),2)
            elif choice=='pointer':
                point=wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(point))
                monitor=user32.MonitorFromPoint(point,2)
            else:
                # An off-screen point with MONITOR_DEFAULTTOPRIMARY selects the
                # Windows primary display regardless of the virtual layout.
                monitor=user32.MonitorFromPoint(wintypes.POINT(-100000,-100000),1)
            info=MONITORINFO(); info.cbSize=ctypes.sizeof(info)
            if monitor and user32.GetMonitorInfoW(monitor,ctypes.byref(info)):
                area=info.rcWork
                native=(area.left,area.top,area.right,area.bottom)
                try: tk_scaling=widget.tk.call('tk','scaling')
                except tk.TclError: tk_scaling=96.0/72.0
                return windows_work_area_to_tk(native,tk_scaling)
        except (AttributeError,OSError,ValueError):
            pass
    if choice=='application':
        left=widget.winfo_rootx(); top=widget.winfo_rooty()
        return left,top,left+widget.winfo_screenwidth(),top+widget.winfo_screenheight()
    return 0,0,widget.winfo_screenwidth(),widget.winfo_screenheight()


def notification_behaviour(policy,popup):
    if policy=='ignore': return 'Ignore'
    if policy=='record': return 'Catalogue only'
    if policy=='alert' and popup: return 'Alert + popup'
    if policy=='alert': return 'Alert silently'
    return str(policy)


def _ensure_notification_delivery_table(db):
    db.execute('''CREATE TABLE IF NOT EXISTS notification_deliveries (
        id INTEGER PRIMARY KEY, attempted_at TEXT NOT NULL, operating_system TEXT NOT NULL,
        method TEXT NOT NULL, result TEXT NOT NULL, source TEXT NOT NULL,
        finding_count INTEGER NOT NULL, system_name TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '')''')


def record_notification_delivery(method,result,findings,source='Live journal',detail='',db_path=DB_PATH):
    """Audit notification delivery without copying raw journal event data."""
    rows=list(findings or [])
    system=str(rows[0][1] if rows and len(rows[0])>1 else '')
    summary='; '.join(str(row[0]) for row in rows[:3])
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(str(db_path))) as db, db:
        _ensure_notification_delivery_table(db)
        db.execute('''INSERT INTO notification_deliveries
            (attempted_at,operating_system,method,result,source,finding_count,system_name,summary,detail)
            VALUES(?,?,?,?,?,?,?,?,?)''',
            (datetime.now(timezone.utc).isoformat(timespec='seconds'),platform.system(),str(method),
             str(result),str(source),len(rows),system,summary[:500],str(detail)[:500]))
        db.execute('''DELETE FROM notification_deliveries WHERE id NOT IN
            (SELECT id FROM notification_deliveries ORDER BY id DESC LIMIT 500)''')


def notification_delivery_summary(db_path=DB_PATH,connection=None):
    """Return compact launch history for diagnostics and support."""
    owned=connection is None
    db=sqlite3.connect(str(db_path)) if owned else connection
    try:
        _ensure_notification_delivery_table(db)
        total=db.execute('SELECT COUNT(*) FROM notification_deliveries').fetchone()[0]
        launched=db.execute("SELECT COUNT(*) FROM notification_deliveries WHERE result='launched'").fetchone()[0]
        failed=db.execute("SELECT COUNT(*) FROM notification_deliveries WHERE result='failed'").fetchone()[0]
        row=db.execute('''SELECT attempted_at,operating_system,method,result,source,finding_count,
            system_name,summary,detail FROM notification_deliveries ORDER BY id DESC LIMIT 1''').fetchone()
        keys=('attempted_at','operating_system','method','result','source','finding_count',
              'system_name','summary','detail')
        return {'total':total,'launched':launched,'failed':failed,
                'last_delivery':dict(zip(keys,row)) if row else None}
    finally:
        if owned: db.close()


from discovery_watch_core.presentation import (
    discovery_history_detail_summary, journal_evidence_summary,
    native_notification_payload, popup_attention_label,
    popup_category_labels, popup_identity, popup_test_scenario, simplify_popup_content,
)
from discovery_watch_core.theme import THEME, THEME_VERSION, apply_app_theme, style_toplevel






def add_scrollable_notebook_page(notebook,label,padding=10):
    """Add a vertically scrollable notebook page and return its content frame."""
    shell=ttk.Frame(notebook)
    background=ttk.Style().lookup('TFrame','background') or '#f0f0f0'
    canvas=tk.Canvas(shell,highlightthickness=0,borderwidth=0,background=background)
    shell._settings_scroll_canvas=canvas
    canvas._settings_scroll_canvas=canvas
    scrollbar=ttk.Scrollbar(shell,orient='vertical',command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right',fill='y')
    canvas.pack(side='left',fill='both',expand=True)
    content=ttk.Frame(canvas,padding=padding)
    content._settings_scroll_canvas=canvas
    window=canvas.create_window((0,0),window=content,anchor='nw')
    content.bind('<Configure>',lambda _event:canvas.configure(scrollregion=canvas.bbox('all')))
    def resize_content(event):
        # Width follows a large/maximised window. Height remains natural so a
        # smaller laptop viewport can expose the complete page by scrolling.
        canvas.itemconfigure(window,width=event.width)
        canvas.configure(scrollregion=canvas.bbox('all'))
    canvas.bind('<Configure>',resize_content)
    notebook.add(shell,text=label)
    return content


def initial_window_geometry(screen_width,screen_height):
    """Choose a useful startup size without extending beyond a laptop display."""
    width=max(800,min(1280,int(screen_width)-80))
    height=max(520,min(860,int(screen_height)-110))
    return f'{width}x{height}'


def play_alert_sound(widget):
    """Play a native Windows alert, falling back to Tk's cross-platform bell."""
    if platform.system()=='Windows':
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            return True
        except (ImportError, RuntimeError):
            pass
    try:
        widget.bell()
        return True
    except tk.TclError:
        return False


def is_wayland_session(environ=None,system_name=None):
    """Detect Wayland without assuming a specific Linux desktop environment."""
    environ=os.environ if environ is None else environ
    system_name=platform.system() if system_name is None else system_name
    return (system_name=='Linux' and
            (str(environ.get('XDG_SESSION_TYPE','')).casefold()=='wayland' or
             bool(environ.get('WAYLAND_DISPLAY'))))


def popup_diagnostics(widget=None,monitor_choice='Main monitor',auto_close=True,timeout=15,
                      keep_above=True,sound=True,environ=None,system_name=None,
                      windows_mode='Native Windows notification'):
    """Describe the effective notification path without exposing journal contents."""
    environ=os.environ if environ is None else environ
    system_name=platform.system() if system_name is None else system_name
    wayland=is_wayland_session(environ,system_name)
    result={
        'operating_system':system_name,
        'session_type':str(environ.get('XDG_SESSION_TYPE') or ('wayland' if environ.get('WAYLAND_DISPLAY') else 'unknown')),
        'wayland':wayland,
        'notification_method':('Native Wayland notification' if wayland else
                               windows_mode if system_name=='Windows' else 'Discovery Watch custom popup'),
        'windows_notification_mode':windows_mode if system_name=='Windows' else 'Not applicable',
        'popup_monitor_setting':monitor_choice,
        'monitor_setting_effective':not wayland,
        'auto_close':bool(auto_close),'timeout_seconds':int(timeout),
        'keep_above_game':bool(keep_above),'sound_enabled':bool(sound),
        'notify_send_available':bool(shutil.which('notify-send')),
        'gdbus_available':bool(shutil.which('gdbus')),
    }
    if system_name=='Windows':
        overlay_error=windows_overlay_error_details()
        result['overlay_error_log']=overlay_error['path']
        result['overlay_last_error']=overlay_error['message']
    if widget is not None and not wayland:
        try: result['calculated_work_area']=popup_work_area(widget,POPUP_MONITOR_VALUES.get(monitor_choice,'primary'))
        except (tk.TclError,ValueError,OSError): result['calculated_work_area']='Unavailable'
    else:
        result['calculated_work_area']='Desktop controlled' if wayland else 'Requires running interface'
    return result




_WINDOWS_NOTIFY_ICON_DATA_TYPE=None
_WINDOWS_NOTIFICATION_SEQUENCE=100


def _windows_notify_icon_data_type():
    """Return the Win32 notification structure through the balloon fields."""
    global _WINDOWS_NOTIFY_ICON_DATA_TYPE
    if _WINDOWS_NOTIFY_ICON_DATA_TYPE is None:
        import ctypes
        from ctypes import wintypes
        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_=(('cbSize',wintypes.DWORD),('hWnd',wintypes.HWND),
                      ('uID',wintypes.UINT),('uFlags',wintypes.UINT),
                      ('uCallbackMessage',wintypes.UINT),('hIcon',wintypes.HICON),
                      ('szTip',wintypes.WCHAR*128),('dwState',wintypes.DWORD),
                      ('dwStateMask',wintypes.DWORD),('szInfo',wintypes.WCHAR*256),
                      ('uTimeoutOrVersion',wintypes.UINT),('szInfoTitle',wintypes.WCHAR*64),
                      ('dwInfoFlags',wintypes.DWORD))
        _WINDOWS_NOTIFY_ICON_DATA_TYPE=NOTIFYICONDATAW
    return _WINDOWS_NOTIFY_ICON_DATA_TYPE


def _send_windows_shell_notification(widget,findings,metadata=None,timeout=15,
                                     user32=None,shell32=None):
    """Display a Win32 notification-area balloon without creating a new window."""
    global _WINDOWS_NOTIFICATION_SEQUENCE
    if platform.system()!='Windows' or widget is None:
        return False
    try:
        import ctypes
        if user32 is None: user32=ctypes.windll.user32
        if shell32 is None: shell32=ctypes.windll.shell32
        hwnd=_windows_popup_handle(widget,user32)
        data_type=_windows_notify_icon_data_type()
        nid=data_type(); nid.cbSize=ctypes.sizeof(nid); nid.hWnd=hwnd
        _WINDOWS_NOTIFICATION_SEQUENCE+=1
        nid.uID=_WINDOWS_NOTIFICATION_SEQUENCE
        nid.uFlags=0x00000002 | 0x00000004  # NIF_ICON | NIF_TIP
        nid.hIcon=user32.LoadIconW(None,ctypes.c_void_p(32515))  # IDI_EXCLAMATION
        nid.szTip='Discovery Watch'
        if not shell32.Shell_NotifyIconW(0,ctypes.byref(nid)):  # NIM_ADD
            return False
        nid.uTimeoutOrVersion=4
        shell32.Shell_NotifyIconW(4,ctypes.byref(nid))  # NIM_SETVERSION
        title,body=native_notification_payload(findings,metadata)
        nid.uFlags=0x00000010  # NIF_INFO
        nid.szInfoTitle=title[:63]
        nid.szInfo=body[:255]
        nid.uTimeoutOrVersion=max(5000,min(30000,int(timeout or 15)*1000))
        nid.dwInfoFlags=2  # NIIF_WARNING
        if not shell32.Shell_NotifyIconW(1,ctypes.byref(nid)):  # NIM_MODIFY
            shell32.Shell_NotifyIconW(2,ctypes.byref(nid))
            return False
        return {'method':'Windows notification area','hwnd':int(hwnd),'uid':int(nid.uID)}
    except (AttributeError,OSError,TypeError,ValueError,tk.TclError):
        return False


def close_windows_notification(token,shell32=None):
    """Remove a temporary Discovery Watch notification-area icon."""
    if not isinstance(token,dict) or token.get('method')!='Windows notification area':
        return False
    try:
        import ctypes
        if shell32 is None: shell32=ctypes.windll.shell32
        data_type=_windows_notify_icon_data_type()
        nid=data_type(); nid.cbSize=ctypes.sizeof(nid)
        nid.hWnd=int(token['hwnd']); nid.uID=int(token['uid'])
        return bool(shell32.Shell_NotifyIconW(2,ctypes.byref(nid)))
    except (AttributeError,OSError,TypeError,ValueError):
        return False


def send_windows_notification(findings,metadata=None,timeout=15,widget=None):
    """Send a focus-safe Windows notification with PowerShell as fallback."""
    if platform.system()!='Windows':
        return False
    shell_result=_send_windows_shell_notification(widget,findings,metadata,timeout)
    if shell_result:
        return shell_result
    executable=next((shutil.which(name) for name in ('powershell.exe','powershell','pwsh.exe','pwsh')
                     if shutil.which(name)),None)
    if not executable:
        return False
    title,body=native_notification_payload(findings,metadata)
    body=body[:700]
    duration='long' if int(timeout or 0)>15 else 'short'
    xml=(f'<toast duration="{duration}"><visual><binding template="ToastGeneric">'
         f'<text>{html.escape(title)}</text><text>{html.escape(body)}</text>'
         '</binding></visual><audio silent="true"/></toast>')
    xml64=base64.b64encode(xml.encode('utf-8')).decode('ascii')
    script=(
        '$null=[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime];'
        '$null=[Windows.UI.Notifications.ToastNotification,Windows.UI.Notifications,ContentType=WindowsRuntime];'
        '$null=[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime];'
        f'$x=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("{xml64}"));'
        '$d=New-Object Windows.Data.Xml.Dom.XmlDocument;$d.LoadXml($x);'
        '$t=New-Object Windows.UI.Notifications.ToastNotification $d;'
        '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Discovery Watch").Show($t)')
    encoded=base64.b64encode(script.encode('utf-16le')).decode('ascii')
    try:
        completed=subprocess.run([executable,'-NoProfile','-NonInteractive','-WindowStyle','Hidden',
                                  '-EncodedCommand',encoded],capture_output=True,text=True,timeout=5,check=False,
                                 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return completed.returncode==0
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return False


def send_windows_overlay(widget,findings,metadata=None,timeout=15,monitor_choice='Main monitor',
                         user32=None,popen_factory=None,position='Bottom right',font_size='Normal'):
    """Launch the native overlay in an isolated process so Tk cannot affect focus."""
    if platform.system()!='Windows':
        return False
    try:
        import ctypes
        if user32 is None: user32=ctypes.windll.user32
        if popen_factory is None: popen_factory=subprocess.Popen
        owner=int(_windows_popup_handle(widget,user32))
        title,body=native_notification_payload(findings,metadata)
        payload={'title':title,'body':body[:900],
                 'timeout':max(5,min(60,int(timeout or 15))),
                 'monitor':POPUP_MONITOR_VALUES.get(monitor_choice,'primary'),
                 'position':position,'font_size':font_size,
                 'owner':owner}
        encoded=base64.urlsafe_b64encode(json.dumps(payload,ensure_ascii=True).encode('ascii')).decode('ascii')
        popen_factory(windows_overlay_command(encoded),
                      stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                      close_fds=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return True
    except (AttributeError,OSError,TypeError,ValueError,tk.TclError):
        return False


def windows_overlay_command(encoded,executable=None,script_path=None,frozen=None):
    """Launch the overlay correctly from source Python or a frozen portable app."""
    executable=str(executable or sys.executable)
    frozen=bool(getattr(sys,'frozen',False)) if frozen is None else bool(frozen)
    if frozen:
        return [executable,'--windows-overlay',str(encoded)]
    script_path=str(script_path or Path(__file__).resolve())
    return [executable,script_path,'--windows-overlay',str(encoded)]


def decode_windows_overlay_payload(encoded):
    return json.loads(base64.urlsafe_b64decode(str(encoded).encode('ascii')).decode('ascii'))


def record_windows_overlay_error(error):
    """Keep child-process overlay failures visible without opening a console."""
    try:
        APP_DIR.mkdir(parents=True,exist_ok=True)
        (APP_DIR/'windows_overlay_error.log').write_text(
            f'{type(error).__name__}: {error}\n',encoding='utf-8')
    except OSError:
        pass


def windows_overlay_error_details():
    """Return the latest isolated overlay failure for the diagnostics screen."""
    path=APP_DIR/'windows_overlay_error.log'
    if not path.is_file():
        return {'present':False,'path':str(path),'message':'No overlay startup error recorded'}
    try:
        return {'present':True,'path':str(path),
                'message':path.read_text(encoding='utf-8',errors='replace')[-1000:].strip()}
    except OSError as exc:
        return {'present':True,'path':str(path),'message':f'Could not read log: {exc}'}


def run_windows_overlay(payload):
    """Run one click-through, non-activating Win32/GDI discovery overlay."""
    if platform.system()!='Windows':
        return 1
    try:
        try: (APP_DIR/'windows_overlay_error.log').unlink(missing_ok=True)
        except OSError: pass
        import ctypes
        from ctypes import wintypes
        user32=ctypes.windll.user32; gdi32=ctypes.windll.gdi32; kernel32=ctypes.windll.kernel32
        LRESULT=ctypes.c_ssize_t
        WNDPROC=ctypes.WINFUNCTYPE(LRESULT,wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM)
        class WNDCLASSW(ctypes.Structure):
            _fields_=(('style',wintypes.UINT),('lpfnWndProc',WNDPROC),
                      ('cbClsExtra',ctypes.c_int),('cbWndExtra',ctypes.c_int),
                      ('hInstance',wintypes.HINSTANCE),('hIcon',wintypes.HICON),
                      ('hCursor',wintypes.HANDLE),('hbrBackground',wintypes.HBRUSH),
                      ('lpszMenuName',wintypes.LPCWSTR),('lpszClassName',wintypes.LPCWSTR))
        class PAINTSTRUCT(ctypes.Structure):
            _fields_=(('hdc',wintypes.HDC),('fErase',wintypes.BOOL),('rcPaint',wintypes.RECT),
                      ('fRestore',wintypes.BOOL),('fIncUpdate',wintypes.BOOL),
                      ('rgbReserved',ctypes.c_byte*32))
        user32.DefWindowProcW.restype=LRESULT
        user32.CreateWindowExW.restype=wintypes.HWND
        user32.CreateWindowExW.argtypes=(wintypes.DWORD,wintypes.LPCWSTR,wintypes.LPCWSTR,
            wintypes.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,
            wintypes.HWND,wintypes.HMENU,wintypes.HINSTANCE,ctypes.c_void_p)
        user32.BeginPaint.restype=wintypes.HDC
        user32.BeginPaint.argtypes=(wintypes.HWND,ctypes.POINTER(PAINTSTRUCT))
        user32.FillRect.restype=ctypes.c_int
        user32.FillRect.argtypes=(wintypes.HDC,ctypes.POINTER(wintypes.RECT),wintypes.HBRUSH)
        user32.DrawTextW.restype=ctypes.c_int
        user32.DrawTextW.argtypes=(wintypes.HDC,wintypes.LPCWSTR,ctypes.c_int,
                                   ctypes.POINTER(wintypes.RECT),wintypes.UINT)
        user32.EndPaint.argtypes=(wintypes.HWND,ctypes.POINTER(PAINTSTRUCT))
        user32.InvalidateRect.argtypes=(wintypes.HWND,ctypes.c_void_p,wintypes.BOOL)
        user32.UpdateWindow.argtypes=(wintypes.HWND,)
        user32.SetLayeredWindowAttributes.argtypes=(wintypes.HWND,wintypes.DWORD,
                                                   wintypes.BYTE,wintypes.DWORD)
        user32.SetWindowPos.argtypes=(wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,
                                     ctypes.c_int,ctypes.c_int,wintypes.UINT)
        user32.MonitorFromWindow.restype=ctypes.c_void_p
        user32.MonitorFromPoint.restype=ctypes.c_void_p
        gdi32.CreateSolidBrush.restype=wintypes.HBRUSH
        gdi32.CreateFontW.restype=wintypes.HANDLE
        gdi32.CreateFontW.argtypes=(ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,
                                    ctypes.c_int,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,
                                    wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,
                                    wintypes.DWORD,wintypes.LPCWSTR)
        gdi32.SelectObject.restype=wintypes.HANDLE
        gdi32.SelectObject.argtypes=(wintypes.HDC,wintypes.HANDLE)
        gdi32.SetBkMode.argtypes=(wintypes.HDC,ctypes.c_int)
        gdi32.SetTextColor.argtypes=(wintypes.HDC,wintypes.DWORD)
        gdi32.TextOutW.restype=wintypes.BOOL
        gdi32.TextOutW.argtypes=(wintypes.HDC,ctypes.c_int,ctypes.c_int,
                                 wintypes.LPCWSTR,ctypes.c_int)
        gdi32.DeleteObject.argtypes=(wintypes.HANDLE,)
        kernel32.GetModuleHandleW.restype=wintypes.HMODULE
        instance=kernel32.GetModuleHandleW(None)
        title=str(payload.get('title') or 'Discovery Watch')
        body=str(payload.get('body') or 'New discovery alert')
        timeout=max(5,min(60,int(payload.get('timeout') or 15)))
        scale=POPUP_FONT_SCALES.get(str(payload.get('font_size') or 'Normal'),1.0)
        width=int(620*scale); lines=max(1,min(8,len(body.splitlines())))
        height=max(190,min(360,135+lines*28))
        def rgb(red,green,blue): return red | (green<<8) | (blue<<16)
        @WNDPROC
        def window_proc(hwnd,message,wparam,lparam):
            if message==15:  # WM_PAINT
                paint=PAINTSTRUCT(); hdc=user32.BeginPaint(hwnd,ctypes.byref(paint))
                rect=wintypes.RECT(0,0,width,height)
                brush=gdi32.CreateSolidBrush(rgb(16,20,24)); user32.FillRect(hdc,ctypes.byref(rect),brush)
                gdi32.DeleteObject(brush)
                accent=wintypes.RECT(0,0,7,height)
                brush=gdi32.CreateSolidBrush(rgb(255,140,26)); user32.FillRect(hdc,ctypes.byref(accent),brush)
                gdi32.DeleteObject(brush); gdi32.SetBkMode(hdc,1)
                label_font=gdi32.CreateFontW(-int(15*scale),0,0,0,700,0,0,0,1,0,0,5,0,'Segoe UI')
                old=gdi32.SelectObject(hdc,label_font); gdi32.SetTextColor(hdc,rgb(255,140,26))
                gdi32.TextOutW(hdc,25,16,'DISCOVERY WATCH',15)
                heading_font=gdi32.CreateFontW(-int(23*scale),0,0,0,700,0,0,0,1,0,0,5,0,'Segoe UI')
                gdi32.SelectObject(hdc,heading_font); gdi32.SetTextColor(hdc,rgb(244,246,248))
                heading=wintypes.RECT(25,43,width-25,77)
                user32.DrawTextW(hdc,title,-1,ctypes.byref(heading),0x20|0x0800|0x8000)
                body_font=gdi32.CreateFontW(-int(18*scale),0,0,0,400,0,0,0,1,0,0,5,0,'Segoe UI')
                gdi32.SelectObject(hdc,body_font); gdi32.SetTextColor(hdc,rgb(117,215,240))
                body_rect=wintypes.RECT(25,83,width-25,height-38)
                user32.DrawTextW(hdc,body,-1,ctypes.byref(body_rect),0x10|0x0800|0x8000)
                gdi32.SelectObject(hdc,old)
                for font in (label_font,heading_font,body_font): gdi32.DeleteObject(font)
                user32.EndPaint(hwnd,ctypes.byref(paint)); return 0
            if message==275:  # WM_TIMER
                user32.DestroyWindow(hwnd); return 0
            if message==132:  # WM_NCHITTEST
                return -1  # HTTRANSPARENT
            if message==2:  # WM_DESTROY
                user32.PostQuitMessage(0); return 0
            return user32.DefWindowProcW(hwnd,message,wparam,lparam)
        class_name=f'DiscoveryWatchOverlay{os.getpid()}'
        window_class=WNDCLASSW(); window_class.lpfnWndProc=window_proc
        window_class.hInstance=instance; window_class.lpszClassName=class_name
        window_class.hCursor=user32.LoadCursorW(None,ctypes.c_void_p(32512))
        if not user32.RegisterClassW(ctypes.byref(window_class)): return 1
        monitor_mode=str(payload.get('monitor') or 'primary')
        if monitor_mode=='application' and int(payload.get('owner') or 0):
            monitor=user32.MonitorFromWindow(int(payload['owner']),2)
        elif monitor_mode=='pointer':
            point=wintypes.POINT(); user32.GetCursorPos(ctypes.byref(point))
            monitor=user32.MonitorFromPoint(point,2)
        else:
            monitor=user32.MonitorFromPoint(wintypes.POINT(-100000,-100000),1)
        info_type=_windows_monitor_info_type(); info=info_type(); info.cbSize=ctypes.sizeof(info)
        user32.GetMonitorInfoW.argtypes=(ctypes.c_void_p,ctypes.POINTER(info_type))
        if not (monitor and user32.GetMonitorInfoW(monitor,ctypes.byref(info))): return 1
        x,y=popup_position((info.rcWork.left,info.rcWork.top,info.rcWork.right,info.rcWork.bottom),
                           width,height,'Windows',str(payload.get('position') or 'Bottom right'))
        ex_style=0x00000008|0x00000020|0x00000080|0x00080000|0x08000000
        hwnd=user32.CreateWindowExW(ex_style,class_name,'Discovery Watch',0x80000000,
                                    x,y,width,height,None,None,instance,None)
        if not hwnd: return 1
        user32.SetLayeredWindowAttributes(hwnd,0,242,2)
        user32.ShowWindow(hwnd,4)  # SW_SHOWNOACTIVATE
        user32.SetWindowPos(hwnd,-1,x,y,width,height,0x0010|0x0040)
        # Force the first GDI paint after the layered window is visible. This is
        # especially important when Elite is occupying the foreground display.
        user32.InvalidateRect(hwnd,None,True)
        user32.UpdateWindow(hwnd)
        user32.SetTimer(hwnd,1,timeout*1000,None)
        message=wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message),None,0,0)>0:
            user32.TranslateMessage(ctypes.byref(message)); user32.DispatchMessageW(ctypes.byref(message))
        return 0
    except Exception as exc:
        record_windows_overlay_error(exc)
        return 1


def send_native_notification(findings,metadata=None,timeout=15):
    """Display a Wayland notification and return its server ID when available."""
    executable=shutil.which('notify-send')
    if not executable:
        return False
    title,body=native_notification_payload(findings,metadata)
    try:
        command=[executable,'--app-name=Discovery Watch','--urgency=critical',
                 f'--expire-time={max(0,int(timeout))*1000}','--print-id',title,body]
        completed=subprocess.run(command,capture_output=True,text=True,timeout=3,check=False)
        if completed.returncode==0:
            value=completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ''
            try: return int(value)
            except ValueError: return True
        # Older notify-send versions lack --print-id. The notification can still
        # be shown, although its desktop service controls final dismissal.
        subprocess.Popen([executable,'--app-name=Discovery Watch','--urgency=critical',
                          f'--expire-time={max(0,int(timeout))*1000}',title,body],
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return True
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return False


def close_native_notification(notification_id):
    """Explicitly close a freedesktop notification whose server ignored expiry."""
    if isinstance(notification_id,bool) or not isinstance(notification_id,int) or notification_id<1:
        return False
    executable=shutil.which('gdbus')
    if not executable:
        return False
    try:
        completed=subprocess.run([executable,'call','--session',
            '--dest','org.freedesktop.Notifications',
            '--object-path','/org/freedesktop/Notifications',
            '--method','org.freedesktop.Notifications.CloseNotification',
            str(notification_id)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            timeout=3,check=False)
        return completed.returncode==0
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return False


def _windows_popup_handle(widget,user32):
    hwnd=widget.winfo_id()
    wrapper=user32.GetParent(hwnd)
    return wrapper or hwnd


def _windows_popup_handles(widget,user32):
    """Return the Tk content handle and its native top-level wrapper."""
    content=widget.winfo_id()
    wrapper=user32.GetParent(content)
    return tuple(dict.fromkeys((content,wrapper or content)))


def prepare_windows_popup(widget,user32=None):
    """Apply non-activating Windows styles before the popup is first mapped."""
    if platform.system()!='Windows':
        return False
    try:
        if user32 is None:
            import ctypes
            user32=ctypes.windll.user32
        for hwnd in _windows_popup_handles(widget,user32):
            current=user32.GetWindowLongW(hwnd,-20)  # GWL_EXSTYLE
            styles=current | 0x08000000 | 0x00000080  # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            user32.SetWindowLongW(hwnd,-20,styles)
        return True
    except (AttributeError,OSError,tk.TclError):
        return False


def windows_popup_position(area,size):
    """Centre native-pixel popup dimensions inside a native monitor work area."""
    left,top,right,bottom=area
    width,height=size
    width=max(1,min(int(width),max(1,right-left)))
    height=max(1,min(int(height),max(1,bottom-top)))
    return (left+max(0,(right-left-width)//2),
            top+max(0,(bottom-top-height)//6))


def show_windows_popup(widget,monitor_choice='primary',user32=None):
    """Show and place the real Win32 wrapper without activating the process."""
    if platform.system()!='Windows':
        return False
    try:
        import ctypes
        from ctypes import wintypes
        if user32 is None:
            user32=ctypes.windll.user32
        prepare_windows_popup(widget,user32)
        hwnd=_windows_popup_handle(widget,user32)
        MONITORINFO=_windows_monitor_info_type()
        # popup_work_area may already have cached this API's ctypes signature.
        # Re-registering the same shared type is safe on Python 3.13 and avoids
        # a pointer-type mismatch between the two monitor callers.
        user32.GetMonitorInfoW.argtypes=(ctypes.c_void_p,ctypes.POINTER(MONITORINFO))
        user32.GetMonitorInfoW.restype=wintypes.BOOL
        user32.GetWindowRect.argtypes=(wintypes.HWND,ctypes.POINTER(wintypes.RECT))
        user32.GetWindowRect.restype=wintypes.BOOL
        rectangle=wintypes.RECT()
        if monitor_choice=='application':
            owner=_windows_popup_handle(widget.master,user32)
            monitor=user32.MonitorFromWindow(owner,2)
        elif monitor_choice=='pointer':
            point=wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            monitor=user32.MonitorFromPoint(point,2)
        else:
            monitor=user32.MonitorFromPoint(wintypes.POINT(-100000,-100000),1)
        info=MONITORINFO(); info.cbSize=ctypes.sizeof(info)
        if not (monitor and user32.GetMonitorInfoW(monitor,ctypes.byref(info)) and
                user32.GetWindowRect(hwnd,ctypes.byref(rectangle))):
            return False
        area=(info.rcWork.left,info.rcWork.top,info.rcWork.right,info.rcWork.bottom)
        size=(rectangle.right-rectangle.left,rectangle.bottom-rectangle.top)
        x,y=windows_popup_position(area,size)
        user32.ShowWindow(hwnd,4)  # SW_SHOWNOACTIVATE
        flags=0x0010 | 0x0040  # SWP_NOACTIVATE | SWP_SHOWWINDOW
        return bool(user32.SetWindowPos(hwnd,-1,x,y,size[0],size[1],flags))
    except (AttributeError,OSError,tk.TclError):
        return False


def reinforce_windows_popup(widget,user32=None):
    """Keep an already placed Windows popup above the game without activation."""
    if platform.system()!='Windows':
        return False
    try:
        if user32 is None:
            import ctypes
            user32=ctypes.windll.user32
        prepare_windows_popup(widget,user32)
        hwnd=_windows_popup_handle(widget,user32)
        flags=0x0001 | 0x0002 | 0x0010 | 0x0040
        return bool(user32.SetWindowPos(hwnd,-1,0,0,0,0,flags))
    except (AttributeError,OSError,tk.TclError):
        return False










from discovery_watch_core.community import (
    _read_json_url, edsm_system_url, fetch_edsm_system, score_edsm_leads,
)








def replay_journal_paths(paths):
    """Analyse copied journals in an isolated temporary database; never touch live app data."""
    sources=[Path(path) for path in paths]
    if not sources:
        raise ValueError('Choose at least one journal file')
    with tempfile.TemporaryDirectory(prefix='discovery-watch-replay-') as directory:
        sandbox=Path(directory)
        for index,source in enumerate(sources,1):
            if not source.is_file():
                raise OSError(f'Journal file not found: {source}')
            shutil.copy2(source,sandbox/f'Journal.replay-{index:04d}.log')
        with Monitor(sandbox,sandbox/'replay.sqlite3') as monitor:
            findings=monitor.poll((True,True,True,True,False,True,True,False))
            alerts=monitor.recent(1000000)
            anomaly_rows=monitor.anomalies(limit=1000000)
            systems=monitor.db.execute('''SELECT COUNT(DISTINCT system_name) FROM historical_events
                WHERE system_name IS NOT NULL AND system_name!='' ''').fetchone()[0]
            event_types=dict(monitor.db.execute('''SELECT event_type,COUNT(*) FROM historical_events
                GROUP BY event_type ORDER BY COUNT(*) DESC,event_type''').fetchall())
            rules=dict(Counter(row[3] for row in alerts))
            anomaly_rules=dict(Counter(row[2] for row in anomaly_rows))
            return {'files':len(sources),'events':monitor.total_events,'systems':systems,
                    'findings':len(alerts),'potential_popups':len(monitor.popup_findings),
                    'duplicate_findings_suppressed':monitor.suppressed_duplicates,
                    'anomalies':len(anomaly_rows),
                    'unknown_system_findings':sum(1 for row in alerts if not row[2]),
                    'invalid_or_read_errors':len(monitor.errors),'finding_titles':rules,
                    'anomaly_rules':anomaly_rules,'event_types':event_types,
                    'errors':list(monitor.errors),
                    'policy_basis':'Built-in fresh-install detection defaults; live database settings were not read or changed.',
                    'isolation_note':'Replay used a temporary database; live Discovery Watch data was not changed.'}


def run_reliability_self_check():
    """Exercise arrival, duplicate and surface-signal handling in an isolated database."""
    with tempfile.TemporaryDirectory(prefix='discovery-watch-self-check-') as directory:
        folder=Path(directory); journal=folder/'Journal.reliability.log'; journal.write_text('',encoding='utf-8')
        with Monitor(folder,folder/'reliability.sqlite3') as monitor:
            cached_megaship={'event':'FSSSignalDiscovered',
                             'SignalName':'$MULTIPLAYER_SCENARIO_RELIABILITY;',
                             'SignalType':'Megaship'}
            monitor.db.execute('''INSERT INTO alerts
                (journal_file,line_no,rule,title,system_name,detail,raw_json)
                VALUES(?,?,?,?,?,?,?)''',('cached.log',1,'MEGASHIP','Megaship detected',
                'Reliability Alpha','cached internal identity',json.dumps(cached_megaship)))
            monitor.db.commit()
            monitor.start_at_end()
            events=[
                {'timestamp':'2026-01-01T00:00:01Z','event':'FSDJump','StarSystem':'Reliability Alpha','SystemAddress':1001},
                {'timestamp':'2026-01-01T00:00:01.5Z','event':'FSSSignalDiscovered','SystemAddress':1001,
                 'SignalType':'Megaship','SignalName_Localised':'Generation Ship Reliability'},
                {'timestamp':'2026-01-01T00:00:01.6Z','event':'SAASignalsFound','SystemAddress':1001,
                 'BodyName':'Reliability Alpha A 2','Signals':[
                     {'Type':'$SAA_SignalType_PlanetaryMiningLocation;',
                      'Type_Localised':'Planetary Mining Location','Count':1}]},
                {'timestamp':'2026-01-01T00:00:02Z','event':'FSSSignalDiscovered','SystemAddress':1001,
                 'SignalType':'Installation','SignalName_Localised':'Research Installation'},
                {'timestamp':'2026-01-01T00:00:03Z','event':'FSSSignalDiscovered','SystemAddress':1001,
                 'SignalType':'Installation','SignalName_Localised':'Research Installation'},
                {'timestamp':'2026-01-01T00:00:04Z','event':'FSDTarget','Name':'Reliability Beta','SystemAddress':1002},
                {'timestamp':'2026-01-01T00:00:05Z','event':'FSSBodySignals','SystemAddress':1001,
                 'BodyName':'Reliability Alpha A 1','Signals':[{'Type':'$SAA_SignalType_Biological;','Count':3}]},
                {'timestamp':'2026-01-01T00:00:06Z','event':'SAASignalsFound','SystemAddress':1001,
                 'BodyName':'Reliability Alpha A 1','Signals':[{'Type':'$SAA_SignalType_Biological;','Count':3}]},
                {'timestamp':'2026-01-01T00:00:07Z','event':'FSDJump','StarSystem':'Reliability Beta','SystemAddress':1002},
                {'timestamp':'2026-01-01T00:00:08Z','event':'FSDJump','StarSystem':'Reliability Alpha','SystemAddress':1001},
            ]
            with journal.open('a',encoding='utf-8') as output:
                output.writelines(json.dumps(event,separators=(',',':'))+'\n' for event in events)
            monitor.poll((True,True,True,True,True,True,True,False,
                          True,True,True,True,True,True))
            alerts=monitor.recent(1000)
            installation_rows=[row for row in alerts if row[3]=='Installation detected']
            live_megaship_rows=[row for row in alerts if row[13]=='MEGASHIP' and
                                row[6].endswith('Journal.reliability.log')]
            mining_rows=[row for row in alerts if 'Planetary Mining Location' in row[4]]
            biological_popups=[row for row in monitor.popup_findings if 'Biological surface signals' in row[0]]
            checks={
                'destination_did_not_replace_current_system':bool(installation_rows and installation_rows[0][2]=='Reliability Alpha'),
                'duplicate_installation_suppressed':len(installation_rows)==1 and monitor.suppressed_duplicates>=1,
                'megaship_alias_duplicate_suppressed':(
                    len(live_megaship_rows)==1 and
                    'already announced by Known POIs on arrival' in live_megaship_rows[0][12] and
                    monitor.db.execute('SELECT COUNT(*) FROM structure_identity_links').fetchone()[0]==1),
                'planetary_mining_checkbox_suppresses_nested_signal':(
                    len(mining_rows)==1 and
                    'Planetary Mining Location popups are disabled' in mining_rows[0][12] and
                    not any('Planetary Mining Location' in row[2]
                            for row in monitor.popup_findings)),
                'surface_confirmation_notified_once':len(biological_popups)==1,
                'return_arrival_recalled_known_pois':any(row[0].startswith('Known POIs on arrival') for row in monitor.popup_findings),
                'no_unknown_system_findings':all(bool(row[2]) for row in alerts),
                'final_arrival_context_correct':monitor.current_system=='Reliability Alpha',
            }
            return {'passed':all(checks.values()),'checks':checks,'events':monitor.total_events,
                    'findings':len(alerts),'potential_popups':len(monitor.popup_findings),
                    'duplicates_suppressed':monitor.suppressed_duplicates,
                    'isolation_note':'Built-in check used temporary journal and database files only.'}


def run_settings_behaviour_check():
    """Verify shared policies and their live journal paths without touching user data."""
    checks=validate_policy_registry()
    reliability=run_reliability_self_check()
    for key in ('duplicate_installation_suppressed',
                'planetary_mining_checkbox_suppresses_nested_signal',
                'surface_confirmation_notified_once',
                'return_arrival_recalled_known_pois'):
        checks['live_'+key]=bool(reliability['checks'].get(key))
    with tempfile.TemporaryDirectory(prefix='discovery-watch-contact-check-') as directory:
        folder=Path(directory); db_path=folder/'contacts.sqlite3'
        checks['experimental_contacts_default_off']=detection_preferences(db_path)==(True,True,False)
        save_detection_preferences(True,True,True,db_path)
        checks['experimental_contacts_saved_choice_preserved']=detection_preferences(db_path)==(True,True,True)
        journal=folder/'Journal.contacts.log'; journal.write_text('',encoding='utf-8')
        with Monitor(folder,db_path) as monitor:
            monitor.start_at_end(); monitor.contact_reconcile_delay=0
            events=[
                {'event':'FSDJump','StarSystem':'Contact Check','SystemAddress':9090},
                {'event':'FSSSignalDiscovered','SystemAddress':9090,'SignalName':'Known A','SignalType':'Megaship'},
                {'event':'FSSSignalDiscovered','SystemAddress':9090,'SignalName':'Known A','SignalType':'Megaship'},
                {'event':'FSSDiscoveryScan','SystemAddress':9090,'NonBodyCount':2},
                {'event':'FSSDiscoveryScan','SystemAddress':9090,'NonBodyCount':2},
            ]
            with journal.open('a',encoding='utf-8') as output:
                output.writelines(json.dumps(event,separators=(',',':'))+'\n' for event in events)
            monitor.poll((True,True,True,True,True))
            rows=[row for row in monitor.recent() if row[13]=='UNRESOLVED_NON_BODY_SIGNALS']
            checks['experimental_contacts_one_record_and_popup_per_visit']=(
                len(rows)==1 and sum(item[0].startswith('System contacts need review')
                                     for item in monitor.popup_findings)==1)
            with journal.open('a',encoding='utf-8') as output:
                output.write(json.dumps({'event':'FSSSignalDiscovered','SystemAddress':9090,
                                         'SignalName':'Known B','SignalType':'Installation'})+'\n')
            monitor.poll((True,True,True,True,True))
            state=monitor.db.execute('''SELECT lifecycle_state,remaining_count
                FROM contact_reconciliations''').fetchone()
            checks['experimental_contacts_resolve_in_place']=state==('resolved',0)
    return {'passed':all(checks.values()),'checks':checks,
            'controls_documented':len(SETTINGS_BEHAVIOUR),
            'isolation_note':'Settings check used policy definitions and temporary journal/database files only.'}


def _is_planetary_mining_identity(event):
    """Recognise a mining-location identity in one journal object."""
    return is_planetary_mining_signal(event)


def is_planetary_mining_location(event):
    """Recognise top-level and nested journal representations of the location."""
    if _is_planetary_mining_identity(event):
        return True
    return any(_is_planetary_mining_identity(item) for item in event.get('Signals') or []
               if isinstance(item,dict))
























class Monitor:
    def __init__(self, folder, db_path=DB_PATH, create_session=True):
        self.folder = Path(folder)
        self.offsets = {}
        self.buffers = {}
        self.deferred_prearrival = {}
        self.lines = {}
        self.systems = {}
        self.file_ids = {}
        self.events = deque(maxlen=2000)
        self.errors = deque(maxlen=100)
        self.popup_findings = []
        self.popup_metadata = []
        self.generic_popup_seen = set()
        self.current_unresolved = 0
        self.contact_visits = {}
        self.contact_reconcile_delay = 2.0
        self.structure_visit_context = None
        self.surface_alerted_this_visit = set()
        self.bio_confirmed_this_visit = set()
        self.known_poi_visit_context = None
        self.arrival_discovery_pending = None
        self.arrived_systems = []
        self.structure_alert_aliases = {'MEGASHIP': set(), 'INSTALLATION': set()}
        self.structure_alert_unnamed = set()
        self.structure_popup_aliases = {'MEGASHIP': set(), 'INSTALLATION': set()}
        self.structure_popup_unnamed = set()
        self.arrival_structure_records = {'MEGASHIP': [], 'INSTALLATION': []}
        self.suppressed_duplicates = 0
        self.last_anomaly_findings = []
        self.total_events = 0
        self.last_received = None
        self.active_file = None
        self.db_path=Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.db_path))
        self.db.execute('''CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY, journal_file TEXT NOT NULL, line_no INTEGER NOT NULL,
            rule TEXT NOT NULL, title TEXT NOT NULL, system_name TEXT,
            timestamp TEXT, detail TEXT NOT NULL, raw_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(journal_file,line_no,rule))''')
        alert_columns={row[1] for row in self.db.execute('PRAGMA table_info(alerts)')}
        if 'status' not in alert_columns:
            self.db.execute("ALTER TABLE alerts ADD COLUMN status TEXT NOT NULL DEFAULT 'new'")
        if 'notes' not in alert_columns:
            self.db.execute("ALTER TABLE alerts ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
        if 'level' not in alert_columns:
            self.db.execute("ALTER TABLE alerts ADD COLUMN level TEXT NOT NULL DEFAULT 'Review'")
        if 'origin' not in alert_columns:
            self.db.execute("ALTER TABLE alerts ADD COLUMN origin TEXT NOT NULL DEFAULT 'Live journal'")
        if 'popup_decision' not in alert_columns:
            self.db.execute("ALTER TABLE alerts ADD COLUMN popup_decision TEXT NOT NULL DEFAULT 'Legacy record - popup decision unavailable'")
        self.db.execute('''CREATE TABLE IF NOT EXISTS exploration_events (
            fingerprint TEXT PRIMARY KEY, journal_file TEXT NOT NULL, line_no INTEGER NOT NULL,
            timestamp TEXT, system_name TEXT, system_address TEXT, event_type TEXT NOT NULL,
            body_name TEXT, fact_type TEXT, raw_json TEXT NOT NULL, event_key TEXT)''')
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(exploration_events)')}
        if 'event_key' not in columns:
            self.db.execute('ALTER TABLE exploration_events ADD COLUMN event_key TEXT')
        for fingerprint, raw, line_no in self.db.execute('SELECT fingerprint,raw_json,line_no FROM exploration_events WHERE event_key IS NULL').fetchall():
            try: key = self.event_fingerprint(json.loads(raw), line_no)
            except (ValueError, TypeError): key = fingerprint
            self.db.execute('UPDATE exploration_events SET event_key=? WHERE fingerprint=?', (key,fingerprint))
        self.db.execute('DELETE FROM exploration_events WHERE rowid NOT IN (SELECT MIN(rowid) FROM exploration_events GROUP BY event_key)')
        self.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS exploration_event_key_idx ON exploration_events(event_key)')
        self.db.execute('CREATE INDEX IF NOT EXISTS exploration_system_idx ON exploration_events(system_name)')
        self.db.execute('CREATE INDEX IF NOT EXISTS exploration_body_idx ON exploration_events(body_name)')
        self.db.execute('''CREATE TABLE IF NOT EXISTS import_history (
            id INTEGER PRIMARY KEY, source_folder TEXT NOT NULL, files_seen INTEGER NOT NULL,
            valid_events INTEGER NOT NULL, exploration_added INTEGER NOT NULL,
            duplicates INTEGER NOT NULL, errors INTEGER NOT NULL,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY, event_key TEXT NOT NULL, rule TEXT NOT NULL,
            score INTEGER NOT NULL, system_name TEXT, body_name TEXT, timestamp TEXT,
            explanation TEXT NOT NULL, evidence_field TEXT NOT NULL, raw_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(event_key,rule))''')
        self.db.execute('CREATE INDEX IF NOT EXISTS anomaly_system_idx ON anomalies(system_name)')
        self.db.execute('''CREATE TABLE IF NOT EXISTS live_sessions (
            session_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS live_session_events (
            id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, sequence_no INTEGER NOT NULL,
            timestamp TEXT, event_type TEXT NOT NULL, system_name TEXT, body_name TEXT,
            summary TEXT NOT NULL, raw_json TEXT NOT NULL,
            UNIQUE(session_id,sequence_no))''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS historical_events (
            event_key TEXT PRIMARY KEY, timestamp TEXT, event_type TEXT NOT NULL,
            system_name TEXT, body_name TEXT, journal_file TEXT NOT NULL, line_no INTEGER NOT NULL,
            source_session TEXT NOT NULL, raw_json TEXT NOT NULL, imported_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        self.db.execute('CREATE INDEX IF NOT EXISTS historical_event_type_idx ON historical_events(event_type)')
        self.db.execute('CREATE INDEX IF NOT EXISTS historical_system_idx ON historical_events(system_name)')
        self.db.execute('''CREATE TABLE IF NOT EXISTS signal_catalog (
            signal_key TEXT PRIMARY KEY, display_name TEXT NOT NULL, policy TEXT NOT NULL DEFAULT 'record',
            priority INTEGER NOT NULL DEFAULT 40, popup INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT, last_seen TEXT, events_seen INTEGER NOT NULL DEFAULT 0,
            last_event_type TEXT, last_system TEXT)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS generic_signal_catalog (
            signature TEXT PRIMARY KEY, localised_name TEXT NOT NULL DEFAULT '',
            internal_name TEXT NOT NULL DEFAULT '', normalized_pattern TEXT NOT NULL DEFAULT '',
            policy TEXT NOT NULL DEFAULT 'review', match_mode TEXT NOT NULL DEFAULT 'exact',
            popup_mode TEXT NOT NULL DEFAULT 'once_system', priority INTEGER NOT NULL DEFAULT 50,
            first_seen TEXT, last_seen TEXT, events_seen INTEGER NOT NULL DEFAULT 0,
            last_event_type TEXT, last_system TEXT, notified INTEGER NOT NULL DEFAULT 0)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS discovery_cases (
            id INTEGER PRIMARY KEY, system_name TEXT, system_address TEXT, body_name TEXT NOT NULL,
            target_key TEXT NOT NULL, title TEXT NOT NULL, state TEXT NOT NULL,
            confidence TEXT NOT NULL, next_action TEXT NOT NULL, evidence_count INTEGER NOT NULL DEFAULT 1,
            first_seen TEXT, last_seen TEXT, last_event TEXT, status TEXT NOT NULL DEFAULT 'active',
            UNIQUE(system_address,body_name,target_key))''')
        self.db.execute('CREATE INDEX IF NOT EXISTS discovery_case_system_idx ON discovery_cases(system_name,status)')
        self.db.execute('''CREATE TABLE IF NOT EXISTS discovery_case_evidence (
            id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL, visit_key TEXT NOT NULL,
            event_key TEXT NOT NULL, stage TEXT NOT NULL, event_type TEXT NOT NULL,
            timestamp TEXT, raw_json TEXT NOT NULL,
            UNIQUE(case_id,visit_key,event_key))''')
        self.db.execute('CREATE INDEX IF NOT EXISTS discovery_case_evidence_visit_idx ON discovery_case_evidence(visit_key,case_id)')
        self.db.execute('''CREATE TABLE IF NOT EXISTS structure_identity_links (
            rule TEXT NOT NULL, system_name TEXT NOT NULL COLLATE NOCASE,
            alias_a TEXT NOT NULL, alias_b TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'arrival-fss reconciliation',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rule,system_name,alias_a,alias_b))''')
        self.db.execute('CREATE INDEX IF NOT EXISTS structure_identity_system_idx '
                        'ON structure_identity_links(rule,system_name)')
        self.db.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY, name TEXT NOT NULL,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        self._run_schema_migrations()
        self.db.execute('''CREATE TABLE IF NOT EXISTS commander_watchlists (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            pattern TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
            popup INTEGER NOT NULL DEFAULT 1, priority INTEGER NOT NULL DEFAULT 70,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
        _ensure_notification_delivery_table(self.db)
        self.db.execute('''CREATE TABLE IF NOT EXISTS edsm_cache (
            system_name TEXT PRIMARY KEY COLLATE NOCASE, fetched_at TEXT NOT NULL,
            status TEXT NOT NULL, payload_json TEXT NOT NULL, error TEXT NOT NULL DEFAULT '')''')
        self.db.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('generic_notify_once','1')")
        self._backfill_stored_anomalies()
        self._backfill_anomaly_alerts()
        for key,name,policy,priority,popup in (
            ('megaship','Megaship','alert',80,1),
            ('installation','Installation','alert',70,1),
            ('titan','Titan','alert',90,1),
            ('touristbeacon','TouristBeacon','alert',55,1),
            ('nonhumanuss','Nonhuman USS','alert',85,1),
            ('listeningpost','Listening Post','alert',80,1),
            ('fleetcarrier','FleetCarrier','ignore',0,0)):
            self.db.execute('''INSERT OR IGNORE INTO signal_catalog
                (signal_key,display_name,policy,priority,popup) VALUES(?,?,?,?,?)''',
                (key,name,policy,priority,popup))
        beacon_signature=self.generic_signature('Unregistered Comms Beacon','')
        self.db.execute('''INSERT OR IGNORE INTO generic_signal_catalog
            (signature,localised_name,normalized_pattern,policy,match_mode,popup_mode,priority)
            VALUES(?,?,?,'alert','contains','once_system',85)''',
            (beacon_signature,'Unregistered Comms Beacon','unregistered comms beacon'))
        self._remove_stored_fleet_carrier_false_positives()
        self._repair_stored_alert_systems()
        self.db.commit()
        self.system_addresses = {}
        self.current_system = None
        self.current_system_address = None
        self.session_id = (datetime.now().strftime('%Y%m%dT%H%M%S.%f')
                           if create_session else None)
        self.current_visit_key = None
        if create_session:
            self.db.execute('INSERT OR IGNORE INTO live_sessions(session_id,started_at) VALUES(?,?)',
                            (self.session_id,datetime.now().isoformat(timespec='seconds')))
            self.db.commit()

    @staticmethod
    def event_fingerprint(event, line_no=None):
        canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        identity = [event.get('timestamp'), event.get('event'), event.get('SystemAddress'),
                    event.get('BodyID'), event.get('BodyName') or event.get('Body'), canonical]
        if not event.get('timestamp'):
            identity.append(line_no)
        return hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()

    def _upsert_case(self,system,address,body,key,title,state,confidence,next_action,event):
        address_key=str(address) if address is not None else 'name:'+str(system or 'unknown').casefold()
        existing=self.db.execute('''SELECT id,state FROM discovery_cases
            WHERE system_address=? AND body_name=? AND target_key=?''',(address_key,body,key)).fetchone()
        ranks={'Lead':1,'Identified':2,'Confirmed':3,'Completed':4,'Abandoned':0}
        timestamp=event.get('timestamp')
        if existing:
            current=existing[1]
            chosen=state if ranks.get(state,0)>=ranks.get(current,0) else current
            case_id=existing[0]
            self.db.execute('''UPDATE discovery_cases SET system_name=?,title=?,state=?,confidence=?,
                next_action=?,last_seen=?,last_event=?,status=? WHERE id=?''',
                (system,title,chosen,confidence,next_action,timestamp,event.get('event'),
                 'closed' if chosen in ('Completed','Abandoned') else 'active',case_id))
        else:
            cursor=self.db.execute('''INSERT INTO discovery_cases
                (system_name,system_address,body_name,target_key,title,state,confidence,next_action,
                 evidence_count,first_seen,last_seen,last_event,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (system,address_key,body,key,title,state,confidence,next_action,0,timestamp,timestamp,
                 event.get('event'),'closed' if state in ('Completed','Abandoned') else 'active'))
            case_id=cursor.lastrowid
        visit_key=self.current_visit_key or f'{self.session_id}:unlocated'
        event_key=self.event_fingerprint(event)
        evidence=self.db.execute('''INSERT OR IGNORE INTO discovery_case_evidence
            (case_id,visit_key,event_key,stage,event_type,timestamp,raw_json)
            VALUES(?,?,?,?,?,?,?)''',(case_id,visit_key,event_key,state,event.get('event') or 'Unknown',
            timestamp,json.dumps(event,ensure_ascii=False,sort_keys=True)))
        if evidence.rowcount:
            self.db.execute('UPDATE discovery_cases SET evidence_count=evidence_count+1 WHERE id=?',(case_id,))

    def _update_discovery_cases(self,event,system,address):
        body=str(event.get('BodyName') or event.get('Body') or 'Unnamed body')
        labels={'thargoid':'Thargoid surface signals','guardian':'Guardian surface signals',
                'biological':'Biological surface signals','geological':'Geological surface signals',
                'human':'Human surface signals','other':'Other surface signals'}
        for item in surface_signal_observations(event):
            rule='SURFACE_'+item['category'].upper()
            if not finding_policy(rule).creates_investigation:
                continue
            early=event.get('event')=='FSSBodySignals'
            self._upsert_case(system,address,body,'surface:'+item['category'],labels[item['category']],
                'Lead' if early else 'Identified','Reported' if early else 'Confirmed',
                'Map this body with the Detailed Surface Scanner.' if early else 'Review or investigate the mapped surface signals.',event)
        for rule,_title,_detail in stratum_findings(event):
            if rule=='BIO_STRATUM_LEAD':
                self._upsert_case(system,address,body,'bio:stratum','Stratum investigation','Identified',
                                  'Confirmed genus','Land and identify the Stratum species.',event)
            else:
                completed=str(event.get('ScanType') or '').casefold()=='analyse'
                self._upsert_case(system,address,body,'bio:stratum','Stratum Tectonicas',
                                  'Completed' if completed else 'Confirmed','Confirmed species',
                                  'Sampling complete.' if completed else 'Complete the remaining organic samples.',event)
        if event.get('event')=='ScanOrganic':
            completed=str(event.get('ScanType') or '').casefold()=='analyse'
            species=str(event.get('Species_Localised') or event.get('Species') or 'Biological species')
            self._upsert_case(system,address,body,'surface:biological','Biological surface signals',
                              'Completed' if completed else 'Confirmed',f'Confirmed species: {species}',
                              'Sampling complete.' if completed else 'Complete the remaining organic samples.',event)

    def _run_schema_migrations(self):
        """Apply each derived-data migration once while preserving journal evidence."""
        migrations=(
            (1,'Remove obsolete mining-only Other investigations',
             self._remove_mining_only_discovery_cases),
            (2,'Add per-visit unresolved-contact reconciliation',
             self._create_contact_reconciliation_table),
            (3,'Complete legacy alert maintenance once',
             self._complete_legacy_alert_maintenance),
            (4,'Add startup performance indexes and maintenance checkpoints',
             self._add_startup_performance_indexes),
            (5,'Remove previously-discovered arrival-star history noise',
             self._remove_discovered_arrival_history),
        )
        applied={row[0] for row in self.db.execute(
            'SELECT version FROM schema_migrations').fetchall()}
        for version,name,operation in migrations:
            if version in applied:
                continue
            operation()
            self.db.execute('INSERT INTO schema_migrations(version,name) VALUES(?,?)',
                            (version,name))

    def _complete_legacy_alert_maintenance(self):
        """Normalise legacy importance values once instead of on every open."""
        for alert_id,rule in self.db.execute('SELECT id,rule FROM alerts').fetchall():
            self.db.execute('UPDATE alerts SET level=? WHERE id=?',(alert_level(rule),alert_id))

    def _add_startup_performance_indexes(self):
        self.db.execute('CREATE INDEX IF NOT EXISTS exploration_address_idx '
                        'ON exploration_events(system_address)')
        self.db.execute('CREATE INDEX IF NOT EXISTS exploration_summary_idx '
                        'ON exploration_events(system_name,fact_type,event_type,body_name)')
        self.db.execute('CREATE INDEX IF NOT EXISTS alert_rule_idx ON alerts(rule)')
        self.db.execute('''CREATE TABLE IF NOT EXISTS maintenance_state (
            key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
        # Older interface-only Monitor objects created short empty sessions.
        # Restrict cleanup to closed, empty sessions lasting no more than five seconds.
        self.db.execute('''DELETE FROM live_sessions
            WHERE ended_at IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM live_session_events
                              WHERE live_session_events.session_id=live_sessions.session_id)
              AND ABS((julianday(ended_at)-julianday(started_at))*86400.0)<=5.0''')

    def _remove_discovered_arrival_history(self):
        """Remove only non-actionable true-status findings, not journal evidence."""
        self.db.execute('''DELETE FROM alerts
            WHERE rule='SYSTEM_DISCOVERY_STATUS'
              AND (title='Arrival star previously discovered'
                   OR detail LIKE '%WasDiscovered=true%')''')

    def _maintenance_checkpoint(self,key):
        try:
            row=self.db.execute('SELECT value FROM maintenance_state WHERE key=?',(key,)).fetchone()
        except sqlite3.OperationalError:
            return 0
        try: return int(row[0]) if row else 0
        except (TypeError,ValueError): return 0

    def _set_maintenance_checkpoint(self,key,value):
        self.db.execute('''INSERT INTO maintenance_state(key,value) VALUES(?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value''',(key,str(int(value))))

    def _remove_stored_fleet_carrier_false_positives(self):
        """Retain compatibility cleanup for records imported after migration."""
        for alert_id,raw in self.db.execute(
                "SELECT id,raw_json FROM alerts WHERE rule='MEGASHIP'").fetchall():
            try:
                stored=json.loads(raw)
                stored_type=str(stored.get('signalType') or stored.get('SignalType') or '')
                if stored_type.casefold().replace(' ','')=='fleetcarrier':
                    self.db.execute('DELETE FROM alerts WHERE id=?',(alert_id,))
            except (ValueError,TypeError):
                continue

    def _create_contact_reconciliation_table(self):
        self.db.execute('''CREATE TABLE IF NOT EXISTS contact_reconciliations (
            visit_key TEXT PRIMARY KEY, session_id TEXT NOT NULL,
            system_address TEXT, system_name TEXT,
            reported_count INTEGER NOT NULL DEFAULT 0,
            identified_count INTEGER NOT NULL DEFAULT 0,
            remaining_count INTEGER NOT NULL DEFAULT 0,
            lifecycle_state TEXT NOT NULL DEFAULT 'pending',
            first_timestamp TEXT, last_timestamp TEXT,
            journal_file TEXT NOT NULL DEFAULT '', line_no INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT NOT NULL DEFAULT '{}', alert_id INTEGER,
            popup_sent INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        self.db.execute('CREATE INDEX IF NOT EXISTS contact_reconciliation_system_idx '
                        'ON contact_reconciliations(system_address,system_name)')

    def schema_version(self):
        row=self.db.execute('SELECT MAX(version) FROM schema_migrations').fetchone()
        return int(row[0] or 0)

    def _remove_mining_only_discovery_cases(self):
        """Remove obsolete Other leads that were derived only from mining locations."""
        case_ids=[row[0] for row in self.db.execute(
            "SELECT id FROM discovery_cases WHERE target_key='surface:other'").fetchall()]
        for case_id in case_ids:
            observations=[]
            for (raw,) in self.db.execute(
                    'SELECT raw_json FROM discovery_case_evidence WHERE case_id=?',(case_id,)):
                try: event=json.loads(raw)
                except (ValueError,TypeError): continue
                observations.extend(surface_signal_observations(event))
            if observations and not any(item['category']=='other' for item in observations):
                self.db.execute('DELETE FROM discovery_case_evidence WHERE case_id=?',(case_id,))
                self.db.execute('DELETE FROM discovery_cases WHERE id=?',(case_id,))

    def current_visit_cases(self,limit=100):
        """Return cases evidenced during this confirmed visit, including completed work."""
        if not self.current_visit_key:
            return []
        rows=self.db.execute('''SELECT c.id,c.system_name,c.body_name,c.title,c.confidence,c.next_action,
            e.stage,e.event_type FROM discovery_cases c JOIN discovery_case_evidence e ON e.case_id=c.id
            WHERE e.visit_key=? ORDER BY e.id''',(self.current_visit_key,)).fetchall()
        ranks={'Lead':1,'Identified':2,'Confirmed':3,'Completed':4,'Abandoned':0}
        grouped={}
        for row in rows:
            case_id=row[0]
            item=grouped.setdefault(case_id,{'base':row[:6],'stage':row[6],
                                             'event':row[7],'count':0})
            item['count']+=1
            if ranks.get(row[6],0)>=ranks.get(item['stage'],0):
                item['stage']=row[6]; item['event']=row[7]
        result=[]
        for item in grouped.values():
            case_id,system,body,title,confidence,next_action=item['base']
            result.append((case_id,system,body,title,item['stage'],confidence,next_action,
                           item['count'],item['event']))
        result.sort(key=lambda row:(-ranks.get(row[4],0),row[2].casefold(),row[3].casefold()))
        return result[:int(limit)]

    def current_visit_intelligence(self):
        """Summarise evidence stages for the present system visit."""
        rows=self.current_visit_cases(10000)
        counts=Counter(row[4] for row in rows)
        return {'visit_key':self.current_visit_key,'cases':len(rows),
                'leads':counts['Lead'],'identified':counts['Identified'],
                'confirmed':counts['Confirmed'],'completed':counts['Completed'],
                'evidence':sum(row[7] for row in rows)}

    def active_cases(self,system=None,limit=100):
        sql='''SELECT id,system_name,body_name,title,state,confidence,next_action,evidence_count,last_event
               FROM discovery_cases WHERE status='active' '''
        args=[]
        if system: sql+='AND system_name=? '; args.append(system)
        sql+='ORDER BY last_seen DESC,id DESC LIMIT ?'; args.append(int(limit))
        return self.db.execute(sql,args).fetchall()

    def abandon_cases(self,system):
        if system:
            self.db.execute("UPDATE discovery_cases SET state='Abandoned',status='closed',next_action='Left system before completing this investigation.' WHERE system_name=? AND status='active'",(system,))

    def watchlists(self):
        return self.db.execute('SELECT id,name,pattern,enabled,popup,priority FROM commander_watchlists ORDER BY name COLLATE NOCASE').fetchall()

    def add_watchlist(self,name,pattern,popup=True,priority=70):
        name=str(name).strip(); pattern=str(pattern).strip()
        if not name or not pattern: raise ValueError('Watchlist name and pattern are required')
        self.db.execute('''INSERT INTO commander_watchlists(name,pattern,enabled,popup,priority)
            VALUES(?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET pattern=excluded.pattern,popup=excluded.popup,priority=excluded.priority''',
            (name,pattern,1,1 if popup else 0,max(0,min(100,int(priority)))))
        self.db.commit()

    def toggle_watchlist(self,watch_id,field):
        if field not in ('enabled','popup'): raise ValueError('Invalid watchlist field')
        self.db.execute(f'UPDATE commander_watchlists SET {field}=CASE {field} WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(int(watch_id),)); self.db.commit()

    def delete_watchlist(self,watch_id):
        self.db.execute('DELETE FROM commander_watchlists WHERE id=?',(int(watch_id),)); self.db.commit()

    def _watchlist_matches(self,event):
        text=json.dumps(event,ensure_ascii=False,sort_keys=True).casefold()
        matches=[]
        for row in self.db.execute('SELECT id,name,pattern,popup,priority FROM commander_watchlists WHERE enabled=1'):
            if row[2].casefold() in text: matches.append(row)
        return matches

    def _store_exploration(self, event, journal_file, line_no, system, address):
        self.last_anomaly_findings=[]
        fact = discovery_facts(event)
        if event.get('event') not in ('FSDJump', 'Location', 'CarrierJump', 'Scan',
                                      'SAAScanComplete', 'ScanOrganic', 'FSSDiscoveryScan',
                                      'FSSAllBodiesFound', 'FSSBodySignals', 'SAASignalsFound',
                                      'CodexEntry'):
            return False
        raw = json.dumps(event, ensure_ascii=False, sort_keys=True)
        event_key = self.event_fingerprint(event, line_no)
        cursor = self.db.execute('''INSERT OR IGNORE INTO exploration_events
            (fingerprint,journal_file,line_no,timestamp,system_name,system_address,
             event_type,body_name,fact_type,raw_json,event_key) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (event_key, str(journal_file), line_no, event.get('timestamp'), system,
             str(address) if address is not None else None, event.get('event'),
             fact[1] if fact else event.get('BodyName'), fact[0] if fact else None, raw,event_key))
        self.last_anomaly_findings=self._store_anomalies(
            event, event_key, system, raw, address=address)
        return bool(cursor.rowcount)

    def _enabled_exploration_criteria(self):
        enabled=set()
        for rule in EXPLORATION_CRITERIA:
            key='exploration_criterion_'+rule.casefold()
            self.db.execute('INSERT OR IGNORE INTO preferences(key,value) VALUES(?,?)',(key,'1'))
            row=self.db.execute('SELECT value FROM preferences WHERE key=?',(key,)).fetchone()
            if row and row[0]=='1': enabled.add(rule)
        return enabled

    def _system_scan_events(self,system,address):
        if address is not None:
            rows=self.db.execute('''SELECT raw_json FROM exploration_events
                WHERE event_type='Scan' AND system_address=? ORDER BY rowid''',(str(address),)).fetchall()
        elif system:
            rows=self.db.execute('''SELECT raw_json FROM exploration_events
                WHERE event_type='Scan' AND system_name=? COLLATE NOCASE ORDER BY rowid''',(system,)).fetchall()
        else:
            rows=[]
        latest={}
        for (raw,) in rows:
            try: scan=json.loads(raw)
            except (ValueError,TypeError): continue
            body_id=scan.get('BodyID')
            if body_id is not None: latest[body_id]=scan
        return list(latest.values())

    def _store_anomalies(self, event, event_key, system, raw, address=None):
        scans=self._system_scan_events(system,address or event.get('SystemAddress'))
        findings=detect_anomalies(event,scans,self._enabled_exploration_criteria())
        inserted=[]
        for rule, score, explanation, evidence_field in findings:
            body_name=event.get('BodyName') or event.get('Body')
            if rule in ('ALL_FSD_MATERIALS','ALL_SURFACE_MATERIALS'):
                prior=self.db.execute('''SELECT 1 FROM anomalies WHERE rule=?
                    AND COALESCE(system_name,'')=COALESCE(?, '') LIMIT 1''',
                    (rule,system)).fetchone()
                if prior:
                    continue
            elif rule in ('CLOSE_BINARY','COLLIDING_BINARY'):
                prior=self.db.execute('''SELECT 1 FROM anomalies WHERE rule=?
                    AND COALESCE(system_name,'')=COALESCE(?, '')
                    AND (COALESCE(body_name,'')=COALESCE(?, '') OR explanation LIKE ?)
                    LIMIT 1''',(rule,system,body_name,'%'+str(body_name or '')+'%')).fetchone()
                if prior:
                    continue
            elif rule in EXPLORATION_CRITERIA and rule!='CODEX_DISCOVERY':
                prior=self.db.execute('''SELECT 1 FROM anomalies WHERE rule=?
                    AND COALESCE(system_name,'')=COALESCE(?, '')
                    AND COALESCE(body_name,'')=COALESCE(?, '') LIMIT 1''',
                    (rule,system,body_name)).fetchone()
                if prior:
                    continue
            cursor=self.db.execute('''INSERT OR IGNORE INTO anomalies
                (event_key,rule,score,system_name,body_name,timestamp,explanation,evidence_field,raw_json)
                VALUES(?,?,?,?,?,?,?,?,?)''', (event_key,rule,score,system,
                body_name,event.get('timestamp'),explanation,evidence_field,raw))
            if cursor.rowcount:
                inserted.append((rule,score,explanation,evidence_field))
        return inserted

    def _backfill_stored_anomalies(self):
        # One-time migration: recover findings from existing records without replaying alerts.
        version = self.db.execute("SELECT value FROM preferences WHERE key='anomaly_backfill_version'").fetchone()
        if version and version[0] == '3':
            return
        for key, raw, system in self.db.execute('''SELECT event_key,raw_json,system_name FROM historical_events
            WHERE event_type IN ('Scan','FSSBodySignals','SAASignalsFound','CodexEntry') ORDER BY rowid'''):
            try: event = json.loads(raw)
            except (ValueError, TypeError): continue
            if isinstance(event, dict):
                self._store_anomalies(event, key, system, raw,address=event.get('SystemAddress'))
        for key, raw, system,address in self.db.execute('''SELECT COALESCE(event_key,fingerprint),raw_json,system_name,system_address
            FROM exploration_events WHERE event_type IN ('Scan','FSSBodySignals','SAASignalsFound','CodexEntry') ORDER BY rowid'''):
            try: event = json.loads(raw)
            except (ValueError, TypeError): continue
            if isinstance(event, dict):
                self._store_anomalies(event, key, system, raw,address=address)
        self.db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('anomaly_backfill_version','3')")

    def _backfill_anomaly_alerts(self):
        """Expose legacy anomaly evidence in Discovery History without replaying popups."""
        version=self.db.execute(
            "SELECT value FROM preferences WHERE key='unified_anomaly_history_version'").fetchone()
        if version and version[0]=='2':
            return
        event_keys=[row[0] for row in self.db.execute(
            'SELECT DISTINCT event_key FROM anomalies ORDER BY event_key').fetchall()]
        for event_key in event_keys:
            rows=self.db.execute('''SELECT rule,score,system_name,body_name,timestamp,explanation,
                raw_json,status,id FROM anomalies WHERE event_key=? ORDER BY score DESC,rule''',
                (event_key,)).fetchall()
            if not rows:
                continue
            source=self.db.execute('''SELECT journal_file,line_no FROM exploration_events
                WHERE COALESCE(event_key,fingerprint)=? LIMIT 1''',(event_key,)).fetchone()
            if not source:
                source=self.db.execute('''SELECT journal_file,line_no FROM historical_events
                    WHERE event_key=? LIMIT 1''',(event_key,)).fetchone()
            journal_file,line_no=source if source else ('Anomaly migration',-int(rows[0][8]))
            body_name=rows[0][3] or 'journal event'
            rules=', '.join(f'{row[0]} ({row[1]})' for row in rows)
            explanations='; '.join(dict.fromkeys(row[5] for row in rows if row[5]))
            detail=f'Rules: {rules}. {explanations}'
            statuses=[row[7] for row in rows]
            status='dismissed' if statuses and all(value=='dismissed' for value in statuses) else \
                   'acknowledged' if any(value=='reviewed' for value in statuses) else 'new'
            self.db.execute('''INSERT OR IGNORE INTO alerts
                (journal_file,line_no,rule,title,system_name,timestamp,detail,raw_json,status,
                 level,origin,popup_decision) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                (str(journal_file),int(line_no or 0),'ANOMALY_ALERT',f'Anomaly review: {body_name}',
                 rows[0][2],rows[0][4],detail,rows[0][6],status,'Review','Anomaly migration',
                 'Historical anomaly migrated to unified Discovery History without a popup'))
        self.db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('unified_anomaly_history_version','2')")

    def _store_historical(self,event,journal_file,line_no,system):
        key=self.event_fingerprint(event,line_no)
        cursor=self.db.execute('''INSERT OR IGNORE INTO historical_events
            (event_key,timestamp,event_type,system_name,body_name,journal_file,line_no,source_session,raw_json)
            VALUES(?,?,?,?,?,?,?,?,?)''',(key,event.get('timestamp'),event.get('event','Unknown'),system,
            str(event.get('BodyName') or event.get('Body') or '') or None,str(journal_file),line_no,
            Path(journal_file).name,json.dumps(event,ensure_ascii=False,sort_keys=True)))
        return bool(cursor.rowcount)

    @staticmethod
    def signal_type(event):
        value=str(event.get('signalType') or event.get('SignalType') or '').strip()
        key=value.casefold().replace(' ','')
        # Elite uses derived classifications such as StationMegaShip for some
        # fixed navigation-panel assets. They are still Megaships and must use
        # the commander's existing Megaship policy instead of silently creating
        # a new, record-only signal category.
        if 'megaship' in key and key!='fleetcarrier':
            return 'Megaship','megaship'
        return value,key

    @staticmethod
    def _arrival_ordered_records(records):
        """Place an immediately pre-arrival FSS signal after its matching jump.

        Elite can write ``FSSSignalDiscovered`` with only a SystemAddress one
        line before the matching FSDJump supplies StarSystem. Preserve each
        source line number, but process the confirmed arrival first so the
        signal cannot inherit the system the commander just left.
        """
        ordered=list(records)
        index=0
        while index<len(ordered):
            _line,event=ordered[index]
            if event.get('event') not in ('FSDJump','CarrierJump'):
                index+=1; continue
            address=event.get('SystemAddress'); timestamp=event.get('timestamp')
            start=index
            while start>0:
                _previous_line,previous=ordered[start-1]
                if (previous.get('event')!='FSSSignalDiscovered' or
                        Monitor.event_system_name(previous) or
                        previous.get('SystemAddress') is None or address is None or
                        str(previous.get('SystemAddress'))!=str(address) or
                        (timestamp and previous.get('timestamp') and
                         previous.get('timestamp')!=timestamp)):
                    break
                start-=1
            if start<index:
                arrival=ordered.pop(index)
                ordered.insert(start,arrival)
                index+=1
            else:
                index+=1
        return ordered

    def _begin_structure_visit(self,event,system,address):
        kind=event.get('event')
        if kind not in LOCATION_CONTEXT_EVENTS:
            return
        context=str(address) if address is not None else self.normalize_signal_name(system)
        # FSDJump/CarrierJump always begin a visit. A Location event immediately
        # following a jump must not clear identities already collected there.
        new_visit=kind in ('FSDJump','CarrierJump','LoadGame') or context != self.structure_visit_context
        if new_visit:
            self.structure_alert_aliases = {'MEGASHIP': set(), 'INSTALLATION': set()}
            self.structure_alert_unnamed.clear()
            self.structure_popup_aliases = {'MEGASHIP': set(), 'INSTALLATION': set()}
            self.structure_popup_unnamed.clear()
            self.arrival_structure_records = {'MEGASHIP': [], 'INSTALLATION': []}
            self.surface_alerted_this_visit.clear()
            self.bio_confirmed_this_visit.clear()
            self.current_visit_key=f'{self.session_id}:{self.total_events}:{context or "unknown"}'
            self.contact_visits[self.current_visit_key]={
                'visit_key':self.current_visit_key,'system':system,'address':address,
                'reported':0,'identities':set(),'remaining':0,'state':'pending',
                'first_timestamp':event.get('timestamp'),'last_timestamp':event.get('timestamp'),
                'journal_file':'','line_no':0,'raw_json':'{}','alert_id':None,
                'popup_sent':False,'due_at':None,
            }
            self.current_unresolved=0
        self.structure_visit_context=context

    def _contact_visit(self,system,address,event=None):
        """Return the current visit state, including launches that start mid-system."""
        if not self.current_visit_key:
            context=str(address) if address is not None else self.normalize_signal_name(system)
            self.current_visit_key=f'{self.session_id}:{self.total_events}:{context or "unknown"}'
        visit=self.contact_visits.get(self.current_visit_key)
        if visit is None:
            visit={'visit_key':self.current_visit_key,'system':system,'address':address,
                   'reported':0,'identities':set(),'remaining':0,'state':'pending',
                   'first_timestamp':(event or {}).get('timestamp'),
                   'last_timestamp':(event or {}).get('timestamp'),
                   'journal_file':'','line_no':0,'raw_json':'{}','alert_id':None,
                   'popup_sent':False,'due_at':None}
            self.contact_visits[self.current_visit_key]=visit
        if system: visit['system']=system
        if address is not None: visit['address']=address
        if event and event.get('timestamp'):
            visit['last_timestamp']=event.get('timestamp')
            if not visit['first_timestamp']: visit['first_timestamp']=event.get('timestamp')
        return visit

    def _contact_identity(self,event):
        """Return a stable identity without collapsing separate temporary USS contacts."""
        if event.get('USSType') or event.get('USSType_Localised') or event.get('TimeRemaining') is not None:
            return self.event_fingerprint(event)
        fields=('SignalName_Localised','SignalName','SignalType','signalType',
                'StationName','StationType','Type_Localised','Type')
        values=[self.normalize_signal_name(event.get(key)) for key in fields]
        values=[value for value in values if value]
        return '|'.join(values) if values else self.event_fingerprint(event)

    def _contact_counts(self,visit):
        identified=len(visit['identities'])
        remaining=max(0,int(visit['reported'])-identified)
        visit['remaining']=remaining
        if visit['reported'] and remaining==0:
            visit['state']='resolved'
        elif visit['state']=='resolved' and remaining:
            visit['state']='pending'
        if visit['visit_key']==self.current_visit_key:
            self.current_unresolved=remaining
        return identified,remaining

    def _store_contact_visit(self,visit):
        identified,remaining=self._contact_counts(visit)
        self.db.execute('''INSERT INTO contact_reconciliations
            (visit_key,session_id,system_address,system_name,reported_count,identified_count,
             remaining_count,lifecycle_state,first_timestamp,last_timestamp,journal_file,line_no,
             raw_json,alert_id,popup_sent,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(visit_key) DO UPDATE SET
             system_address=excluded.system_address,system_name=excluded.system_name,
             reported_count=excluded.reported_count,identified_count=excluded.identified_count,
             remaining_count=excluded.remaining_count,lifecycle_state=excluded.lifecycle_state,
             last_timestamp=excluded.last_timestamp,journal_file=excluded.journal_file,
             line_no=excluded.line_no,raw_json=excluded.raw_json,alert_id=excluded.alert_id,
             popup_sent=excluded.popup_sent,updated_at=CURRENT_TIMESTAMP''',
            (visit['visit_key'],self.session_id,
             str(visit['address']) if visit['address'] is not None else None,visit['system'],
             int(visit['reported']),identified,remaining,visit['state'],visit['first_timestamp'],
             visit['last_timestamp'],visit['journal_file'],int(visit['line_no']),visit['raw_json'],
             visit['alert_id'],1 if visit['popup_sent'] else 0))

    @staticmethod
    def _contact_detail(visit):
        identified=len(visit['identities'])
        remaining=max(0,int(visit['reported'])-identified)
        state=str(visit['state']).capitalize()
        return (f'Experimental estimate: reported={int(visit["reported"])}; '
                f'identified this visit={identified}; remaining={remaining}; state={state}. '
                'Check the navigation panel or FSS. This is a reconciliation prompt, '
                'not evidence that any contact is rare or unusual.')

    def _record_contact_finding(self,visit,found,allow_popup):
        """Create or update the single History observation belonging to a visit."""
        title='System contacts need review (Experimental)'
        if visit['state']=='resolved': title='System contacts resolved (Experimental)'
        elif visit['state']=='incomplete': title='System contacts incomplete (Experimental)'
        detail=self._contact_detail(visit)
        if visit['alert_id']:
            self.db.execute('UPDATE alerts SET title=?,system_name=?,detail=? WHERE id=?',
                            (title,visit['system'],detail,visit['alert_id']))
        else:
            cursor=self.db.execute('''INSERT OR IGNORE INTO alerts
                (journal_file,line_no,rule,title,system_name,timestamp,detail,raw_json,level,
                 origin,popup_decision) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                (visit['journal_file'],int(visit['line_no']),'UNRESOLVED_NON_BODY_SIGNALS',title,
                 visit['system'],visit['last_timestamp'],detail,visit['raw_json'],'Informational',
                 'Live journal','Pending notification decision'))
            if cursor.rowcount:
                visit['alert_id']=cursor.lastrowid
                found.append((title,visit['system'] or 'Unknown system',detail))
            else:
                row=self.db.execute('''SELECT id FROM alerts
                    WHERE journal_file=? AND line_no=? AND rule='UNRESOLVED_NON_BODY_SIGNALS' ''',
                    (visit['journal_file'],int(visit['line_no']))).fetchone()
                if row: visit['alert_id']=row[0]
        if allow_popup and visit['alert_id'] and not visit['popup_sent'] and visit['remaining']:
            finding=(title,visit['system'] or 'Unknown system',detail)
            self.popup_findings.append(finding)
            self.popup_metadata.append(popup_identity(json.loads(visit['raw_json']),title,
                                                       'UNRESOLVED_NON_BODY_SIGNALS'))
            visit['popup_sent']=True
            self.db.execute('UPDATE alerts SET popup_decision=? WHERE id=?',
                            ('Popup eligible once for this system visit; the interface master popup switch is applied separately',
                             visit['alert_id']))
        elif visit['alert_id'] and not visit['popup_sent']:
            self.db.execute('UPDATE alerts SET popup_decision=? WHERE id=?',
                            ('Saved without popup because the contact estimate resolved or the visit ended before notification',
                             visit['alert_id']))
        self._store_contact_visit(visit)

    def _observe_contact_signal(self,event,system,address,found):
        visit=self._contact_visit(system,address,event)
        visit['identities'].add(self._contact_identity(event))
        self._contact_counts(visit)
        if visit['alert_id']:
            self._record_contact_finding(visit,found,False)
        else:
            self._store_contact_visit(visit)

    def _observe_contact_scan(self,event,system,address,journal_file,line_no):
        reported=event.get('NonBodyCount')
        if isinstance(reported,bool) or not isinstance(reported,(int,float)) or reported<0:
            return
        visit=self._contact_visit(system,address,event)
        visit['reported']=int(reported)
        visit['journal_file']=str(journal_file)
        visit['line_no']=int(line_no)
        visit['raw_json']=json.dumps(event,ensure_ascii=False)
        if visit['due_at'] is None:
            visit['due_at']=time.monotonic()+self.contact_reconcile_delay
        self._contact_counts(visit)
        self._store_contact_visit(visit)

    def _emit_due_contact_findings(self,found):
        now=time.monotonic()
        current=self.contact_visits.get(self.current_visit_key)
        for visit in ([current] if current else []):
            if visit['due_at'] is None or visit['due_at']>now or visit['alert_id']:
                continue
            self._contact_counts(visit)
            if visit['remaining']:
                self._record_contact_finding(visit,found,True)

    def _finalize_contact_visit(self,found):
        visit=self.contact_visits.get(self.current_visit_key)
        if not visit or not visit['reported']:
            return
        self._contact_counts(visit)
        visit['state']='resolved' if not visit['remaining'] else 'incomplete'
        if visit['remaining'] or visit['alert_id']:
            self._record_contact_finding(visit,found,False)
        else:
            self._store_contact_visit(visit)

    def _duplicate_structure_alert(self,rule,event):
        if rule not in self.structure_alert_aliases:
            return False
        aliases=self._structure_aliases(event)
        seen=self.structure_alert_aliases[rule]
        duplicate=(rule in self.structure_alert_unnamed or bool(aliases & seen)) if aliases else \
                  (rule in self.structure_alert_unnamed or bool(seen))
        if aliases:
            seen.update(aliases)
        else:
            self.structure_alert_unnamed.add(rule)
        return duplicate

    def _structure_aliases(self,event):
        """Return every usable internal and localised identity for a structure."""
        aliases={self.normalize_signal_name(event.get(key)) for key in
                 ('SignalName_Localised','SignalName','Name_Localised','Name',
                  'StationName','Type_Localised','Type')}
        aliases.discard('')
        aliases.difference_update({'megaship','mega ship','installation'})
        return aliases

    @staticmethod
    def _unstable_structure_alias(alias):
        """Return True for journal identifiers that are not reliable display names."""
        text=' '.join(str(alias or '').casefold().split())
        return (text.startswith('$') or text.endswith(';') or '#index=' in text or
                'multiplayer_scenario' in text or 'scenario_' in text)

    def _linked_structure_aliases(self,rule,system,aliases):
        """Expand identities through previously verified same-system alias links."""
        expanded={self.normalize_signal_name(value) for value in aliases}
        expanded.discard('')
        if not system or rule not in self.structure_popup_aliases or not expanded:
            return expanded
        rows=self.db.execute('''SELECT alias_a,alias_b FROM structure_identity_links
            WHERE rule=? AND system_name=? COLLATE NOCASE''',(rule,system)).fetchall()
        changed=True
        while changed:
            changed=False
            for left,right in rows:
                if left in expanded and right not in expanded:
                    expanded.add(right); changed=True
                elif right in expanded and left not in expanded:
                    expanded.add(left); changed=True
        return expanded

    def _store_structure_alias_links(self,rule,system,left_aliases,right_aliases):
        """Remember a cautious reconciliation without altering original evidence."""
        if not system or rule not in self.structure_popup_aliases:
            return
        for left in left_aliases:
            for right in right_aliases:
                left=self.normalize_signal_name(left); right=self.normalize_signal_name(right)
                if not left or not right or left==right:
                    continue
                alias_a,alias_b=sorted((left,right))
                self.db.execute('''INSERT OR IGNORE INTO structure_identity_links
                    (rule,system_name,alias_a,alias_b) VALUES(?,?,?,?)''',
                    (rule,system,alias_a,alias_b))

    def _remember_structure_popup(self,rule,name=None,aliases=None):
        """Return whether a structure identity was already announced this visit."""
        if rule not in self.structure_popup_aliases:
            return False
        identities={self.normalize_signal_name(value) for value in (aliases or ())}
        alias=self.normalize_signal_name(name)
        if alias:
            identities.add(alias)
        identities.discard('')
        identities.difference_update({'megaship','mega ship','installation'})
        seen=self.structure_popup_aliases[rule]
        duplicate=(rule in self.structure_popup_unnamed or bool(identities & seen)) if identities else \
                  (rule in self.structure_popup_unnamed or bool(seen))
        if identities:
            seen.update(identities)
        else:
            self.structure_popup_unnamed.add(rule)
        return duplicate

    def _duplicate_structure_popup(self,rule,event):
        if rule not in self.structure_popup_aliases:
            return False
        system=self.current_system or self.event_system_name(event)
        raw_aliases=self._structure_aliases(event)
        aliases=self._linked_structure_aliases(rule,system,raw_aliases)
        records=self.arrival_structure_records.get(rule,[])
        matching=[record for record in records if aliases and record['aliases'] & aliases]
        if matching:
            matching[0]['matched']=True
            matching[0]['aliases'].update(aliases)
            self.structure_popup_aliases[rule].update(aliases)
            return True
        seen=self.structure_popup_aliases[rule]
        if aliases and aliases & seen:
            return True
        if not aliases and (rule in self.structure_popup_unnamed or bool(seen)):
            return True

        # Some journal paths expose only an internal token on arrival and only a
        # localised name after FSS. Reconcile one unambiguous cached candidate,
        # but never merge two clear, differently named ships.
        unmatched=[record for record in records if not record['matched']]
        cached_has_stable=any(not self._unstable_structure_alias(alias)
                              for alias in unmatched[0]['aliases']) if len(unmatched)==1 else False
        live_has_stable=any(not self._unstable_structure_alias(alias) for alias in raw_aliases)
        if (event.get('event')=='FSSSignalDiscovered' and len(unmatched)==1 and aliases and
                (not cached_has_stable or not live_has_stable)):
            record=unmatched[0]
            self._store_structure_alias_links(rule,system,record['aliases'],raw_aliases)
            record['matched']=True
            record['aliases'].update(aliases)
            self.structure_popup_aliases[rule].update(record['aliases'])
            return True

        if aliases:
            seen.update(aliases)
        else:
            self.structure_popup_unnamed.add(rule)
        return False

    @staticmethod
    def _poi_name(event, fallback):
        for key in ('SignalName_Localised','SignalName','Name_Localised','Name',
                    'StationName','Type_Localised'):
            value=str(event.get(key) or '').strip()
            if value and value.casefold() not in ('megaship','installation'):
                return value
        return fallback

    def _known_poi_groups(self,system):
        """Merge stored POI rows that share an internal or localised identity."""
        if not system:
            return []
        placeholders=','.join('?' for _ in KNOWN_POI_RULES)
        rows=self.db.execute(f'''SELECT rule,title,raw_json FROM alerts
            WHERE system_name=? COLLATE NOCASE AND rule IN ({placeholders}) ORDER BY id''',
            (system,*KNOWN_POI_RULES)).fetchall()
        groups=[]
        for rule,title,raw in rows:
            try: event=json.loads(raw)
            except (ValueError,TypeError): event={}
            label=KNOWN_POI_RULES[rule]
            name=self._poi_name(event,label)
            aliases=(self._structure_aliases(event) if rule in self.structure_popup_aliases
                     else {self.normalize_signal_name(name)})
            if rule in self.structure_popup_aliases:
                aliases=self._linked_structure_aliases(rule,system,aliases)
            aliases.discard('')
            matching=[group for group in groups
                      if group['rule']==rule and aliases and group['aliases'] & aliases]
            if matching:
                group=matching[0]
                group['aliases'].update(aliases)
                for duplicate in matching[1:]:
                    group['aliases'].update(duplicate['aliases'])
                    groups.remove(duplicate)
                if (self.normalize_signal_name(group['name']).startswith('$') and
                        not self.normalize_signal_name(name).startswith('$')):
                    group['name']=name
            else:
                groups.append({'rule':rule,'label':label,'name':name,'aliases':set(aliases)})
        return groups

    def known_pois(self, system):
        """Return unique POIs previously saved for a system, without replaying alerts."""
        return [(group['rule'],group['label'],group['name'])
                for group in self._known_poi_groups(system)]

    def known_poi_overview_text(self, system=None):
        """Return compact, current-system POI intelligence for the Home card."""
        system=system or self.current_system
        if not system:
            return 'Waiting for location'
        pois=self.known_pois(system)
        if not pois:
            return 'No known POIs'
        counts={}
        for _rule,label,_name in pois:
            counts[label]=counts.get(label,0)+1
        categories=[]
        for label,count in counts.items():
            shown=label if count==1 else KNOWN_POI_PLURALS.get(label,label+'s')
            categories.append(f'{count} {shown}')
        total=len(pois)
        return (f'{total} known POI' + ('s' if total!=1 else '') + '\n' +
                ' | '.join(categories))

    def local_body_names(self,system):
        if not system: return []
        return [row[0] for row in self.db.execute('''SELECT DISTINCT body_name FROM exploration_events
            WHERE system_name=? COLLATE NOCASE AND body_name IS NOT NULL AND body_name!=''
            ORDER BY body_name COLLATE NOCASE''',(system,)).fetchall()]

    def save_edsm_cache(self,system,result,error=''):
        fetched=result.get('fetched_at') or datetime.now(timezone.utc).isoformat(timespec='seconds')
        self.db.execute('''INSERT OR REPLACE INTO edsm_cache
            (system_name,fetched_at,status,payload_json,error) VALUES(?,?,?,?,?)''',
            (system,fetched,result.get('status','error'),json.dumps(result,ensure_ascii=False,sort_keys=True),str(error or '')))
        self.db.commit()

    def edsm_cache_entry(self,system,max_age_hours=EDSM_CACHE_HOURS):
        row=self.db.execute('''SELECT fetched_at,status,payload_json,error FROM edsm_cache
            WHERE system_name=? COLLATE NOCASE''',(system,)).fetchone()
        if not row: return None
        try: payload=json.loads(row[2])
        except (ValueError,TypeError): return None
        try:
            fetched=datetime.fromisoformat(row[0].replace('Z','+00:00'))
            if fetched.tzinfo is None: fetched=fetched.replace(tzinfo=timezone.utc)
            stale=datetime.now(timezone.utc)-fetched>timedelta(hours=max_age_hours)
        except (ValueError,TypeError): stale=True
        return {'fetched_at':row[0],'status':row[1],'payload':payload,'error':row[3],'stale':stale}

    def _known_poi_arrival_summary(self,event,system,address,enabled):
        """Build one cached-intelligence popup per confirmed system visit."""
        if event.get('event') not in LOCATION_CONTEXT_EVENTS:
            return None
        context=str(address) if address is not None else self.normalize_signal_name(system)
        new_visit=(event.get('event') in ('FSDJump','CarrierJump','LoadGame') or
                   context != self.known_poi_visit_context)
        if not new_visit:
            return None
        self.known_poi_visit_context=context
        if not enabled or not system:
            return None
        groups=self._known_poi_groups(system)
        if not groups:
            return None
        # The arrival reminder already announces these identities. A later live
        # FSS record remains evidence, but should not interrupt the commander again.
        for group in groups:
            self._remember_structure_popup(group['rule'],group['name'],group['aliases'])
            if group['rule'] in self.arrival_structure_records:
                self.arrival_structure_records[group['rule']].append({
                    'aliases':set(group['aliases']), 'matched':False, 'name':group['name']})
        pois=[(group['rule'],group['label'],group['name']) for group in groups]
        counts={}
        for _rule,label,_name in pois:
            counts[label]=counts.get(label,0)+1
        categories=', '.join(f'{count} {label}' for label,count in counts.items())
        names=[]
        for _rule,label,name in pois:
            display=name if self.normalize_signal_name(name)!=self.normalize_signal_name(label) else label
            if display not in names: names.append(display)
        name_text=', '.join(names[:6])
        if len(names)>6: name_text += f', plus {len(names)-6} more'
        detail=(f'Previously recorded by Discovery Watch: {categories}. '
                f'Known names: {name_text}. Confirm availability in the navigation panel; '
                'this is cached information, not a fresh journal detection.')
        return (f'Known POIs on arrival - {len(pois)} recorded',system,detail)

    def _arrival_discovery_status_finding(self,event,system,address,enabled):
        """Return a cautious finding only for a possibly undiscovered arrival star."""
        kind=event.get('event')
        if kind=='FSDJump':
            self.arrival_discovery_pending={
                'system':system,
                'address':str(address) if address is not None else None,
                'announced':False,
            }
            return None
        pending=self.arrival_discovery_pending
        if not enabled or kind!='Scan' or not pending or pending['announced']:
            return None
        was_discovered=event.get('WasDiscovered')
        if not isinstance(was_discovered,bool):
            return None
        event_address=event.get('SystemAddress')
        if (pending['address'] is not None and event_address is not None and
                str(event_address)!=pending['address']):
            return None
        expected=self.normalize_signal_name(pending.get('system'))
        actual=self.normalize_signal_name(system or event.get('StarSystem'))
        if expected and actual and expected!=actual:
            return None
        body_id=event.get('BodyID')
        body_name=self.normalize_signal_name(event.get('BodyName') or event.get('Body'))
        distance=event.get('DistanceFromArrivalLS')
        arrival_star=bool(event.get('StarType')) and (
            (isinstance(body_id,(int,float)) and not isinstance(body_id,bool) and body_id==0) or
            (expected and body_name==expected) or
            (isinstance(distance,(int,float)) and not isinstance(distance,bool) and distance<=0.1))
        if not arrival_star:
            return None
        pending['announced']=True
        if was_discovered:
            # A positive status resolves the pending check but is ordinary and
            # should not crowd Discovery History.
            return None
        title='Possible undiscovered system'
        detail=('Scan: Arrival star reports WasDiscovered=false. '
                'This is a possible first-discovery opportunity, not proof that every body is undiscovered.')
        return ('SYSTEM_DISCOVERY_STATUS',title,detail)

    @staticmethod
    def is_nonhuman_uss(event):
        return (event.get('event') == 'FSSSignalDiscovered' and
                (str(event.get('USSType') or '').strip().casefold() == '$uss_type_nonhuman;' or
                 str(event.get('USSType_Localised') or '').strip().casefold() == 'nonhuman signal source'))

    @staticmethod
    def is_listening_post(event):
        internal=str(event.get('Type') or event.get('SignalName') or '').strip().casefold()
        localised=str(event.get('Type_Localised') or
                      event.get('SignalName_Localised') or '').strip().casefold()
        return internal.startswith('$listeningpost:') or localised == 'listening post'

    def observe_signal_type(self,event,system):
        display,key=self.signal_type(event)
        if not key: return None
        timestamp=event.get('timestamp') or datetime.now().isoformat(timespec='seconds')
        self.db.execute('''INSERT INTO signal_catalog
            (signal_key,display_name,policy,priority,popup,first_seen,last_seen,events_seen,last_event_type,last_system)
            VALUES(?,?,\'record\',40,0,?,?,1,?,?)
            ON CONFLICT(signal_key) DO UPDATE SET display_name=excluded.display_name,
            last_seen=excluded.last_seen,events_seen=signal_catalog.events_seen+1,
            last_event_type=excluded.last_event_type,last_system=excluded.last_system''',
            (key,display,timestamp,timestamp,event.get('event'),system))
        return self.db.execute('''SELECT signal_key,display_name,policy,priority,popup,
            first_seen,last_seen,events_seen,last_event_type,last_system FROM signal_catalog WHERE signal_key=?''',(key,)).fetchone()

    def signal_catalog(self):
        return self.db.execute('''SELECT signal_key,display_name,policy,priority,popup,
            first_seen,last_seen,events_seen,last_event_type,last_system
            FROM signal_catalog ORDER BY priority DESC,display_name COLLATE NOCASE''').fetchall()

    def set_signal_policy(self,key,policy,priority=None,popup=None):
        if policy not in ('alert','record','ignore'): raise ValueError('Invalid signal policy')
        row=self.db.execute('SELECT priority,popup FROM signal_catalog WHERE signal_key=?',(key,)).fetchone()
        if not row: raise ValueError('Unknown signal type')
        priority=row[0] if priority is None else max(0,min(100,int(priority)))
        popup=row[1] if popup is None else int(bool(popup))
        self.db.execute('UPDATE signal_catalog SET policy=?,priority=?,popup=? WHERE signal_key=?',
                        (policy,priority,popup,key)); self.db.commit()

    @staticmethod
    def normalize_signal_name(value):
        return ' '.join(str(value or '').casefold().split())

    @classmethod
    def generic_signature(cls,localised_name,internal_name):
        payload=['generic',cls.normalize_signal_name(localised_name),cls.normalize_signal_name(internal_name)]
        return hashlib.sha256(json.dumps(payload,separators=(',',':')).encode('utf-8')).hexdigest()

    def observe_generic_signal(self,event,system,notify=False):
        _display,key=self.signal_type(event)
        if key != 'generic': return None
        localised=str(event.get('SignalName_Localised') or '')
        internal=str(event.get('SignalName') or '')
        local_norm=self.normalize_signal_name(localised); internal_norm=self.normalize_signal_name(internal)
        signature=self.generic_signature(localised,internal)
        pattern=local_norm or internal_norm
        timestamp=event.get('timestamp') or datetime.now().isoformat(timespec='seconds')
        cursor=self.db.execute('''INSERT OR IGNORE INTO generic_signal_catalog
            (signature,localised_name,internal_name,normalized_pattern,first_seen,last_seen,
             events_seen,last_event_type,last_system) VALUES(?,?,?,?,?,?,1,?,?)''',
            (signature,localised,internal,pattern,timestamp,timestamp,event.get('event'),system))
        is_new=bool(cursor.rowcount)
        if not is_new:
            self.db.execute('''UPDATE generic_signal_catalog SET localised_name=?,internal_name=?,
                last_seen=?,events_seen=events_seen+1,last_event_type=?,last_system=? WHERE signature=?''',
                (localised,internal,timestamp,event.get('event'),system,signature))
        exact=self.db.execute('''SELECT signature,policy,match_mode,popup_mode,priority,notified
            FROM generic_signal_catalog WHERE signature=?''',(signature,)).fetchone()
        effective=exact
        if exact[1]=='review':
            candidates=self.db.execute('''SELECT signature,policy,match_mode,popup_mode,priority,notified,
                normalized_pattern FROM generic_signal_catalog
                WHERE match_mode='contains' AND policy!='review' AND normalized_pattern!=''
                ORDER BY LENGTH(normalized_pattern) DESC''').fetchall()
            for candidate in candidates:
                if candidate[6] in local_norm or candidate[6] in internal_norm:
                    effective=candidate[:6]
                    break
        notify_enabled=self.generic_notify_once()
        needs_notice=bool(notify and is_new and notify_enabled and effective[1]=='review')
        if needs_notice:
            self.db.execute('UPDATE generic_signal_catalog SET notified=1 WHERE signature=?',(signature,))
        return {'signature':signature,'localised':localised,'internal':internal,
                'policy':effective[1],'popup_mode':effective[3],'priority':effective[4],
                'matched_rule':effective[0],'is_new':is_new,'needs_notice':needs_notice}

    def generic_signals(self):
        return self.db.execute('''SELECT signature,localised_name,internal_name,policy,match_mode,
            popup_mode,priority,events_seen,first_seen,last_seen,last_event_type,last_system,notified,
            normalized_pattern FROM generic_signal_catalog
            ORDER BY CASE policy WHEN 'review' THEN 0 ELSE 1 END,last_seen DESC''').fetchall()

    def set_generic_rule(self,signature,policy,match_mode='exact',popup_mode='once_system',priority=50,pattern=None):
        if policy not in ('alert','record','ignore','review'): raise ValueError('Invalid Generic signal policy')
        if match_mode not in ('exact','contains'): raise ValueError('Invalid match mode')
        if popup_mode not in ('off','once_system','always'): raise ValueError('Invalid popup mode')
        normalized_pattern=self.normalize_signal_name(pattern) if pattern is not None else None
        if match_mode=='contains' and not normalized_pattern:
            raise ValueError('Contains matching requires a pattern')
        if normalized_pattern is None:
            normalized_pattern=self.db.execute('SELECT normalized_pattern FROM generic_signal_catalog WHERE signature=?',(signature,)).fetchone()[0]
        self.db.execute('''UPDATE generic_signal_catalog SET policy=?,match_mode=?,popup_mode=?,priority=?,normalized_pattern=?
            WHERE signature=?''',(policy,match_mode,popup_mode,max(0,min(100,int(priority))),normalized_pattern,signature))
        self.db.commit()

    def generic_notify_once(self,value=None):
        if value is not None:
            self.db.execute("UPDATE preferences SET value=? WHERE key='generic_notify_once'",('1' if value else '0',))
            self.db.commit()
        return self.db.execute("SELECT value FROM preferences WHERE key='generic_notify_once'").fetchone()[0]=='1'

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.execute('UPDATE live_sessions SET ended_at=? WHERE session_id=?',
                        (datetime.now().isoformat(timespec='seconds'),self.session_id))
        self.db.commit()
        self.db.close()

    @staticmethod
    def event_system_name(event):
        return (event.get('StarSystem') or event.get('SystemName') or
                event.get('StarSystemName') or event.get('System'))

    def system_name_for_address(self,address):
        if address is None: return None
        current_system=getattr(self,'current_system',None)
        current_address=getattr(self,'current_system_address',None)
        if current_system and str(address)==str(current_address):
            return current_system
        row=self.db.execute('''SELECT system_name FROM exploration_events
            WHERE system_address=? AND system_name IS NOT NULL ORDER BY rowid DESC LIMIT 1''',(str(address),)).fetchone()
        return row[0] if row else None

    def _repair_stored_alert_systems(self):
        """Correct older alerts when their own SystemAddress identifies another known system."""
        checkpoint=self._maintenance_checkpoint('system_repair_alert_id')
        maximum=self.db.execute('SELECT COALESCE(MAX(id),0) FROM alerts').fetchone()[0]
        for alert_id,raw,stored_system in self.db.execute(
                'SELECT id,raw_json,system_name FROM alerts WHERE id>?',(checkpoint,)).fetchall():
            try: address=json.loads(raw).get('SystemAddress')
            except (ValueError,TypeError,AttributeError): continue
            resolved=self.system_name_for_address(address)
            if resolved and resolved != stored_system:
                self.db.execute('UPDATE alerts SET system_name=? WHERE id=?',(resolved,alert_id))
        self._set_maintenance_checkpoint('system_repair_alert_id',maximum)

    def _backfill_file_system(self,journal_file,system):
        if not system: return
        self.db.execute('''UPDATE alerts SET system_name=?
            WHERE journal_file=? AND (system_name IS NULL OR system_name='')''',(system,str(journal_file)))
        self.db.execute('''UPDATE historical_events SET system_name=?
            WHERE journal_file=? AND (system_name IS NULL OR system_name='')''',(system,str(journal_file)))

    def _latest_system_context(self, file):
        """Recover context without ingesting or alerting on historical events."""
        system = address = None
        try:
            with file.open('r', encoding='utf-8-sig', errors='replace') as stream:
                for line in stream:
                    if not any(key in line for key in ('"StarSystem"','"SystemName"','"StarSystemName"','"SystemAddress"')):
                        continue
                    try: event=json.loads(line)
                    except ValueError: continue
                    if event.get('event') not in LOCATION_CONTEXT_EVENTS:
                        continue
                    explicit=self.event_system_name(event)
                    if explicit: system=explicit
                    if event.get('SystemAddress') is not None: address=event.get('SystemAddress')
        except OSError as exc:
            self.errors.append(f"Cannot recover system context from {file}: {exc}")
        return system,address

    def start_at_end(self):
        """Ignore historical entries; capture new lines only."""
        for file in sorted(self.folder.glob('Journal.*.log')):
            try:
                stat = file.stat()
                self.offsets[str(file)] = stat.st_size
                self.file_ids[str(file)] = (stat.st_dev, stat.st_ino)
                with file.open('rb') as stream:
                    self.lines[str(file)] = sum(chunk.count(b'\n') for chunk in iter(lambda: stream.read(1024 * 1024), b''))
                system,address=self._latest_system_context(file)
                if not system and self.current_system:
                    system=self.current_system
                if address is None and system==self.current_system:
                    address=self.current_system_address
                if system:
                    self.systems[str(file)]=system
                    self.current_system=system
                if address is not None:
                    self.system_addresses[str(file)]=address
                    self.current_system_address=address
            except OSError as exc:
                self.errors.append(f"Cannot initialise {file}: {exc}")

    def poll(self, options=(True, True, True, True, True, False, True, False,
                            True, True, False, False, True, True, False, False, False)):
        found = []
        self.popup_findings = []
        self.popup_metadata = []
        self.arrived_systems = []
        unresolved_enabled=options[4] if len(options)>4 else False
        anomaly_alerts_enabled=options[5] if len(options)>5 else False
        known_pois_enabled=options[6] if len(options)>6 else True
        planetary_mining_popups_enabled=options[7] if len(options)>7 else False
        legacy_other=options[11] if len(options)>11 else False
        surface_popup_choices={
            'thargoid':options[8] if len(options)>8 else True,
            'guardian':options[9] if len(options)>9 else True,
            'biological':options[10] if len(options)>10 else False,
            'other':legacy_other,
            'geological':options[14] if len(options)>14 else legacy_other,
            'human':options[15] if len(options)>15 else legacy_other,
        }
        stratum_popups_enabled=options[12] if len(options)>12 else True
        before_leave_enabled=options[13] if len(options)>13 else True
        arrival_discovery_status_enabled=options[16] if len(options)>16 else False
        if not self.folder.is_dir():
            raise OSError(f'Journal folder unavailable: {self.folder}')
        for file in sorted(self.folder.glob('Journal.*.log')):
            name = str(file)
            try:
                stat = file.stat()
                size = stat.st_size
                identity = (stat.st_dev, stat.st_ino)
                if name in self.file_ids and self.file_ids[name] != identity:
                    self.offsets[name], self.lines[name], self.buffers[name] = 0, 0, b''
                    self.deferred_prearrival.pop(name,None)
                    self.systems.pop(name, None)
                    self.system_addresses.pop(name, None)
                    if self.current_system: self.systems[name]=self.current_system
                    if self.current_system_address is not None: self.system_addresses[name]=self.current_system_address
                self.file_ids[name] = identity
                if name not in self.offsets:
                    self.offsets[name] = 0  # newly created journal: read its opening lines
                    self.lines[name] = 0
                    self.buffers.pop(name, None)
                    if self.current_system: self.systems[name]=self.current_system
                    if self.current_system_address is not None: self.system_addresses[name]=self.current_system_address
                if size < self.offsets[name]:
                    self.offsets[name], self.lines[name], self.buffers[name] = 0, 0, b''
                    self.deferred_prearrival.pop(name,None)
                    self.systems.pop(name, None)
                    self.system_addresses.pop(name, None)
                    if self.current_system: self.systems[name]=self.current_system
                    if self.current_system_address is not None: self.system_addresses[name]=self.current_system_address
                with file.open('rb') as stream:
                    stream.seek(self.offsets[name])
                    data = stream.read()
                    self.offsets[name] = stream.tell()
            except OSError as exc:
                self.errors.append(f"Cannot read {file}: {exc}")
                continue
            data = self.buffers.pop(name, b'') + data
            chunks = data.split(b'\n')
            self.buffers[name] = chunks.pop()
            records=[]
            for chunk in chunks:
                self.lines[name] += 1
                event_line=self.lines[name]
                try:
                    event = json.loads(chunk.decode('utf-8-sig'))
                except (ValueError, UnicodeError) as exc:
                    self.errors.append(f'{file.name} line {event_line}: invalid JSON ({exc})')
                    continue
                if not isinstance(event, dict):
                    self.errors.append(f'{file.name} line {event_line}: JSON event is not an object')
                    continue
                records.append((event_line,event))
            deferred=self.deferred_prearrival.pop(name,None)
            deferred_waits=0
            if deferred:
                deferred_line,deferred_event,deferred_waits=deferred
                records.insert(0,(deferred_line,deferred_event))
            # A location-less FSS signal for another address is occasionally
            # flushed just before its FSDJump. Give the arrival up to two poll
            # cycles to provide StarSystem; do not inherit the departure system.
            if records:
                tail_line,tail_event=records[-1]
                tail_address=tail_event.get('SystemAddress')
                inherited_address=self.system_addresses.get(name)
                tail_signal_type=str(tail_event.get('SignalType') or
                                     tail_event.get('signalType') or '').casefold()
                structure_signal=('megaship' in tail_signal_type or
                                  tail_signal_type.strip()=='installation')
                unresolved_tail=(tail_event.get('event')=='FSSSignalDiscovered' and
                    structure_signal and not self.event_system_name(tail_event) and
                    tail_address is not None and not self.system_name_for_address(tail_address) and
                    (inherited_address is None or str(tail_address)!=str(inherited_address)))
                matching_arrival=any(item.get('event') in ('FSDJump','CarrierJump') and
                    item.get('SystemAddress') is not None and
                    str(item.get('SystemAddress'))==str(tail_address)
                    for _item_line,item in records)
                if unresolved_tail and not matching_arrival and deferred_waits<2:
                    records.pop()
                    self.deferred_prearrival[name]=(tail_line,tail_event,deferred_waits+1)
            for event_line,event in self._arrival_ordered_records(records):
                self.total_events += 1
                self.last_received = datetime.now()
                self.active_file = name
                self.events.append((self.total_events, name, event_line, event))
                event_kind=event.get('event')
                departure_system=self.current_system
                if event_kind in ('FSDJump','CarrierJump') and departure_system:
                    if unresolved_enabled:
                        self._finalize_contact_visit(found)
                    self.abandon_cases(departure_system)
                elif event_kind=='Shutdown' and unresolved_enabled:
                    self._finalize_contact_visit(found)
                top_level_planetary_mining_location=_is_planetary_mining_identity(event)
                suppress_top_level_planetary_mining_popup=(
                    top_level_planetary_mining_location and
                    not planetary_mining_popups_enabled)
                confirms_location=event_kind in LOCATION_CONTEXT_EVENTS
                explicit_system=self.event_system_name(event)
                event_address=event.get('SystemAddress')
                inherited_system=self.systems.get(name)
                inherited_address=self.system_addresses.get(name)
                address=event_address if event_address is not None else inherited_address
                if explicit_system:
                    system=explicit_system
                elif event_address is not None:
                    system=self.system_name_for_address(event_address)
                    same_context=(inherited_address is not None and str(event_address)==str(inherited_address))
                    if not system and same_context:
                        system=inherited_system
                else:
                    system=inherited_system
                # Destination-selection events can refer to another system before
                # the ship jumps. Attribute that event correctly, but only a
                # confirmed location event may advance inherited/current context.
                if confirms_location:
                    if event_address is not None:
                        self.system_addresses[name]=event_address
                        if system: self.systems[name]=system
                        else: self.systems.pop(name,None)
                    elif system:
                        self.systems[name]=system
                        if inherited_system and system!=inherited_system:
                            self.system_addresses.pop(name,None); address=None
                    if system:
                        self.current_system=system
                        self.current_system_address=address
                self._begin_structure_visit(event,system,address)
                arrival_discovery_finding=self._arrival_discovery_status_finding(
                    event,system,address,arrival_discovery_status_enabled)
                previous_visit=self.known_poi_visit_context
                known_summary=self._known_poi_arrival_summary(
                    event,system,address,known_pois_enabled)
                if system and self.known_poi_visit_context!=previous_visit:
                    self.arrived_systems.append(system)
                elif system and event_kind in ('FSDJump','CarrierJump','LoadGame'):
                    self.arrived_systems.append(system)
                if known_summary:
                    self.popup_findings.append(known_summary)
                    self.popup_metadata.append(popup_identity({},known_summary[0],
                                                               'Previously recorded POI','Cached arrival reminder'))
                if confirms_location and system:
                    self._backfill_file_system(name,system)
                    found[:]=[(title,system if old_system=='Unknown system' else old_system,detail)
                              for title,old_system,detail in found]
                    self.popup_findings[:]=[(title,system if old_system=='Unknown system' else old_system,detail)
                                           for title,old_system,detail in self.popup_findings]
                if unresolved_enabled and event_kind=='FSSSignalDiscovered':
                    self._observe_contact_signal(event,system,address,found)
                if unresolved_enabled and event_kind=='FSSDiscoveryScan':
                    self._observe_contact_scan(event,system,address,name,event_line)
                signal_row=self.observe_signal_type(event,system)
                uss_row=None
                if self.is_nonhuman_uss(event):
                    uss_row=self.db.execute('SELECT policy,priority,popup FROM signal_catalog WHERE signal_key=?',
                                            ('nonhumanuss',)).fetchone()
                listening_row=None
                if self.is_listening_post(event):
                    listening_row=self.db.execute('SELECT policy,priority,popup FROM signal_catalog WHERE signal_key=?',
                                                  ('listeningpost',)).fetchone()
                # Listening Posts are sometimes journalled as Generic signals
                # whose identity is carried by SignalName rather than Type.
                # Once recognised, do not also create a Generic review alert.
                generic=None if listening_row else self.observe_generic_signal(event,system,notify=True)
                self._store_historical(event,name,event_line,system)
                body = event.get('BodyName') or event.get('Body')
                summary = str(body or event.get('StarSystem') or event.get('SignalName_Localised') or event.get('SignalName') or '')
                self.db.execute('''INSERT OR IGNORE INTO live_session_events
                    (session_id,sequence_no,timestamp,event_type,system_name,body_name,summary,raw_json)
                    VALUES(?,?,?,?,?,?,?,?)''', (self.session_id,self.total_events,event.get('timestamp'),
                    event.get('event','Unknown'),system,str(body) if body is not None else None,summary,
                    json.dumps(event,ensure_ascii=False,sort_keys=True)))
                self._store_exploration(event, name, event_line, system, address)
                self._update_discovery_cases(event,system,address)
                event_findings=classify(event, *options[:4])
                if arrival_discovery_finding:
                    event_findings.append(arrival_discovery_finding)
                if before_leave_enabled and event_kind=='StartJump' and str(event.get('JumpType') or '').casefold()=='hyperspace':
                    warning_system=inherited_system or self.current_system
                    unfinished=self.active_cases(warning_system)
                    if unfinished:
                        names=', '.join(dict.fromkeys(row[3] for row in unfinished[:4]))
                        event_findings.append(('BEFORE_LEAVING','Unfinished discoveries before departure',
                            f'{len(unfinished)} active investigation(s) in {warning_system or "this system"}: {names}. '
                            'This is a reminder only; the plotted jump has not been changed.'))
                watch_matches=self._watchlist_matches(event)
                watch_popup_by_rule={}
                watch_priority_by_rule={}
                for watch_id,watch_name,pattern,watch_popup,watch_priority in watch_matches:
                    rule=f'WATCHLIST_{watch_id}'
                    event_findings.append((rule,f'Watchlist match: {watch_name}',
                        f"{event_kind}: matched commander watchlist pattern '{pattern}' (priority {watch_priority})."))
                    watch_popup_by_rule[rule]=bool(watch_popup)
                    watch_priority_by_rule[rule]=watch_priority
                surface_findings=surface_signal_findings(event)
                event_findings.extend(item[:3] for item in surface_findings)
                planetary_mining_surface_findings={tuple(item[:3]) for item in surface_findings
                    if _is_planetary_mining_identity({'Type':item[4]})}
                bio_findings=stratum_findings(event)
                if bio_findings and event_kind=='ScanOrganic':
                    bio_key=(self.structure_visit_context or str(address) or system or 'unknown',
                             self.normalize_signal_name(event.get('BodyName') or event.get('Body')),
                             bio_findings[0][0])
                    if bio_key in self.bio_confirmed_this_visit:
                        bio_findings=[]
                    else:
                        self.bio_confirmed_this_visit.add(bio_key)
                event_findings.extend(bio_findings)
                popup_controls={
                    'Planetary Mining Locations':planetary_mining_popups_enabled,
                    'Thargoid surface signals':surface_popup_choices['thargoid'],
                    'Guardian surface signals':surface_popup_choices['guardian'],
                    'Biological surface signals':surface_popup_choices['biological'],
                    'Geological surface signals':surface_popup_choices['geological'],
                    'Human surface signals':surface_popup_choices['human'],
                    'Other surface signals':surface_popup_choices['other'],
                }
                surface_popup_by_rule={item[0]:popup_controls.get(
                    finding_policy(item[0]).popup_control,False) for item in surface_findings}
                anomaly_findings=self.last_anomaly_findings
                # Dedicated surface findings carry the same evidence more clearly;
                # do not create a second broad anomaly popup for the same event.
                alert_anomalies=[item for item in anomaly_findings
                                 if not (surface_findings and item[0] in (
                                     'SURFACE_SIGNALS_RECORDED','SIGNAL_RICH_BODY',
                                     'BIOLOGICAL_SIGNALS','GEOLOGICAL_SIGNALS'))]
                if alert_anomalies:
                    body_name=str(event.get('BodyName') or event.get('Body') or event.get('event') or 'journal event')
                    rules=', '.join(f'{rule} ({score})' for rule,score,_,_ in alert_anomalies)
                    explanations='; '.join(explanation for _,_,explanation,_ in alert_anomalies)
                    event_findings.append(('ANOMALY_ALERT',f'Anomaly review: {body_name}',
                                           f'Rules: {rules}. {explanations}'))
                if uss_row and uss_row[0]=='alert':
                    event_findings.append(('NONHUMAN_USS','Nonhuman signal source detected',
                        f"{event.get('event')}: USSType={event.get('USSType') or ''}; "
                        f"USSType_Localised={event.get('USSType_Localised') or ''} "
                        f"(journal USS classification; priority {uss_row[1]})"))
                if listening_row and listening_row[0]=='alert':
                    event_findings.append(('LISTENING_POST','Listening Post detected',
                        f"{event.get('event')}: SignalName={event.get('SignalName') or event.get('Type') or ''}; "
                        f"SignalName_Localised={event.get('SignalName_Localised') or event.get('Type_Localised') or ''} "
                        f"(journal navigation classification; priority {listening_row[1]})"))
                if generic:
                    if generic['policy'] != 'alert':
                        event_findings=[finding for finding in event_findings if finding[0]!='COMMS_BEACON']
                    elif not any(finding[0]=='COMMS_BEACON' for finding in event_findings):
                        display=generic['localised'] or generic['internal'] or 'Unnamed Generic signal'
                        event_findings.append(('GENERIC_'+generic['signature'][:16].upper(),
                            f'{display} detected',
                            f"{event.get('event')}: Generic signal compound match; policy=alert; "
                            f"priority={generic['priority']}; matched_rule={generic['matched_rule'][:12]}"))
                    if generic['needs_notice'] and not suppress_top_level_planetary_mining_popup:
                        display=generic['localised'] or generic['internal'] or 'Unnamed Generic signal'
                        if not (signal_row and signal_row[0]=='generic' and signal_row[2]=='alert'):
                            event_findings.append(('GENERIC_REVIEW_'+generic['signature'][:16].upper(),
                                f'New Generic signal: {display}',
                                'First observation; review it in Settings > Advanced alert rules > Generic signal names.'))
                if signal_row:
                    signal_key,display,policy,priority,signal_popup=signal_row[:5]
                    if policy != 'alert':
                        event_findings=[finding for finding in event_findings
                                        if finding[0] not in ('MEGASHIP','INSTALLATION')]
                    elif signal_key not in ('megaship','installation','fleetcarrier'):
                        already_named_generic=(signal_key=='generic' and any(
                            rule in ('COMMS_BEACON','LISTENING_POST') or rule.startswith('GENERIC_')
                            for rule,_,_ in event_findings))
                        if not already_named_generic:
                            signal_title=f'{display} signal detected'
                            extra_detail=''
                            if signal_key=='generic':
                                generic_name=str(event.get('SignalName_Localised') or
                                                 event.get('SignalName') or '').strip()
                                generic_name=generic_name or 'Unnamed Generic signal'
                                signal_title=f'{generic_name} (Generic signal)'
                                extra_detail=(f"; SignalName_Localised={event.get('SignalName_Localised') or ''}; "
                                              f"SignalName={event.get('SignalName') or ''}")
                            event_findings.append(('SIGNAL_TYPE_'+signal_key.upper(),signal_title,
                                f"{event.get('event')}: signalType={display} "
                                f"(catalogue policy: alert; priority {priority}){extra_detail}"))
                for rule, title, detail in event_findings:
                    if self._duplicate_structure_alert(rule,event):
                        self.suppressed_duplicates += 1
                        continue
                    raw = json.dumps(event, ensure_ascii=False)
                    priority_hint=None
                    if generic and (rule=='COMMS_BEACON' or rule.startswith('GENERIC_')):
                        priority_hint=generic['priority']
                    elif signal_row and (rule.startswith('SIGNAL_TYPE_') or rule in ('MEGASHIP','INSTALLATION')):
                        priority_hint=signal_row[3]
                    elif rule=='NONHUMAN_USS' and uss_row:
                        priority_hint=uss_row[1]
                    elif rule=='LISTENING_POST' and listening_row:
                        priority_hint=listening_row[1]
                    elif rule in watch_priority_by_rule:
                        priority_hint=watch_priority_by_rule[rule]
                    level=alert_level(rule,priority_hint)
                    finding_system=(warning_system if rule=='BEFORE_LEAVING' else system)
                    cursor = self.db.execute('''INSERT OR IGNORE INTO alerts
                        (journal_file,line_no,rule,title,system_name,timestamp,detail,raw_json,level,origin,popup_decision)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (name,event_line,rule,title,finding_system,event.get('timestamp'),detail,raw,level,
                        'Live journal','Pending notification decision'))
                    if cursor.rowcount:
                        finding=(title, finding_system or 'Unknown system', detail)
                        found.append(finding)
                        suppress_planetary_mining_popup=(
                            not planetary_mining_popups_enabled and
                            (top_level_planetary_mining_location or
                             (rule,title,detail) in planetary_mining_surface_findings))
                        generic_rule=generic and (rule=='COMMS_BEACON' or rule.startswith('GENERIC_'))
                        generic_popup=False
                        if generic_rule:
                            popup_mode=generic['popup_mode']
                            popup_key=(generic['matched_rule'],system or '')
                            generic_popup=popup_mode=='always' or (popup_mode=='once_system' and popup_key not in self.generic_popup_seen)
                            if generic_popup: self.generic_popup_seen.add(popup_key)
                        surface_rule=rule in surface_popup_by_rule
                        bio_rule=rule in ('BIO_STRATUM_LEAD','BIO_STRATUM_TECTONICAS')
                        anomaly_rule=rule=='ANOMALY_ALERT'
                        discovery_status_rule=rule=='SYSTEM_DISCOVERY_STATUS'
                        discovery_status_popup=(discovery_status_rule and
                                                'WasDiscovered=false' in detail)
                        watch_rule=rule in watch_popup_by_rule
                        signal_catalog_rule=(rule.startswith('SIGNAL_TYPE_') or
                                             rule in ('MEGASHIP','INSTALLATION'))
                        signal_review_popup=bool(signal_catalog_rule and signal_row and
                            signal_row[0]=='generic' and generic and generic['needs_notice'])
                        special_popup=(rule=='NONHUMAN_USS' and bool(uss_row[2])) or \
                                      (rule=='LISTENING_POST' and bool(listening_row[2]))
                        special_rule=rule in ('NONHUMAN_USS','LISTENING_POST')
                        popup_allowed=(generic_popup or special_popup or discovery_status_popup or
                                       (surface_rule and surface_popup_by_rule[rule]) or
                                       (bio_rule and stratum_popups_enabled) or
                                       (anomaly_rule and anomaly_alerts_enabled) or
                                       (watch_rule and watch_popup_by_rule[rule]) or
                                       signal_review_popup or
                                       (not generic_rule and not special_rule and not discovery_status_rule and
                                        not surface_rule and not bio_rule and not anomaly_rule and not watch_rule and
                                        (not signal_catalog_rule or not signal_row or bool(signal_row[4]))))
                        will_popup=popup_allowed and not suppress_planetary_mining_popup
                        surface_confirmation_suppressed=False
                        arrival_structure_suppressed=False
                        if rule in ('MEGASHIP','INSTALLATION') and will_popup:
                            if self._duplicate_structure_popup(rule,event):
                                will_popup=False
                                arrival_structure_suppressed=True
                                self.suppressed_duplicates += 1
                        if surface_rule and will_popup:
                            surface_key=(self.structure_visit_context or str(address) or system or 'unknown',
                                         self.normalize_signal_name(event.get('BodyName') or event.get('Body')),
                                         rule)
                            if event_kind=='SAASignalsFound' and surface_key in self.surface_alerted_this_visit:
                                will_popup=False
                                surface_confirmation_suppressed=True
                            else:
                                self.surface_alerted_this_visit.add(surface_key)
                        if will_popup:
                            self.popup_findings.append(finding)
                            self.popup_metadata.append(popup_identity(event,title,rule))
                        if suppress_planetary_mining_popup:
                            popup_decision='Suppressed: Planetary Mining Location popups are disabled'
                        elif will_popup:
                            popup_decision='Popup eligible under the matching rule; the interface master popup switch is applied separately'
                        elif arrival_structure_suppressed:
                            popup_decision=('Saved without popup because this structure was already '
                                            'announced by Known POIs on arrival during the current system visit')
                        elif generic_rule:
                            popup_decision='Saved without popup by the matching Generic rule'
                        elif special_rule:
                            popup_decision='Saved without popup because this category popup is disabled'
                        elif surface_rule:
                            popup_decision=('Saved as DSS confirmation; the matching FSS body-signal alert was already shown this visit'
                                            if surface_confirmation_suppressed else
                                            'Saved without popup because this surface-signal category popup is disabled')
                        elif bio_rule:
                            popup_decision='Saved without popup because Stratum popups are disabled'
                        elif anomaly_rule:
                            popup_decision='Saved to unified history without popup because anomaly popups are disabled'
                        elif discovery_status_rule:
                            popup_decision=('Popup eligible for a possible first-discovery opportunity; '
                                            'the interface master popup switch is applied separately'
                                            if discovery_status_popup else
                                            'Saved without popup because the arrival star was previously discovered')
                        elif watch_rule:
                            popup_decision='Saved without popup because this Commander Watchlist popup is disabled'
                        elif signal_catalog_rule and signal_row and not bool(signal_row[4]):
                            popup_decision='Saved without popup because the signal-type popup is disabled'
                        else:
                            popup_decision='Saved without popup by current notification settings'
                        self.db.execute('UPDATE alerts SET popup_decision=? WHERE id=?',
                                        (popup_decision,cursor.lastrowid))
            self.db.commit()
        if unresolved_enabled:
            self._emit_due_contact_findings(found)
            self.db.commit()
        return found

    def import_journals(self, source, progress=None):
        source = Path(source)
        files = sorted(source.glob('Journal.*.log'))
        valid = added = duplicates = errors = historical_added = 0
        tracked = ('FSDJump','Location','CarrierJump','Scan','SAAScanComplete','ScanOrganic',
                   'FSSDiscoveryScan','FSSAllBodiesFound','FSSBodySignals','SAASignalsFound',
                   'CodexEntry')
        for file_index, file in enumerate(files, 1):
            system = address = None
            try:
                with file.open('r', encoding='utf-8-sig', errors='strict') as stream:
                    for line_no, line in enumerate(stream, 1):
                        if not line.strip(): continue
                        try:
                            event = json.loads(line)
                            if not isinstance(event, dict): raise ValueError('not an object')
                        except (ValueError, UnicodeError):
                            errors += 1; continue
                        valid += 1
                        if event.get('event') in ('FSDJump', 'Location', 'CarrierJump'):
                            system = self.event_system_name(event) or system
                            address = event.get('SystemAddress') or address
                        event_system = self.event_system_name(event) or system
                        event_address = event.get('SystemAddress') or address
                        self.observe_signal_type(event,event_system)
                        self.observe_generic_signal(event,event_system,notify=False)
                        if self._store_historical(event,file,line_no,event_system): historical_added += 1
                        if self._store_exploration(event, file, line_no, event_system, event_address): added += 1
                        elif event.get('event') in tracked: duplicates += 1
            except OSError: errors += 1
            if progress: progress(file_index, len(files), file.name)
        self.db.execute('''INSERT INTO import_history
            (source_folder,files_seen,valid_events,exploration_added,duplicates,errors)
            VALUES(?,?,?,?,?,?)''', (str(source),len(files),valid,added,duplicates,errors))
        self.db.commit()
        return {'files':len(files),'valid_events':valid,'added':added,'historical_added':historical_added,
                'duplicates':duplicates,'errors':errors}

    def search_exploration(self, query='', incomplete_only=False, limit=1000):
        params = []
        where = 'WHERE system_name IS NOT NULL'
        if query.strip():
            where += ' AND (system_name LIKE ? OR body_name LIKE ? OR event_type LIKE ?)'
            pattern = '%' + query.strip() + '%'; params.extend((pattern,pattern,pattern))
        if incomplete_only:
            where += " AND system_name IN (SELECT system_name FROM exploration_events GROUP BY system_name HAVING SUM(event_type='FSSDiscoveryScan')>0 AND SUM(event_type='FSSAllBodiesFound')=0)"
        params.append(limit)
        return self.db.execute('''SELECT system_name, COUNT(DISTINCT CASE WHEN fact_type='scan' THEN body_name END),
            COUNT(DISTINCT CASE WHEN fact_type='mapping' THEN body_name END),
            SUM(CASE WHEN fact_type LIKE 'organic_%' THEN 1 ELSE 0 END), COUNT(*),
            CASE WHEN SUM(event_type='FSSAllBodiesFound')>0 THEN 'Complete'
                 WHEN SUM(event_type='FSSDiscoveryScan')>0 THEN 'Incomplete' ELSE 'Unknown' END
            FROM exploration_events ''' + where + ''' GROUP BY system_name
            ORDER BY MAX(rowid) DESC LIMIT ?''', params).fetchall()

    def integrity_check(self):
        result = self.db.execute('PRAGMA integrity_check').fetchone()[0]
        orphaned = self.db.execute("SELECT COUNT(*) FROM exploration_events WHERE event_type IS NULL OR raw_json IS NULL").fetchone()[0]
        invalid_json = 0
        for (raw,) in self.db.execute('SELECT raw_json FROM exploration_events UNION ALL SELECT raw_json FROM historical_events'):
            try: json.loads(raw)
            except (ValueError, TypeError): invalid_json += 1
        return {'sqlite':result,'orphaned':orphaned,'invalid_json':invalid_json,
                'events':self.db.execute('SELECT COUNT(*) FROM exploration_events').fetchone()[0],
                'historical_events':self.db.execute('SELECT COUNT(*) FROM historical_events').fetchone()[0]}

    def diagnostic_report(self):
        """Return support information without including raw journal events."""
        tables=('alerts','exploration_events','historical_events','anomalies','live_sessions',
                'signal_catalog','generic_signal_catalog','discovery_case_evidence','discovery_cases','commander_watchlists',
                'notification_deliveries','edsm_cache','structure_identity_links','schema_migrations',
                'contact_reconciliations')
        counts={table:self.db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in tables}
        preferences=dict(self.db.execute('SELECT key,value FROM preferences ORDER BY key').fetchall())
        monitor_label={stored:label for label,stored in POPUP_MONITOR_VALUES.items()}.get(
            preferences.get('popup_monitor','primary'),'Main monitor')
        popup_info=popup_diagnostics(
            monitor_choice=monitor_label,
            auto_close=preferences.get('popup_auto_close','1')=='1',
            timeout=int(preferences.get('popup_timeout_seconds','15')) if preferences.get('popup_timeout_seconds','15').isdigit() else 15,
            keep_above=preferences.get('popup_above_game','1')=='1',
            sound=preferences.get('popup_sound','1')=='1',
            windows_mode=(WINDOWS_NOTIFICATION_MODES[1]
                          if preferences.get('windows_notification_mode','overlay') in ('overlay','custom')
                          else WINDOWS_NOTIFICATION_MODES[0]))
        popup_info['position']=preferences.get('popup_position','Bottom right')
        popup_info['text_size']=preferences.get('popup_font_size','Normal')
        decision_counts=dict(self.db.execute('''SELECT COALESCE(popup_decision,'Legacy / unknown'),COUNT(*)
            FROM alerts GROUP BY COALESCE(popup_decision,'Legacy / unknown') ORDER BY COUNT(*) DESC''').fetchall())
        journals=[]
        if self.folder.is_dir():
            for file in sorted(self.folder.glob('Journal.*.log'))[-20:]:
                try:
                    stat=file.stat()
                    journals.append({'name':file.name,'size_bytes':stat.st_size,
                                     'modified_utc':datetime.fromtimestamp(stat.st_mtime,timezone.utc).isoformat()})
                except OSError as exc:
                    journals.append({'name':file.name,'error':str(exc)})
        return {
            'application':{'name':'Discovery Watch','version':APP_VERSION},
            'runtime':{'python':platform.python_version(),'platform':platform.platform(),
                       'tk':str(tk.TkVersion)},
            'monitor':{'running_session_events':self.total_events,
                       'current_system':self.current_system,
                       'active_journal':Path(self.active_file).name if self.active_file else None,
                       'recent_errors':list(self.errors)[-20:]},
            'database':{'integrity':self.integrity_check(),'row_counts':counts,
                        'schema_version':self.schema_version(),
                        'expected_schema_version':SCHEMA_VERSION},
            'popup_diagnostics':popup_info,
            'notification_delivery':notification_delivery_summary(connection=self.db),
            'notification_decisions':decision_counts,
            'settings':preferences,
            'journal_folder':str(self.folder),
            'journal_files':journals,
            'privacy_note':'Contains local paths and settings, but no raw journal event contents.'}

    def backup_database(self, destination):
        target = sqlite3.connect(str(destination))
        try: self.db.backup(target)
        finally: target.close()
        return Path(destination)

    def anomalies(self, query='', status='all', limit=1000):
        where=[]; params=[]
        if query.strip():
            where.append('(system_name LIKE ? OR body_name LIKE ? OR rule LIKE ? OR explanation LIKE ?)')
            pattern='%'+query.strip()+'%'; params.extend((pattern,pattern,pattern,pattern))
        if status != 'all': where.append('status=?'); params.append(status)
        sql='''SELECT id,score,rule,COALESCE(system_name,''),COALESCE(body_name,''),
            COALESCE(timestamp,''),explanation,evidence_field,status,raw_json
            FROM anomalies'''
        if where: sql += ' WHERE ' + ' AND '.join(where)
        sql += ' ORDER BY score DESC,id DESC LIMIT ?'; params.append(limit)
        return self.db.execute(sql,params).fetchall()

    def set_anomaly_status(self, anomaly_id, status):
        if status not in ('new','reviewed','dismissed'): raise ValueError('Invalid anomaly status')
        self.db.execute('UPDATE anomalies SET status=? WHERE id=?',(status,anomaly_id)); self.db.commit()

    def live_summary(self, system=None):
        system = system or self.current_system
        if not system:
            return {'system':None,'scans':0,'maps':0,'signals':0,'complete':'Unknown','anomalies':0,
                    'findings':0,'unresolved':0,'visit':self.current_visit_intelligence(),
                    'suggestions':['Wait for a Location or FSDJump event.']}
        row=self.db.execute('''SELECT COUNT(DISTINCT CASE WHEN fact_type='scan' THEN body_name END),
            COUNT(DISTINCT CASE WHEN fact_type='mapping' THEN body_name END),
            SUM(event_type IN ('FSSBodySignals','SAASignalsFound')),
            SUM(event_type='FSSDiscoveryScan'), SUM(event_type='FSSAllBodiesFound')
            FROM exploration_events WHERE system_name=?''',(system,)).fetchone()
        scans,maps,signals,fss,all_found=[int(value or 0) for value in row]
        anomaly_count=self.db.execute("SELECT COUNT(*) FROM anomalies WHERE system_name=? AND status!='dismissed'",(system,)).fetchone()[0]
        finding_count=self.db.execute("SELECT COUNT(*) FROM alerts WHERE system_name=? AND status!='dismissed'",(system,)).fetchone()[0]
        suggestions=[]
        if fss and not all_found: suggestions.append('Complete the FSS scan; not all bodies are confirmed found.')
        if scans > maps: suggestions.append(f'{scans-maps} scanned body/bodies have no recorded mapping event.')
        if signals: suggestions.append('Review bodies with surface signals for worthwhile follow-up.')
        if anomaly_count: suggestions.append(f'Review {anomaly_count} anomaly lead(s) recorded in this system.')
        if not suggestions: suggestions.append('No specific follow-up is supported by the current journal evidence.')
        return {'system':system,'scans':scans,'maps':maps,'signals':signals,
                'complete':'Complete' if all_found else ('Incomplete' if fss else 'Unknown'),
                'anomalies':anomaly_count,'findings':finding_count,
                'unresolved':self.current_unresolved,'visit':self.current_visit_intelligence(),
                'suggestions':suggestions}

    def live_timeline(self, limit=300):
        return self.db.execute('''SELECT timestamp,event_type,COALESCE(system_name,''),
            COALESCE(body_name,''),summary,raw_json FROM live_session_events
            WHERE session_id=? ORDER BY id DESC LIMIT ?''',(self.session_id,limit)).fetchall()

    def historical_search(self,query='',event_type='',date_from='',date_to='',limit=2000):
        where=[]; params=[]
        if query.strip():
            where.append('(system_name LIKE ? OR body_name LIKE ? OR journal_file LIKE ? OR raw_json LIKE ?)')
            pattern='%'+query.strip()+'%'; params.extend((pattern,pattern,pattern,pattern))
        if event_type.strip(): where.append('event_type LIKE ?'); params.append('%'+event_type.strip()+'%')
        if date_from.strip(): where.append('timestamp>=?'); params.append(date_from.strip())
        if date_to.strip(): where.append('timestamp<=?'); params.append(date_to.strip()+'T23:59:59Z' if len(date_to.strip())==10 else date_to.strip())
        sql='''SELECT timestamp,event_type,COALESCE(system_name,''),COALESCE(body_name,''),
            source_session,line_no,raw_json FROM historical_events'''
        if where: sql += ' WHERE '+' AND '.join(where)
        sql += ' ORDER BY timestamp DESC,rowid DESC LIMIT ?'; params.append(limit)
        return self.db.execute(sql,params).fetchall()

    def historical_sessions(self):
        return self.db.execute('''SELECT source_session,COUNT(*),MIN(timestamp),MAX(timestamp),
            COUNT(DISTINCT system_name) FROM historical_events GROUP BY source_session
            ORDER BY MAX(COALESCE(timestamp,imported_at)) DESC''').fetchall()

    def import_reports(self,limit=100):
        return self.db.execute('''SELECT imported_at,source_folder,files_seen,valid_events,
            exploration_added,duplicates,errors FROM import_history ORDER BY id DESC LIMIT ?''',(limit,)).fetchall()


    def systems_summary(self):
        return [row[:5] for row in self.search_exploration()]

    def system_details(self, system):
        return self.db.execute('''SELECT timestamp,event_type,COALESCE(body_name,''),
            COALESCE(fact_type,''),raw_json,journal_file,line_no FROM exploration_events
            WHERE system_name=? ORDER BY rowid DESC LIMIT 500''', (system,)).fetchall()

    def export_exploration(self, destination, format='json'):
        if format not in ('json', 'csv'):
            raise ValueError('Unsupported export format')
        columns = ('timestamp','system_name','system_address','event_type','body_name',
                   'fact_type','journal_file','line_no','raw_json')
        rows = self.db.execute('SELECT ' + ','.join(columns) +
                               ' FROM exploration_events ORDER BY rowid').fetchall()
        with Path(destination).open('w', encoding='utf-8', newline='') as out:
            if format == 'json':
                json.dump([dict(zip(columns,row)) for row in rows],out,indent=2,ensure_ascii=False)
            else:
                writer = csv.writer(out); writer.writerow(columns); writer.writerows(rows)
        return len(rows)

    def export(self, destination, format='csv'):
        """Export all stored evidence, preserving the original JSON and provenance."""
        if format not in ('csv', 'json'):
            raise ValueError('Export format must be csv or json')
        columns = ('id', 'timestamp', 'system_name', 'rule', 'title', 'detail',
                   'journal_file', 'line_no', 'raw_json', 'created_at','level','origin','popup_decision')
        rows = self.db.execute('SELECT ' + ','.join(columns) + ' FROM alerts ORDER BY id').fetchall()
        destination = Path(destination)
        if format == 'csv':
            with destination.open('w', encoding='utf-8', newline='') as output:
                writer = csv.writer(output)
                writer.writerow(columns)
                writer.writerows(rows)
        else:
            with destination.open('w', encoding='utf-8') as output:
                json.dump([dict(zip(columns, row)) for row in rows], output,
                          ensure_ascii=False, indent=2)
        return len(rows)

    def export_selected_alerts(self, alert_ids, destination, format='json'):
        if format not in ('csv','json'): raise ValueError('Export format must be csv or json')
        ids=[int(value) for value in alert_ids]
        if not ids: return 0
        columns=('id','timestamp','system_name','rule','title','detail','journal_file','line_no','raw_json','status','notes','level','origin','popup_decision')
        placeholders=','.join('?' for _ in ids)
        rows=self.db.execute('SELECT '+','.join(columns)+' FROM alerts WHERE id IN ('+placeholders+') ORDER BY id',ids).fetchall()
        with Path(destination).open('w',encoding='utf-8',newline='') as output:
            if format=='json': json.dump([dict(zip(columns,row)) for row in rows],output,ensure_ascii=False,indent=2)
            else:
                writer=csv.writer(output); writer.writerow(columns); writer.writerows(rows)
        return len(rows)

    def update_alert(self,alert_id,status=None,notes=None):
        if status is not None:
            if status not in ('new','acknowledged','dismissed'): raise ValueError('Invalid alert status')
            self.db.execute('UPDATE alerts SET status=? WHERE id=?',(status,alert_id))
        if notes is not None: self.db.execute('UPDATE alerts SET notes=? WHERE id=?',(str(notes),alert_id))
        self.db.commit()

    def recent(self, limit=200):
        return self.db.execute('''SELECT id, timestamp, system_name, title, detail, raw_json,
            journal_file, line_no,status,notes,level,origin,popup_decision,rule
            FROM alerts ORDER BY id DESC LIMIT ?''', (limit,)).fetchall()

    def active_alert_count(self):
        """Count every non-dismissed finding, independent of display limits."""
        return self.db.execute("SELECT COUNT(*) FROM alerts WHERE status!='dismissed'").fetchone()[0]






class AlertPopup(tk.Toplevel):
    """Styled non-modal discovery panel with a hover-paused countdown."""
    BG=THEME['surface']; PANEL=THEME['panel']; PANEL_ALT=THEME['panel_alt']; ORANGE=THEME['orange']
    TEXT=THEME['text']; MUTED=THEME['muted']; CYAN=THEME['cyan']; REVIEW=THEME['review']
    SCROLLABLE=True
    NON_FOCUSING=True
    WINDOWS_NO_ACTIVATE_BEFORE_MAP=True
    WINDOWS_TK_TOPMOST=False
    WINDOWS_TOPMOST_REINFORCEMENT_MS=500
    LINUX_WINDOW_MODE='splash_with_normal_fallback'

    def __init__(self,parent,findings,timeout=15,auto_close=True,on_open_history=None,
                 keep_above=True,play_sound=True,monitor_choice='Main monitor',metadata=None,
                 position='Bottom right',font_size='Normal'):
        super().__init__(parent)
        # Configure the window before its first map. Mapping a normal Toplevel
        # immediately can cause Linux window managers to take focus from Elite.
        self.withdraw()
        self.title('Discovery Watch - new finding')
        self.configure(background=self.BG,takefocus=False)
        self.resizable(False,False)
        self.remaining=int(timeout); self.initial_timeout=max(1,int(timeout))
        self.auto_close=bool(auto_close); self.on_open_history=on_open_history
        self.keep_above=bool(keep_above)
        self.play_sound=bool(play_sound)
        self.monitor_choice=POPUP_MONITOR_VALUES.get(monitor_choice,'primary')
        self.position=position
        self.font_scale=POPUP_FONT_SCALES.get(font_size,1.0)
        self.metadata=list(metadata or [])
        self.compact_summary=bool(findings and self.metadata and
                                  all(item.get('compact_summary') for item in self.metadata))
        if platform.system()=='Linux':
            # Splash windows are managed and visible on X11/XWayland without
            # asking for keyboard focus. Some compositors suppress notification
            # and override-redirect windows, so neither is used here.
            try:
                self.attributes('-type','splash')
            except tk.TclError: pass
        # A transient child can be hidden with its minimized parent on both Windows
        # and Linux. Always-on-top alerts must remain independent of the main window.
        if not self.keep_above and platform.system()!='Windows':
            self.transient(parent)
        self.countdown=tk.StringVar(); self._timer=None
        self.protocol('WM_DELETE_WINDOW',self.close_now)
        self.bind('<Escape>',lambda _event:self.close_now())

        body=tk.Frame(self,bg=self.BG,padx=18,pady=16); body.pack(fill='both',expand=True)
        header=tk.Frame(body,bg=self.BG); header.pack(fill='x')
        icon=tk.Canvas(header,width=54,height=54,bg=self.BG,highlightthickness=0)
        icon.pack(side='left',padx=(0,12))
        icon.create_oval(5,5,49,49,outline=self.ORANGE,width=2)
        icon.create_oval(15,15,39,39,outline=self.ORANGE,width=1)
        icon.create_line(27,1,27,53,fill=self.ORANGE)
        icon.create_line(1,27,53,27,fill=self.ORANGE)
        icon.create_oval(23,23,31,31,fill=self.ORANGE,outline='')
        heading=tk.Frame(header,bg=self.BG); heading.pack(side='left',fill='x',expand=True)
        tk.Label(heading,text='DISCOVERY WATCH',bg=self.BG,fg=self.ORANGE,
                 font=('TkDefaultFont',max(8,round(9*self.font_scale)),'bold')).pack(anchor='w')
        count_text='DISCOVERIES DETECTED' if self.compact_summary else \
                   ('DISCOVERY UPDATE' if len(findings)==1 else f'{len(findings)} DISCOVERY UPDATES')
        tk.Label(heading,text=count_text,bg=self.BG,fg=self.TEXT,
                 font=('TkDefaultFont',max(11,round(16*self.font_scale)),'bold')).pack(anchor='w',pady=(2,0))

        cards_view=tk.Frame(body,bg=self.BG)
        cards_view.pack(fill='both',expand=True,pady=(14,8))
        self.cards_canvas=tk.Canvas(cards_view,bg=self.BG,highlightthickness=0,
                                    borderwidth=0,width=550)
        cards_scroll=ttk.Scrollbar(cards_view,orient='vertical',command=self.cards_canvas.yview)
        self.cards_canvas.configure(yscrollcommand=cards_scroll.set)
        cards_scroll.pack(side='right',fill='y')
        self.cards_canvas.pack(side='left',fill='both',expand=True)
        cards=tk.Frame(self.cards_canvas,bg=self.BG)
        self.cards_window=self.cards_canvas.create_window((0,0),window=cards,anchor='nw')
        cards.bind('<Configure>',self._update_cards_scrollregion)
        self.cards_canvas.bind('<Configure>',self._resize_cards_width)
        self.bind('<MouseWheel>',self._scroll_cards)
        self.bind('<Button-4>',self._scroll_cards)
        self.bind('<Button-5>',self._scroll_cards)
        self.bind('<Prior>',lambda event:self._scroll_cards_page(event,-1))
        self.bind('<Next>',lambda event:self._scroll_cards_page(event,1))
        self.bind('<Up>',lambda event:self._scroll_cards_units(event,-1))
        self.bind('<Down>',lambda event:self._scroll_cards_units(event,1))
        for index,(title,system,detail) in enumerate(findings):
            identity=self.metadata[index] if index<len(self.metadata) else popup_identity({},title)
            card=tk.Frame(cards,bg=self.PANEL,highlightthickness=1,highlightbackground=THEME['border'])
            card.pack(fill='x',padx=(0,5),pady=4)
            tk.Frame(card,bg=self.ORANGE,width=5).pack(side='left',fill='y')
            content=tk.Frame(card,bg=self.PANEL,padx=12,pady=9); content.pack(side='left',fill='both',expand=True)
            top=tk.Frame(content,bg=self.PANEL); top.pack(fill='x')
            if not self.compact_summary:
                tk.Label(top,text=popup_attention_label(title),bg=self.PANEL,
                         fg=self.REVIEW if popup_attention_label(title)=='REVIEW' else self.ORANGE,
                         font=('TkDefaultFont',8,'bold')).pack(side='right')
            tk.Label(top,text=identity.get('name') or title,bg=self.PANEL,fg=self.TEXT,
                     font=('TkDefaultFont',max(9,round(11*self.font_scale)),'bold')).pack(side='left',anchor='w')
            tk.Label(content,text=f'SYSTEM  {system or "Unknown system"}',bg=self.PANEL,fg=self.CYAN,
                     font=('TkDefaultFont',max(8,round(9*self.font_scale)),'bold')).pack(anchor='w',pady=(4,2))
            if self.compact_summary and identity.get('key_fact'):
                tk.Label(content,text=identity['key_fact'],bg=self.PANEL,fg=self.MUTED,
                         justify='left',anchor='w',wraplength=480,
                         font=('TkDefaultFont',9)).pack(fill='x',pady=(2,0))
            if not self.compact_summary:
                identity_line=f"TYPE  {identity.get('signal_type') or 'Discovery'}   |   EVENT  {identity.get('event') or 'Unknown'}"
                tk.Label(content,text=identity_line,bg=self.PANEL,fg=self.MUTED,
                         justify='left',anchor='w',wraplength=480,font=('TkDefaultFont',9)).pack(fill='x')
                if identity.get('show_detail') and detail:
                    tk.Label(content,text=detail,bg=self.PANEL,fg=self.MUTED,
                             justify='left',anchor='w',wraplength=480,
                             font=('TkDefaultFont',9)).pack(fill='x',pady=(5,0))
        if self.compact_summary:
            tk.Label(body,text='Check Discovery History for more information.',bg=self.BG,fg=self.MUTED,
                     font=('TkDefaultFont',9)).pack(anchor='w',pady=(0,6))

        progress_bg=tk.Frame(body,bg=THEME['trough'],height=5); progress_bg.pack(fill='x',pady=(8,5))
        progress_bg.pack_propagate(False)
        self.progress=tk.Frame(progress_bg,bg=self.ORANGE)
        self.progress.place(relx=0,rely=0,relheight=1,relwidth=1)
        footer=tk.Frame(body,bg=self.BG); footer.pack(fill='x')
        tk.Label(footer,textvariable=self.countdown,bg=self.BG,fg=self.MUTED,
                 font=('TkDefaultFont',9)).pack(side='left')
        tk.Button(footer,text='Close',command=self.close_now,bg=self.PANEL_ALT,fg=self.TEXT,
                  activebackground=THEME['border'],activeforeground=self.TEXT,relief='flat',padx=12,pady=6).pack(side='right')
        self.keep_button=tk.Button(footer,text='Keep open',command=self.keep_open,bg=self.PANEL_ALT,fg=self.TEXT,
                                   activebackground=THEME['border'],activeforeground=self.TEXT,relief='flat',padx=12,pady=6)
        self.keep_button.pack(side='right',padx=7)
        tk.Button(footer,text='Open history',command=self.open_history,bg=self.ORANGE,fg=THEME['selection_text'],
                  activebackground=THEME['orange_hover'],activeforeground=THEME['selection_text'],relief='flat',
                  font=('TkDefaultFont',9,'bold'),padx=14,pady=6).pack(side='right')

        height=min(620,230+min(len(findings),3)*105)
        self.geometry(f'600x{height}')
        self.after_idle(self._present)
        if self.auto_close:
            self._update_countdown(); self._timer=self.after(1000,self._tick)
        else:
            self.countdown.set('Stays open until closed'); self.keep_button.configure(state='disabled')
            self.progress.place_configure(relwidth=1)

    def _update_cards_scrollregion(self,_event=None):
        self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox('all'))

    def _resize_cards_width(self,event):
        self.cards_canvas.itemconfigure(self.cards_window,width=event.width)

    def _scroll_cards(self,event):
        if getattr(event,'num',None)==4:
            direction=-1
        elif getattr(event,'num',None)==5:
            direction=1
        else:
            delta=getattr(event,'delta',0)
            direction=-1 if delta>0 else 1 if delta<0 else 0
        if direction:
            self.cards_canvas.yview_scroll(direction,'units')
        return 'break'

    def _scroll_cards_page(self,_event,direction):
        self.cards_canvas.yview_scroll(direction,'pages')
        return 'break'

    def _scroll_cards_units(self,_event,direction):
        self.cards_canvas.yview_scroll(direction,'units')
        return 'break'

    def _present(self):
        try:
            self.update_idletasks()
            left,top,right,bottom=popup_work_area(self.master,self.monitor_choice)
            x,y=popup_position((left,top,right,bottom),self.winfo_width(),self.winfo_height(),
                               choice=self.position)
            self.geometry(f'{x:+d}{y:+d}')
            if platform.system()=='Windows':
                # Tk must map its content as well as the Win32 wrapper. Both native
                # handles already carry WS_EX_NOACTIVATE, and this window is never
                # transient to the main app, so deiconify cannot legitimately
                # activate either Discovery Watch window.
                prepare_windows_popup(self)
                self.deiconify()
                show_windows_popup(self,self.monitor_choice)
                if self.keep_above:
                    self.after(self.WINDOWS_TOPMOST_REINFORCEMENT_MS,
                               self._windows_keep_above)
            else:
                self.deiconify(); self.lift()
                self.attributes('-topmost',True)
            if self.play_sound:
                play_alert_sound(self)
            # Some desktop compositors apply the stacking hint one event cycle late.
            self.after(150,self._reinforce_visibility)
            self.after(400,self._ensure_visible)
            if not self.keep_above:
                self.after(300,self._release_topmost)
        except tk.TclError:
            pass

    def _reinforce_visibility(self):
        try:
            if not self.winfo_exists(): return
            if platform.system()=='Windows':
                reinforce_windows_popup(self)
            else:
                self.deiconify(); self.lift()
                if self.keep_above:
                    self.attributes('-topmost',True)
        except tk.TclError:
            pass

    def _windows_keep_above(self):
        """Reassert topmost without activation while a borderless game is open."""
        try:
            if platform.system()!='Windows' or not self.keep_above or not self.winfo_exists():
                return
            reinforce_windows_popup(self)
            self.after(self.WINDOWS_TOPMOST_REINFORCEMENT_MS,self._windows_keep_above)
        except tk.TclError:
            pass

    def _ensure_visible(self):
        """Fall back to a normal topmost window when a compositor suppresses splash."""
        try:
            if not self.winfo_exists() or self.winfo_viewable(): return
            if platform.system()=='Windows':
                reinforce_windows_popup(self)
                return
            if platform.system()=='Linux':
                self.withdraw()
                try: self.attributes('-type','normal')
                except tk.TclError: pass
            self.deiconify(); self.lift(); self.attributes('-topmost',True)
        except tk.TclError:
            pass

    def _release_topmost(self):
        try:
            if self.winfo_exists(): self.attributes('-topmost',False)
        except tk.TclError:
            pass

    def _pointer_is_inside(self):
        try:
            widget=self.winfo_containing(self.winfo_pointerx(),self.winfo_pointery())
            return bool(widget and widget.winfo_toplevel()==self)
        except tk.TclError:
            return False

    def _update_countdown(self):
        paused=' - paused while pointer is over this window' if self._pointer_is_inside() else ''
        self.countdown.set(f'Closing in {self.remaining} second' + ('s' if self.remaining!=1 else '') + paused)
        self.progress.place_configure(relwidth=max(0,min(1,self.remaining/self.initial_timeout)))

    def _tick(self):
        if not self.winfo_exists() or not self.auto_close: return
        if not self._pointer_is_inside(): self.remaining-=1
        if self.remaining<=0:
            self.close_now(); return
        self._update_countdown(); self._timer=self.after(1000,self._tick)

    def keep_open(self):
        self.auto_close=False
        if self._timer:
            self.after_cancel(self._timer); self._timer=None
        self.countdown.set('Kept open - close when finished')
        self.keep_button.configure(state='disabled')
        self.progress.place_configure(relwidth=1)

    def open_history(self):
        if self.on_open_history: self.on_open_history()
        self.close_now()

    def close_now(self):
        if self._timer:
            try: self.after_cancel(self._timer)
            except tk.TclError: pass
            self._timer=None
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        startup_clock=time.perf_counter()
        super().__init__()
        ensure_linux_ui_scaling(self)
        self._app_icon_image=None
        png_icon,ico_icon=application_icon_paths()
        try:
            if png_icon.is_file():
                self._app_icon_image=tk.PhotoImage(file=str(png_icon))
                self.iconphoto(True,self._app_icon_image)
            if platform.system()=='Windows' and ico_icon.is_file():
                self.iconbitmap(default=str(ico_icon))
        except (OSError,tk.TclError):
            # Branding must never prevent journal monitoring from starting.
            self._app_icon_image=None
        self.title(f'Discovery Watch v{APP_VERSION} - Elite Dangerous')
        startup_geometry=initial_window_geometry(self.winfo_screenwidth(),self.winfo_screenheight())
        self.geometry(startup_geometry)
        startup_width,startup_height=(int(value) for value in startup_geometry.split('x'))
        self.minsize(min(1000,startup_width),min(680,startup_height))
        style=apply_app_theme(self)
        self.monitor = None
        self._startup_monitor = None
        self._startup_views_loaded = False
        self._lazy_views_loaded = set()
        self.startup_timings = {'views':{}}
        self.running = False
        self.windows_overlay_queue=deque()
        self.windows_overlay_active=False
        self.windows_overlay_timer=None
        saved_folder,auto_start,popup_auto_close,popup_timeout=interface_preferences()
        saved_path=Path(saved_folder).expanduser() if saved_folder else None
        self.saved_folder_unavailable=bool(saved_path and not saved_path.is_dir())
        initial_folder=saved_path if saved_path and saved_path.is_dir() else DEFAULT_JOURNAL
        self.folder = tk.StringVar(value=str(initial_folder))
        self.auto_start_monitoring=tk.BooleanVar(value=auto_start)
        self.popup_auto_close=tk.BooleanVar(value=popup_auto_close)
        self.popup_timeout=tk.IntVar(value=popup_timeout)
        self.popup_above_game=tk.BooleanVar(value=popup_above_game_preference())
        self.popup_sound=tk.BooleanVar(value=popup_sound_preference())
        self.popup_monitor=tk.StringVar(value=popup_monitor_preference())
        popup_position_choice,popup_font_choice=popup_appearance_preferences()
        self.popup_position_choice=tk.StringVar(value=popup_position_choice)
        self.popup_font_choice=tk.StringVar(value=popup_font_choice)
        self.windows_notification_mode=tk.StringVar(value=windows_notification_mode_preference())
        self.popup_test_choice=tk.StringVar(value=POPUP_TEST_SCENARIOS[0])
        detect_megaships,detect_installations,detect_unresolved=detection_preferences()
        self.mega = tk.BooleanVar(value=detect_megaships)
        self.installations = tk.BooleanVar(value=detect_installations)
        self.unresolved = tk.BooleanVar(value=detect_unresolved)
        detect_phenomena,detect_unknown,popup_alerts=general_alert_preferences()
        self.phenomena = tk.BooleanVar(value=detect_phenomena)
        self.unusual = tk.BooleanVar(value=detect_unknown)
        self.popup = tk.BooleanVar(value=popup_alerts)
        self.anomaly_alerts = tk.BooleanVar(value=anomaly_alert_preference())
        self.exploration_criteria_vars={rule:tk.BooleanVar(value=enabled)
            for rule,enabled in exploration_criteria_preferences().items()}
        self.planetary_mining_popups = tk.BooleanVar(value=planetary_mining_popup_preference())
        self.surface_popup_vars={category:tk.BooleanVar(value=enabled)
                                 for category,enabled in surface_signal_popup_preferences().items()}
        self.stratum_popups=tk.BooleanVar(value=stratum_popup_preference())
        self.before_leave=tk.BooleanVar(value=before_leave_preference())
        self.known_pois_on_arrival = tk.BooleanVar(value=known_poi_arrival_preference())
        self.arrival_discovery_status = tk.BooleanVar(value=arrival_discovery_status_preference())
        self.edsm_enabled = tk.BooleanVar(value=edsm_enabled_preference())
        self.search = tk.StringVar()
        self.level_filter = tk.StringVar(value='All levels')
        self.finding_type_filter = tk.StringVar(value='All findings')
        self.explorer_search = tk.StringVar()
        self.incomplete_only = tk.BooleanVar(value=False)
        self.history_search = tk.StringVar(); self.history_event = tk.StringVar()
        self.history_from = tk.StringVar(); self.history_to = tk.StringVar()
        self.signal_priority=tk.IntVar(value=40); self.signal_popup=tk.BooleanVar(value=False)
        self.quick_signal_vars={key:tk.BooleanVar(value=True) for key in QUICK_SIGNAL_KEYS}
        self.generic_priority=tk.IntVar(value=50); self.generic_match=tk.StringVar(value='exact')
        self.generic_popup=tk.StringVar(value='once_system'); self.generic_notify=tk.BooleanVar(value=True)
        self.generic_pattern=tk.StringVar()
        self.advanced_rule_search=tk.StringVar()
        self.monitor_status = tk.StringVar(value='Stopped')
        self.active_journal = tk.StringVar(value='None')
        self.event_count = tk.StringVar(value='0 events received')
        self.last_event = tk.StringVar(value='No events received')
        self.journal_error = tk.StringVar(value='No errors')
        self.displayed_events = 0
        self.status = tk.StringVar(value='Stopped - choose your journal folder and click Start.')
        self.current_summary = tk.StringVar(value='Current system: waiting for monitoring data')
        self.activity_text=tk.StringVar(value='Journal: stopped')
        self.activity_generation=0
        self.edsm_status=tk.StringVar(value='EDSM disabled - enable it in Settings to add community context.')
        self.edsm_details=tk.StringVar(value='Offline journal intelligence remains fully available.')
        self.edsm_leads=tk.StringVar(value='Possible leads: none evaluated.')
        self.edsm_current_system=None
        self.edsm_results=queue.Queue()
        self.edsm_inflight=set()
        self.replay_results=queue.Queue()
        self.replay_running=False
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill='both', expand=True)
        heading=ttk.Frame(outer,style='Header.TFrame',padding=(10,8)); heading.pack(fill='x')
        ttk.Label(heading, text=f'Discovery Watch v{APP_VERSION}',style='Title.TLabel').pack(side='left')
        ttk.Label(heading,text='Exploration intelligence from your Elite Dangerous journal',
                  style='Header.TLabel').pack(side='left',padx=14)
        self.activity_canvas=tk.Canvas(heading,width=20,height=20,highlightthickness=0,
                                       background=THEME['surface'])
        self.activity_canvas.pack(side='right',padx=(6,2))
        self.activity_icon=self.activity_canvas.create_oval(4,4,16,16,fill=THEME['subtle'],outline='')
        ttk.Label(heading,textvariable=self.activity_text,style='Header.TLabel').pack(side='right')
        ttk.Label(outer, text='Journal folder').pack(anchor='w',pady=(8,0))
        folder_row = ttk.Frame(outer)
        folder_row.pack(fill='x', pady=5)
        ttk.Entry(folder_row, textvariable=self.folder).pack(side='left', fill='x', expand=True)
        ttk.Button(folder_row, text='Browse...', command=self.browse).pack(side='left', padx=5)
        controls = ttk.Frame(outer)
        controls.pack(fill='x', pady=5)
        self.start_button = ttk.Button(controls, text='Start monitoring', command=self.start,style='Accent.TButton')
        self.start_button.pack(side='left')
        ttk.Button(controls, text='Stop', command=self.stop).pack(side='left', padx=6)
        ttk.Button(controls,text='How it works',command=self.show_first_run_help).pack(side='right')
        ttk.Label(outer, textvariable=self.status,style='Status.TLabel').pack(anchor='w', pady=(4,1))
        ttk.Label(outer,textvariable=self.current_summary,style='System.TLabel').pack(anchor='w',pady=(0,6))
        tabs = ttk.Notebook(outer)
        self.tabs=tabs
        tabs.pack(fill='both', expand=True)
        home = ttk.Frame(tabs, padding=8)
        history = ttk.Frame(tabs)
        explorer_shell = ttk.Frame(tabs, padding=6)
        settings = ttk.Frame(tabs, padding=6)
        for frame,label in zip((home,history,explorer_shell,settings),PRIMARY_TAB_LABELS):
            tabs.add(frame,text=label)

        home_tabs=ttk.Notebook(home); home_tabs.pack(fill='both',expand=True)
        self.home_tabs=home_tabs
        assistant=add_scrollable_notebook_page(home_tabs,'Overview',padding=8)
        self.home_overview_canvas=assistant._settings_scroll_canvas
        journal=ttk.Frame(home_tabs,padding=8)
        home_tabs.add(journal,text='Journal diagnostics')
        explorer_tabs=ttk.Notebook(explorer_shell); explorer_tabs.pack(fill='both',expand=True)
        self.explorer_tabs=explorer_tabs
        explorer=ttk.Frame(explorer_tabs,padding=8); historical=ttk.Frame(explorer_tabs,padding=8)
        explorer_tabs.add(explorer,text='Recorded systems'); explorer_tabs.add(historical,text='Journal search')
        ttk.Label(settings,text=('Navigation: use the section tabs, scrollbar, mouse wheel or Page Up/Page Down. '
                                 'Shortcuts: Ctrl+1 to Ctrl+4 for main pages; Ctrl+Alt+1 to Ctrl+Alt+3 for Settings sections.'),
                  wraplength=1100).pack(anchor='w',padx=4,pady=(0,5))
        settings_tabs=ttk.Notebook(settings); settings_tabs.pack(fill='both',expand=True)
        self.settings_tabs=settings_tabs
        signals=add_scrollable_notebook_page(settings_tabs,SETTINGS_TAB_LABELS[0])
        advanced_rules=add_scrollable_notebook_page(settings_tabs,SETTINGS_TAB_LABELS[1])
        data_settings=add_scrollable_notebook_page(settings_tabs,SETTINGS_TAB_LABELS[2])
        ttk.Label(advanced_rules,text='Advanced Alert Rules',style='Section.TLabel').pack(anchor='w')
        ttk.Label(advanced_rules,text='Signal types control broad journal categories. Generic signal names identify specific contacts when Elite reports only SignalType: Generic.',
                  wraplength=950).pack(anchor='w',pady=(2,8))
        advanced_search=ttk.Frame(advanced_rules); advanced_search.pack(fill='x',pady=(0,8))
        ttk.Label(advanced_search,text='Search all rules:').pack(side='left')
        ttk.Entry(advanced_search,textvariable=self.advanced_rule_search).pack(side='left',fill='x',expand=True,padx=6)
        ttk.Button(advanced_search,text='Clear',command=lambda:self.advanced_rule_search.set('')).pack(side='left')
        rule_views=ttk.Notebook(advanced_rules); rule_views.pack(fill='both',expand=True)
        self.rule_views=rule_views
        advanced_signals=ttk.Frame(rule_views,padding=8)
        generic_signals=ttk.Frame(rule_views,padding=8)
        watchlists=ttk.Frame(rule_views,padding=8)
        rule_views.add(advanced_signals,text='Signal types')
        rule_views.add(generic_signals,text='Generic signal names')
        rule_views.add(watchlists,text='Commander watchlists')
        history_controls=ttk.Frame(history); history_controls.pack(fill='x',pady=(0,4))
        ttk.Button(history_controls,text='Acknowledge',command=lambda:self.change_alert('acknowledged')).pack(side='left')
        ttk.Button(history_controls,text='Add/edit note',command=self.edit_alert_note).pack(side='left')
        ttk.Button(history_controls,text='Export selected...',command=self.export_selected_alerts).pack(side='left',padx=5)
        ttk.Button(history_controls,text='Clear Discovery History...',style='Danger.TButton',
                   command=self.clear_discovery_history_action).pack(side='left',padx=(8,0))
        ttk.Button(history_controls,text='Export all CSV',command=lambda:self.export('csv')).pack(side='right')
        ttk.Button(history_controls,text='Export all JSON',command=lambda:self.export('json')).pack(side='right',padx=5)
        ttk.Button(history_controls,text='Refresh',command=self.refresh).pack(side='right')
        search_row=ttk.Frame(history); search_row.pack(fill='x',pady=(0,5))
        ttk.Label(search_row,text='Search findings:').pack(side='left')
        self.history_filter_entry=ttk.Entry(search_row,textvariable=self.search)
        self.history_filter_entry.pack(side='left',fill='x',expand=True,padx=6)
        ttk.Label(search_row,text='Importance:').pack(side='left')
        level_box=ttk.Combobox(search_row,textvariable=self.level_filter,state='readonly',width=14,
                               values=('All levels','Important','Review','Informational'))
        level_box.pack(side='left',padx=(5,0)); level_box.bind('<<ComboboxSelected>>',lambda *_:self.refresh())
        ttk.Label(search_row,text='Type:').pack(side='left',padx=(10,0))
        type_box=ttk.Combobox(search_row,textvariable=self.finding_type_filter,state='readonly',width=22,
                              values=FINDING_TYPE_CHOICES)
        type_box.pack(side='left',padx=(5,0)); type_box.bind('<<ComboboxSelected>>',lambda *_:self.refresh())
        self.search.trace_add('write',lambda *_:self.refresh())
        columns = ('time', 'level', 'type', 'system', 'finding', 'detail','status','notes')
        self.table = ttk.Treeview(history, columns=columns, show='headings')
        for col, width in [('time',135),('level',85),('type',145),('system',135),('finding',170),
                          ('detail',260),('status',85),('notes',130)]:
            self.table.heading(col, text=col.title())
            self.table.column(col, width=width)
        self.table.pack(fill='both', expand=True)
        self.table.tag_configure('Important',foreground=THEME['orange'])
        self.table.tag_configure('Review',foreground=THEME['review'])
        self.table.tag_configure('Informational',foreground=THEME['cyan'])
        self.table.tag_configure('acknowledged',foreground=THEME['cyan'])
        self.table.tag_configure('dismissed',foreground=THEME['subtle'])
        self.table.bind('<Double-1>', self.show_detail)
        self.history_empty=tk.StringVar(value='No discoveries recorded yet. Start monitoring, enter a system and use the Discovery Scanner.')
        ttk.Label(history,textvariable=self.history_empty).pack(anchor='w',pady=5)
        ttk.Label(history, text='Double-click a finding to view the original journal evidence. Findings are leads, not proof of rarity.').pack(anchor='w')
        self.rows = {}
        for variable in (self.monitor_status, self.active_journal, self.event_count, self.last_event, self.journal_error):
            ttk.Label(journal, textvariable=variable, wraplength=950).pack(anchor='w', pady=2)
        ttk.Label(journal, text='All new journal events, including events that do not trigger discovery alerts. Select an event to inspect its full JSON.').pack(anchor='w', pady=6)
        pane = ttk.Panedwindow(journal, orient='vertical')
        pane.pack(fill='both', expand=True)
        event_frame = ttk.Frame(pane)
        json_frame = ttk.Frame(pane)
        pane.add(event_frame, weight=3)
        pane.add(json_frame, weight=2)
        self.event_table = ttk.Treeview(event_frame, columns=('received','timestamp','event','system','file','line'), show='headings')
        for column, width in [('received',80),('timestamp',160),('event',190),('system',160),('file',210),('line',65)]:
            self.event_table.heading(column, text=column.title())
            self.event_table.column(column, width=width)
        self.event_table.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(event_frame, orient='vertical', command=self.event_table.yview)
        scroll.pack(side='right', fill='y')
        self.event_table.configure(yscrollcommand=scroll.set)
        self.raw_text = tk.Text(json_frame, wrap='none', height=10)
        self.raw_text.pack(fill='both', expand=True)
        self.raw_text.configure(state='disabled')
        self.event_rows = {}
        self.event_table.bind('<<TreeviewSelect>>', self.select_event)
        ttk.Button(journal, text='Clear displayed events', command=self.clear_events).pack(anchor='e', pady=4)
        ttk.Label(explorer, text='Journal-recorded exploration only. Scan and mapping counts are not confirmed first-discovery awards.').pack(anchor='w')
        self.explorer_status = tk.StringVar(value='Select a system to inspect its stored journal evidence.')
        ttk.Label(explorer, textvariable=self.explorer_status).pack(anchor='w', pady=5)
        erow = ttk.Frame(explorer); erow.pack(fill='x')
        ttk.Button(erow, text='Refresh systems', command=self.refresh_explorer).pack(side='left')
        ttk.Button(erow,text='Import older journals...',command=self.import_history).pack(side='left',padx=5)
        epane = ttk.Panedwindow(explorer, orient='vertical'); epane.pack(fill='both', expand=True, pady=5)
        sf = ttk.Frame(epane); df = ttk.Frame(epane); epane.add(sf,weight=1); epane.add(df,weight=2)
        filterrow=ttk.Frame(sf); filterrow.pack(fill='x',pady=(0,4))
        ttk.Label(filterrow,text='Search system/body/event:').pack(side='left')
        self.explorer_filter_entry=ttk.Entry(filterrow,textvariable=self.explorer_search)
        self.explorer_filter_entry.pack(side='left',fill='x',expand=True,padx=5)
        ttk.Checkbutton(filterrow,text='Incomplete only',variable=self.incomplete_only,command=self.refresh_explorer).pack(side='left')
        self.explorer_search.trace_add('write',lambda *_: self.refresh_explorer())
        self.system_table = ttk.Treeview(sf,columns=('system','scans','maps','organic','events','status'),show='headings',height=6)
        for col,width in [('system',240),('scans',70),('maps',70),('organic',80),('events',70),('status',90)]:
            self.system_table.heading(col,text=col.title()); self.system_table.column(col,width=width)
        self.system_table.pack(fill='both',expand=True)
        self.system_table.bind('<<TreeviewSelect>>',self.select_system)
        self.detail_table = ttk.Treeview(df,columns=('time','event','body','fact'),show='headings')
        for col,width in [('time',180),('event',190),('body',330),('fact',130)]:
            self.detail_table.heading(col,text=col.title()); self.detail_table.column(col,width=width)
        self.detail_table.pack(fill='both',expand=True)
        self.detail_table.bind('<Double-1>',self.show_exploration_detail)
        self.exploration_rows = {}
        self.home_system=tk.StringVar(value='Waiting for journal data')
        self.home_known_pois=tk.StringVar(value='Waiting for location')
        self.live_heading=tk.StringVar(value='Current system: waiting for journal data')
        self.live_stats=tk.StringVar(value='Scans: 0  |  Maps: 0  |  Signals: 0  |  Anomalies: 0  |  Completion: Unknown')
        self.live_advice=tk.StringVar(value='Start monitoring and enter or jump to a system.')
        self.visit_intelligence=tk.StringVar(value='No confirmed system visit yet.')
        self.home_alert_heading=tk.StringVar(value='No discovery alerts yet')
        self.home_alert_received=tk.StringVar(value='No alert received this session')
        self.latest_alert_findings=[]
        self.latest_alert_time=None
        ttk.Label(assistant,text=('Overview navigation: use the scrollbar, mouse wheel, Page Up/Page Down, '
                                  'Home or End. Maximising the window uses all available space.'),
                  wraplength=1050).pack(anchor='w',pady=(0,6))
        cards=ttk.Frame(assistant); cards.pack(fill='x',pady=(0,10))
        for title,variable in [('Monitoring',self.monitor_status),('Current system',self.home_system),
                               ('Known POIs here',self.home_known_pois),('Last journal event',self.last_event)]:
            card=ttk.LabelFrame(cards,text=title,padding=8,style='Card.TLabelframe'); card.pack(side='left',fill='both',expand=True,padx=3)
            ttk.Label(card,textvariable=variable,style='CardValue.TLabel',wraplength=245).pack(anchor='w')
        community=ttk.LabelFrame(assistant,text='Community Intelligence (EDSM)',padding=8,style='Card.TLabelframe')
        community.pack(fill='x',pady=(0,10))
        community_top=ttk.Frame(community,style='Card.TFrame'); community_top.pack(fill='x')
        ttk.Label(community_top,textvariable=self.edsm_status,style='CardTitle.TLabel').pack(side='left',anchor='w')
        self.edsm_open_button=ttk.Button(community_top,text='Open system on EDSM',
                                         command=self.open_current_edsm,state='disabled')
        self.edsm_open_button.pack(side='right')
        ttk.Label(community,textvariable=self.edsm_details,wraplength=1000,style='Card.TLabel').pack(anchor='w',pady=(4,2))
        ttk.Label(community,textvariable=self.edsm_leads,wraplength=1000,style='Card.TLabel').pack(anchor='w')
        home_lower=ttk.Panedwindow(assistant,orient='horizontal')
        cases_frame=ttk.LabelFrame(home_lower,text='Current visit intelligence',padding=8,style='Card.TLabelframe')
        ttk.Label(cases_frame,textvariable=self.visit_intelligence,wraplength=620,style='Card.TLabel').pack(anchor='w',pady=(0,5))
        self.case_table=ttk.Treeview(cases_frame,columns=('body','target','state','evidence','next'),
                                     show='headings',height=3)
        for col,width in [('body',145),('target',165),('state',75),('evidence',70),('next',220)]:
            self.case_table.heading(col,text=col.title()); self.case_table.column(col,width=width)
        case_scroll=ttk.Scrollbar(cases_frame,orient='vertical',command=self.case_table.yview)
        self.case_table.configure(yscrollcommand=case_scroll.set)
        case_scroll.pack(side='right',fill='y'); self.case_table.pack(side='left',fill='both',expand=True)
        ttk.Label(assistant,textvariable=self.live_heading,style='Section.TLabel').pack(anchor='w')
        ttk.Label(assistant,textvariable=self.live_stats).pack(anchor='w',pady=4)
        ttk.Label(assistant,textvariable=self.live_advice,wraplength=1050).pack(anchor='w',pady=(0,8))
        alert_frame=ttk.LabelFrame(home_lower,text='Latest discovery alerts',padding=8,style='Card.TLabelframe')
        alert_top=ttk.Frame(alert_frame,style='Card.TFrame'); alert_top.pack(fill='x',pady=(0,5))
        ttk.Label(alert_top,textvariable=self.home_alert_heading,style='Section.TLabel').pack(side='left')
        ttk.Button(alert_top,text='Open Discovery History',command=self.open_discovery_history).pack(side='right')
        ttk.Label(alert_frame,textvariable=self.home_alert_received,style='Card.TLabel').pack(anchor='w',pady=(0,5))
        alert_body=ttk.Frame(alert_frame,style='Card.TFrame'); alert_body.pack(fill='both',expand=True)
        self.home_alert_text=tk.Text(alert_body,wrap='word',height=10,borderwidth=0,padx=10,pady=8,
                                     background=THEME['surface'],foreground=THEME['text'],
                                     insertbackground=THEME['text'],font=('TkDefaultFont',10),
                                     highlightthickness=1,highlightbackground=THEME['border'])
        alert_scroll=ttk.Scrollbar(alert_body,orient='vertical',command=self.home_alert_text.yview)
        self.home_alert_text.configure(yscrollcommand=alert_scroll.set)
        alert_scroll.pack(side='right',fill='y'); self.home_alert_text.pack(side='left',fill='both',expand=True)
        self.home_alert_text.tag_configure('importance',foreground=THEME['orange'],font=('TkDefaultFont',9,'bold'))
        self.home_alert_text.tag_configure('title',foreground=THEME['text'],font=('TkDefaultFont',12,'bold'))
        self.home_alert_text.tag_configure('system',foreground=THEME['cyan'],font=('TkDefaultFont',9,'bold'))
        self.home_alert_text.tag_configure('detail',foreground=THEME['muted'])
        home_lower.add(cases_frame,weight=1)
        home_lower.add(alert_frame,weight=1)
        home_lower.pack(fill='both',expand=True)
        self.update_home_alert_panel([])
        hfilter=ttk.Frame(historical); hfilter.pack(fill='x')
        for label,var,width in [('Search',self.history_search,22),('Event type',self.history_event,15),('From',self.history_from,11),('To',self.history_to,11)]:
            ttk.Label(hfilter,text=label+':').pack(side='left'); ttk.Entry(hfilter,textvariable=var,width=width).pack(side='left',padx=(3,8))
        ttk.Button(hfilter,text='Search',command=self.refresh_historical).pack(side='left')
        ttk.Label(historical,text='Dates accept YYYY-MM-DD. Double-click any event for its complete original JSON.').pack(anchor='w',pady=5)
        self.historical_table=ttk.Treeview(historical,columns=('time','event','system','body','session','line'),show='headings')
        for col,width in [('time',165),('event',165),('system',180),('body',240),('session',185),('line',55)]:
            self.historical_table.heading(col,text=col.title()); self.historical_table.column(col,width=width)
        self.historical_table.pack(fill='both',expand=True)
        self.historical_rows={}; self.historical_table.bind('<Double-1>',self.show_historical_event)
        self.history_status=tk.StringVar(value='No historical search run yet.')
        ttk.Label(historical,textvariable=self.history_status).pack(anchor='w',pady=4)
        ttk.Label(signals,text='Choose what should interrupt you',style='Section.TLabel').pack(anchor='w')
        ttk.Label(signals,text='Enabled categories create Discovery History findings. Popup notifications remain controlled by the master switch below.',
                  wraplength=900).pack(anchor='w',pady=(2,10))
        basic_grid=ttk.Frame(signals); basic_grid.pack(fill='x')
        discoveries=ttk.LabelFrame(basic_grid,text='Discovery contacts',padding=10)
        discoveries.pack(fill='x',pady=(0,8))
        for text,variable in [('Megaships',self.mega),('Installations',self.installations)]:
            ttk.Checkbutton(discoveries,text=text,variable=variable,
                            command=self.save_detection_filters).pack(anchor='w',pady=2)
        for text,key in [('Titans','titan'),('Tourist beacons','touristbeacon'),
                         ('Nonhuman signal sources','nonhumanuss'),('Listening posts','listeningpost')]:
            ttk.Checkbutton(discoveries,text=text,variable=self.quick_signal_vars[key],
                            command=lambda k=key:self.toggle_quick_signal(k)).pack(anchor='w',pady=2)
        review=ttk.LabelFrame(basic_grid,text='Review prompts',padding=10)
        review.pack(fill='x',pady=(0,8))
        ttk.Checkbutton(review,text='Experimental: Unidentified system contacts (exploration)',variable=self.unresolved,
                        command=self.save_detection_filters).pack(anchor='w',pady=2)
        ttk.Label(review,text='Off by default. Tracks unresolved contacts per system visit; may include ordinary signals.',
                  wraplength=260).pack(anchor='w',pady=(0,4))
        ttk.Checkbutton(review,text='Stellar phenomena',variable=self.phenomena,
                        command=self.save_general_alert_settings).pack(anchor='w',pady=2)
        ttk.Checkbutton(review,text='Unknown or unidentified names',variable=self.unusual,
                        command=self.save_general_alert_settings).pack(anchor='w',pady=2)
        ttk.Checkbutton(review,text='Popup for notable worlds and anomalies',variable=self.anomaly_alerts,
                        command=self.save_anomaly_alert_setting).pack(anchor='w',pady=2)
        ttk.Checkbutton(review,text='Show Planetary Mining Location popups',variable=self.planetary_mining_popups,
                        command=self.save_planetary_mining_popup_setting).pack(anchor='w',pady=2)
        ttk.Checkbutton(review,text='Warn before leaving unfinished discoveries',variable=self.before_leave,
                        command=self.save_before_leave_setting).pack(anchor='w',pady=2)
        criteria_box=ttk.LabelFrame(signals,text='Built-in exploration criteria',padding=10)
        criteria_box.pack(fill='x',pady=(4,10))
        ttk.Label(criteria_box,
                  text=('Journal-supported astronomical checks. Every enabled match is saved in Discovery History; '
                        'the anomaly popup switch above controls whether it interrupts play.'),
                  wraplength=900).grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,6))
        for index,(rule,label) in enumerate(EXPLORATION_CRITERIA.items()):
            row=1+index//2; column=index%2
            ttk.Checkbutton(criteria_box,text=label,variable=self.exploration_criteria_vars[rule],
                            command=self.save_exploration_criteria_settings).grid(
                                row=row,column=column,sticky='w',padx=(0,24),pady=2)
        criteria_box.columnconfigure(0,weight=1); criteria_box.columnconfigure(1,weight=1)
        notifications=ttk.LabelFrame(basic_grid,text='Notifications',padding=10)
        notifications.pack(fill='x')
        ttk.Checkbutton(notifications,text='Show popup notifications',variable=self.popup,
                        command=self.save_general_alert_settings).pack(anchor='w',pady=2)
        ttk.Checkbutton(notifications,text='Show known POIs when arriving in a system',
                        variable=self.known_pois_on_arrival,
                        command=self.save_known_poi_arrival_setting).pack(anchor='w',pady=2)
        ttk.Checkbutton(notifications,text='Alert possible undiscovered arrival stars (experimental)',
                        variable=self.arrival_discovery_status,
                        command=self.save_arrival_discovery_status_setting).pack(anchor='w',pady=2)
        ttk.Label(notifications,
                  text='Off by default. Uses the arrival star WasDiscovered value; it cannot prove the status of every body.',
                  wraplength=850).pack(anchor='w',pady=(0,4))
        ttk.Checkbutton(notifications,text='Close alert popups automatically',variable=self.popup_auto_close,
                        command=self.save_interface_settings).pack(anchor='w',pady=2)
        ttk.Checkbutton(notifications,text='Keep alert popups above the game',variable=self.popup_above_game,
                        command=self.save_popup_above_game_setting).pack(anchor='w',pady=2)
        ttk.Checkbutton(notifications,text='Play a sound with alert popups',variable=self.popup_sound,
                        command=self.save_popup_sound_setting).pack(anchor='w',pady=2)
        windows_mode_row=ttk.Frame(notifications); windows_mode_row.pack(anchor='w',fill='x',pady=2)
        ttk.Label(windows_mode_row,text='Windows notification mode:').pack(side='left')
        windows_mode_box=ttk.Combobox(windows_mode_row,textvariable=self.windows_notification_mode,
                                      values=WINDOWS_NOTIFICATION_MODES,state='readonly',width=31)
        if platform.system()!='Windows': windows_mode_box.configure(state='disabled')
        windows_mode_box.pack(side='left',padx=4)
        windows_mode_box.bind('<<ComboboxSelected>>',lambda _event:self.save_windows_notification_mode_setting())
        ttk.Label(notifications,text=('Windows game overlay is recommended for Elite: it is click-through, stays above '
                                      'borderless gameplay and does not take focus. Native uses Windows notifications.'),
                  wraplength=650).pack(anchor='w',pady=(0,4))
        monitor_row=ttk.Frame(notifications); monitor_row.pack(anchor='w',fill='x',pady=2)
        wayland_active=is_wayland_session()
        ttk.Label(monitor_row,text='Popup monitor - Windows/X11 only:').pack(side='left')
        monitor_box=ttk.Combobox(monitor_row,textvariable=self.popup_monitor,state='readonly',width=24,
                                 values=POPUP_MONITOR_CHOICES)
        self.popup_monitor_box=monitor_box
        if wayland_active: monitor_box.configure(state='disabled')
        monitor_box.pack(side='left',padx=4)
        monitor_box.bind('<<ComboboxSelected>>',lambda _event:self.save_popup_monitor_setting())
        ttk.Label(notifications,text=('Wayland detected: your Linux desktop controls native-notification placement.'
                                      if wayland_active else 'Monitor selection applies to Discovery Watch custom popups.'),
                  wraplength=260).pack(anchor='w',pady=(0,4))
        appearance_row=ttk.Frame(notifications); appearance_row.pack(anchor='w',fill='x',pady=2)
        ttk.Label(appearance_row,text='Popup position:').pack(side='left')
        position_box=ttk.Combobox(appearance_row,textvariable=self.popup_position_choice,
                                  values=POPUP_POSITION_CHOICES,state='readonly',width=14)
        position_box.pack(side='left',padx=(4,12))
        position_box.bind('<<ComboboxSelected>>',lambda _event:self.save_popup_appearance_setting())
        ttk.Label(appearance_row,text='Text size:').pack(side='left')
        font_box=ttk.Combobox(appearance_row,textvariable=self.popup_font_choice,
                              values=POPUP_FONT_CHOICES,state='readonly',width=9)
        font_box.pack(side='left',padx=4)
        font_box.bind('<<ComboboxSelected>>',lambda _event:self.save_popup_appearance_setting())
        if wayland_active:
            position_box.configure(state='disabled')
            ttk.Label(notifications,text=('Wayland native notifications use the desktop notification position; '
                                          'text size is also desktop controlled.'),
                      wraplength=700).pack(anchor='w',pady=(0,4))
        timeout_row=ttk.Frame(notifications); timeout_row.pack(anchor='w',pady=2)
        ttk.Label(timeout_row,text='Popup timeout:').pack(side='left')
        timeout_box=ttk.Combobox(timeout_row,textvariable=self.popup_timeout,state='readonly',width=5,
                                 values=POPUP_TIMEOUT_CHOICES)
        timeout_box.pack(side='left',padx=4); ttk.Label(timeout_row,text='seconds').pack(side='left')
        timeout_box.bind('<<ComboboxSelected>>',lambda _event:self.save_interface_settings())
        ttk.Checkbutton(notifications,text='Notify once for new Generic names',variable=self.generic_notify,
                        command=self.save_generic_notify).pack(anchor='w',pady=2)
        test_row=ttk.Frame(notifications); test_row.pack(anchor='w',fill='x',pady=(8,2))
        ttk.Combobox(test_row,textvariable=self.popup_test_choice,values=POPUP_TEST_SCENARIOS,
                     state='readonly',width=24).pack(side='left')
        ttk.Button(test_row,text='Test selected popup and sound',command=self.test_notification).pack(side='left',padx=6)
        ttk.Button(notifications,text='Popup diagnostics...',command=self.show_popup_diagnostics).pack(anchor='w',pady=2)
        ttk.Button(notifications,text='View Windows overlay error log...',
                   command=self.show_windows_overlay_error).pack(anchor='w',pady=2)
        ttk.Label(notifications,text='Turning popups off does not stop findings being saved.',wraplength=250).pack(anchor='w',pady=(8,0))
        surface_alerts=ttk.LabelFrame(signals,text='Surface-signal popups',padding=10)
        surface_alerts.pack(fill='x',pady=(12,0))
        ttk.Label(surface_alerts,
                  text='Every SAASignalsFound/FSSBodySignals category is saved. Choose which categories should interrupt play.',
                  wraplength=900).pack(anchor='w',pady=(0,5))
        for text,category in [('Thargoid','thargoid'),('Guardian','guardian'),
                              ('Biological','biological'),('Geological','geological'),
                              ('Human','human'),('Other / unclassified','other')]:
            ttk.Checkbutton(surface_alerts,text=text,variable=self.surface_popup_vars[category],
                            command=self.save_surface_signal_popup_settings).pack(anchor='w',pady=2)
        ttk.Checkbutton(surface_alerts,text='Stratum leads and Tectonicas confirmations',
                        variable=self.stratum_popups,
                        command=self.save_stratum_popup_setting).pack(anchor='w',pady=2)
        startup=ttk.LabelFrame(signals,text='Startup',padding=10); startup.pack(fill='x',pady=(12,0))
        ttk.Checkbutton(startup,text='Start monitoring automatically when Discovery Watch opens',
                        variable=self.auto_start_monitoring,command=self.save_interface_settings).pack(anchor='w')
        ttk.Label(startup,text='Automatic monitoring starts only when the remembered journal folder is available.',
                  wraplength=850).pack(anchor='w',pady=(4,0))
        online=ttk.LabelFrame(signals,text='Online community data',padding=10); online.pack(fill='x',pady=(10,0))
        ttk.Checkbutton(online,text='Enable EDSM Community Intelligence',variable=self.edsm_enabled,
                        command=self.save_edsm_setting).pack(anchor='w')
        ttk.Label(online,text='Opt-in. After a confirmed arrival, Discovery Watch sends only the system name to EDSM. Responses are cached locally for seven days. Journal monitoring continues normally when offline.',
                  wraplength=850).pack(anchor='w',pady=(4,0))
        ttk.Label(signals,text='Advanced matching, priorities and per-type popup choices are available in Advanced alert rules.',
                  wraplength=900).pack(anchor='w',pady=(14,0))

        ttk.Label(advanced_signals,text='Signal types',style='Section.TLabel').pack(anchor='w')
        ttk.Label(advanced_signals,text='Broad journal categories such as Megaship, Installation and TouristBeacon. Choose Alert with Popup ticked, Alert silently, Catalogue only, or Ignore.',
                  wraplength=950).pack(anchor='w',pady=(2,8))
        srules=ttk.Frame(advanced_signals); srules.pack(fill='x',pady=5)
        for policy in ('alert','record','ignore'):
            label={'alert':'Alert','record':'Catalogue only','ignore':'Ignore'}[policy]
            ttk.Button(srules,text=label,command=lambda p=policy:self.set_selected_signal_policy(p)).pack(side='left',padx=(0,5))
        ttk.Label(srules,text='Priority:').pack(side='left',padx=(10,2))
        ttk.Spinbox(srules,from_=0,to=100,textvariable=self.signal_priority,width=5).pack(side='left')
        ttk.Checkbutton(srules,text='Popup',variable=self.signal_popup).pack(side='left',padx=8)
        self.signal_table=ttk.Treeview(advanced_signals,columns=('name','policy','priority','popup','seen','first','last','event','system'),show='headings')
        for col,width in [('name',130),('policy',110),('priority',60),('popup',55),('seen',55),('first',145),('last',145),('event',130),('system',150)]:
            self.signal_table.heading(col,text=col.title()); self.signal_table.column(col,width=width)
        self.signal_table.heading('policy',text='Effective behaviour')
        self.signal_table.pack(fill='both',expand=True); self.signal_rows={}
        self.signal_table.bind('<<TreeviewSelect>>',self.select_signal_rule)
        ttk.Label(generic_signals,text='Generic signal names',style='Section.TLabel').pack(anchor='w')
        ttk.Label(generic_signals,text='Used only when Elite reports SignalType: Generic. Rules compare the localised and internal names so useful contacts can be separated from routine Generic signals. New names wait for review.',
                  wraplength=950).pack(anchor='w',pady=(2,8))
        grow=ttk.Frame(generic_signals); grow.pack(fill='x',pady=5)
        for policy in ('alert','record','ignore','review'):
            ttk.Button(grow,text=policy.title(),command=lambda p=policy:self.set_selected_generic_rule(p)).pack(side='left',padx=(0,4))
        ttk.Label(grow,text='Match:').pack(side='left',padx=(8,2))
        ttk.Combobox(grow,textvariable=self.generic_match,values=('exact','contains'),state='readonly',width=9).pack(side='left')
        ttk.Label(grow,text='Popup:').pack(side='left',padx=(8,2))
        ttk.Combobox(grow,textvariable=self.generic_popup,values=('off','once_system','always'),state='readonly',width=12).pack(side='left')
        ttk.Label(grow,text='Priority:').pack(side='left',padx=(8,2))
        ttk.Spinbox(grow,from_=0,to=100,textvariable=self.generic_priority,width=5).pack(side='left')
        ttk.Label(generic_signals,text='Match text (editable for Contains rules):').pack(anchor='w')
        ttk.Entry(generic_signals,textvariable=self.generic_pattern).pack(fill='x',pady=(0,5))
        ttk.Checkbutton(generic_signals,text='Notify once when a previously unseen Generic name needs review',
                        variable=self.generic_notify,command=self.save_generic_notify).pack(anchor='w',pady=(0,5))
        self.generic_table=ttk.Treeview(generic_signals,columns=('local','internal','policy','match','pattern','popup','priority','seen','last','system'),show='headings')
        for col,width in [('local',155),('internal',130),('policy',60),('match',60),('pattern',135),('popup',80),('priority',50),('seen',45),('last',125),('system',125)]:
            self.generic_table.heading(col,text=col.title()); self.generic_table.column(col,width=width)
        self.generic_table.pack(fill='both',expand=True); self.generic_rows={}

        ttk.Label(watchlists,text='Commander Watchlists',style='Section.TLabel').pack(anchor='w')
        ttk.Label(watchlists,text='Match a case-insensitive phrase against new journal events. Use exact journal text such as Stratum Tectonicas or $SAA_SignalType_Thargoid;.',
                  wraplength=950).pack(anchor='w',pady=(2,8))
        wcontrols=ttk.Frame(watchlists); wcontrols.pack(fill='x',pady=5)
        ttk.Button(wcontrols,text='Add target...',command=self.add_watchlist).pack(side='left')
        ttk.Button(wcontrols,text='Enable/disable',command=lambda:self.toggle_watchlist('enabled')).pack(side='left',padx=5)
        ttk.Button(wcontrols,text='Toggle popup',command=lambda:self.toggle_watchlist('popup')).pack(side='left')
        ttk.Button(wcontrols,text='Delete',command=self.delete_watchlist).pack(side='left',padx=5)
        self.watchlist_table=ttk.Treeview(watchlists,columns=('name','pattern','enabled','popup','priority'),show='headings')
        for col,width in [('name',190),('pattern',340),('enabled',80),('popup',80),('priority',80)]:
            self.watchlist_table.heading(col,text=col.title()); self.watchlist_table.column(col,width=width)
        self.watchlist_table.pack(fill='both',expand=True); self.watchlist_rows={}
        self.generic_table.bind('<<TreeviewSelect>>',self.select_generic_rule)
        self.advanced_rule_search.trace_add('write',lambda *_:(self.refresh_signal_catalog(),self.refresh_generic_signals()))

        ttk.Label(data_settings,text='Data and support tools',style='Section.TLabel').pack(anchor='w')
        ttk.Label(data_settings,text='Import, export and backup actions do not change your Elite Dangerous journal files.',
                  wraplength=900).pack(anchor='w',pady=(2,10))
        transfer_box=ttk.LabelFrame(data_settings,text='Import and export',padding=10)
        transfer_box.pack(fill='x',pady=(0,10))
        for text,command in (
            ('Import older journal files...',self.import_history),
            ('Export exploration as JSON...',lambda:self.export_exploration('json')),
            ('Export exploration as CSV...',lambda:self.export_exploration('csv')),
            ('Back up Discovery Watch database...',self.backup_database)):
            ttk.Button(transfer_box,text=text,command=command).pack(anchor='w',fill='x',pady=2)
        support_box=ttk.LabelFrame(data_settings,text='Diagnostics and help',padding=10)
        support_box.pack(fill='x',pady=(0,10))
        ttk.Button(support_box,text='Check database integrity',command=self.check_database).pack(anchor='w',fill='x',pady=2)
        ttk.Button(support_box,text='Export diagnostic report...',command=self.export_diagnostic_report).pack(anchor='w',fill='x',pady=2)
        ttk.Button(support_box,text='Replay journal test...',command=self.run_journal_replay).pack(anchor='w',fill='x',pady=2)
        ttk.Button(support_box,text='Run built-in reliability check',command=self.run_builtin_reliability_check).pack(anchor='w',fill='x',pady=2)
        ttk.Button(support_box,text='Run Settings behaviour check',command=self.run_settings_behaviour_check).pack(anchor='w',fill='x',pady=2)
        ttk.Button(support_box,text='Show monitoring guide',command=self.show_first_run_help).pack(anchor='w',fill='x',pady=2)
        reset_box=ttk.LabelFrame(data_settings,text='Start fresh',padding=10)
        reset_box.pack(fill='x')
        ttk.Label(reset_box,text='Permanently removes Discovery Watch history, preferences and custom rules. Elite journal files are never deleted.',
                  wraplength=900).pack(anchor='w',pady=(0,6))
        ttk.Button(reset_box,text='Delete all Discovery Watch data...',command=self.delete_all_data,
                   style='Danger.TButton').pack(anchor='w')

        if self.edsm_enabled.get():
            self.edsm_status.set('EDSM enabled - waiting for a confirmed arrival.')
            self.edsm_details.set('No network request has been made yet.')
        # Draw the shell first. Saved data is populated shortly afterwards with
        # one shared database connection instead of constructing a Monitor for
        # every panel before the window can appear.
        self.refresh_live_assistant()
        self.refresh_cases()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind_all('<Control-f>',self.focus_current_search)
        self.bind_all('<F5>',lambda _event:self.refresh_all_views())
        self.bind_all('<MouseWheel>',self._scroll_settings_wheel,add='+')
        self.bind_all('<Button-4>',self._scroll_settings_wheel,add='+')
        self.bind_all('<Button-5>',self._scroll_settings_wheel,add='+')
        self.bind_all('<Prior>',lambda event:self._scroll_settings_key(event,-1),add='+')
        self.bind_all('<Next>',lambda event:self._scroll_settings_key(event,1),add='+')
        self.bind_all('<Home>',lambda event:self._scroll_settings_end(event,0),add='+')
        self.bind_all('<End>',lambda event:self._scroll_settings_end(event,1),add='+')
        self.tabs.bind('<<NotebookTabChanged>>',self._load_selected_lazy_view,add='+')
        self.explorer_tabs.bind('<<NotebookTabChanged>>',self._load_selected_lazy_view,add='+')
        self.settings_tabs.bind('<<NotebookTabChanged>>',self._load_selected_lazy_view,add='+')
        self.rule_views.bind('<<NotebookTabChanged>>',self._load_selected_lazy_view,add='+')
        for index in range(len(PRIMARY_TAB_LABELS)):
            self.bind_all(f'<Control-Key-{index+1}>',lambda _event,i=index:self.tabs.select(i))
        for index in range(len(SETTINGS_TAB_LABELS)):
            self.bind_all(f'<Control-Alt-Key-{index+1}>',
                          lambda _event,i=index:(self.tabs.select(3),self.settings_tabs.select(i)))
        self.after(250,self._drain_edsm_results)
        self.after(250,self._drain_replay_results)
        self.startup_timings['window_constructed_ms']=round(
            (time.perf_counter()-startup_clock)*1000,1)
        self.after(50,lambda:self._load_startup_views(startup_clock))
        pending_guide=first_run_pending()
        if self.saved_folder_unavailable:
            self.status.set('The remembered journal folder is unavailable. Choose its new location before monitoring.')
        if pending_guide:
            self.after(250,self.show_first_run_help)
        elif self.auto_start_monitoring.get() and Path(self.folder.get()).expanduser().is_dir():
            self.after(350,self.start)

    def _load_startup_views(self,startup_clock=None):
        """Populate persisted views after the shell is visible using one DB open."""
        if self._startup_views_loaded:
            return
        self._startup_views_loaded=True
        started=time.perf_counter()
        monitor=None
        try:
            if DB_PATH.exists():
                database_started=time.perf_counter()
                monitor=Monitor(self.folder.get(),DB_PATH,create_session=False)
                self._startup_monitor=monitor
                self.startup_timings['database_initialisation_ms']=round(
                    (time.perf_counter()-database_started)*1000,1)
            for name,operation in (
                    ('discovery_history',self.refresh),):
                view_started=time.perf_counter()
                operation()
                self.startup_timings['views'][name]=round(
                    (time.perf_counter()-view_started)*1000,1)
                self._lazy_views_loaded.add(name)
        except (OSError,sqlite3.Error,ValueError) as exc:
            self.journal_error.set(f'Startup data load: {exc}')
            self.status.set(f'Interface opened, but saved data could not be loaded: {exc}')
        finally:
            self._startup_monitor=None
            if monitor is not None:
                monitor.db.close()
            self.startup_timings['saved_views_ms']=round(
                (time.perf_counter()-started)*1000,1)
            origin=startup_clock if startup_clock is not None else started
            self.startup_timings['total_until_views_loaded_ms']=round(
                (time.perf_counter()-origin)*1000,1)

    def _load_selected_lazy_view(self,_event=None):
        """Load expensive hidden tables only when their page is selected."""
        if not self._startup_views_loaded:
            return
        target=None
        try:
            main_index=self.tabs.index(self.tabs.select())
            if main_index==2:
                explorer_index=self.explorer_tabs.index(self.explorer_tabs.select())
                target=(('recorded_systems',self.refresh_explorer),
                        ('journal_search',self.refresh_historical))[explorer_index]
            elif (main_index==3 and
                  self.settings_tabs.index(self.settings_tabs.select())==1):
                rule_index=self.rule_views.index(self.rule_views.select())
                target=(('signal_catalogue',self.refresh_signal_catalog),
                        ('generic_rules',self.refresh_generic_signals),
                        ('watchlists',self.refresh_watchlists))[rule_index]
        except (tk.TclError,IndexError):
            return
        if target is None or target[0] in self._lazy_views_loaded:
            return
        name,operation=target
        self._lazy_views_loaded.add(name)
        started=time.perf_counter()
        try:
            operation()
            self.startup_timings['views'][name]=round(
                (time.perf_counter()-started)*1000,1)
        except (OSError,sqlite3.Error,ValueError) as exc:
            self._lazy_views_loaded.discard(name)
            self.journal_error.set(f'Could not load {name.replace("_"," ")}: {exc}')

    def save_interface_settings(self):
        try:
            save_interface_preferences(self.folder.get(),self.auto_start_monitoring.get(),
                                       self.popup_auto_close.get(),self.popup_timeout.get())
        except (sqlite3.Error,ValueError) as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def set_activity_state(self,state):
        colours={'stopped':THEME['subtle'],'waiting':THEME['warning'],
                 'reading':THEME['success'],'error':THEME['danger']}
        labels={'stopped':'Journal: stopped','waiting':'Journal: monitoring - waiting',
                'reading':'Journal: reading new events','error':'Journal: read error'}
        self.activity_canvas.itemconfigure(self.activity_icon,fill=colours[state])
        self.activity_text.set(labels[state])

    def pulse_journal_activity(self):
        self.activity_generation+=1
        generation=self.activity_generation
        colours=(THEME['success'],THEME['cyan'],THEME['success'],
                 THEME['orange'],THEME['success'],THEME['cyan'])
        self.activity_text.set('Journal: reading new events')
        def frame(index=0):
            if generation!=self.activity_generation or not self.running: return
            if index>=len(colours):
                self.set_activity_state('waiting'); return
            self.activity_canvas.itemconfigure(self.activity_icon,fill=colours[index])
            self.after(180,lambda:frame(index+1))
        frame()

    def toggle_quick_signal(self,key):
        policy='alert' if self.quick_signal_vars[key].get() else 'record'
        try:
            if self.monitor:
                self.monitor.set_signal_policy(key,policy)
            else:
                with Monitor(self.folder.get()) as monitor:
                    monitor.set_signal_policy(key,policy)
        except (ValueError,sqlite3.Error) as exc:
            messagebox.showerror('Setting not saved',str(exc))
        self.refresh_signal_catalog()

    def focus_current_search(self,_event=None):
        index=self.tabs.index(self.tabs.select())
        target={1:self.history_filter_entry,2:self.explorer_filter_entry}.get(index)
        if target:
            target.focus_set(); target.selection_range(0,'end')
        return 'break'

    def _settings_canvas_for_event(self,event):
        widget=getattr(event,'widget',None)
        try:
            if widget is not None and widget.winfo_class() in ('Text','Treeview','Listbox'):
                return None
        except tk.TclError:
            return None
        while widget is not None:
            canvas=getattr(widget,'_settings_scroll_canvas',None)
            if canvas is not None:
                return canvas
            widget=getattr(widget,'master',None)
        # Keyboard events can be delivered to the root or notebook rather than
        # the visible page. Fall back to the active scrollable page.
        try:
            main_index=self.tabs.index(self.tabs.select())
            if main_index==0 and self.home_tabs.index(self.home_tabs.select())==0:
                return self.home_overview_canvas
            if main_index==3:
                page=self.nametowidget(self.settings_tabs.select())
                return getattr(page,'_settings_scroll_canvas',None)
        except (AttributeError,tk.TclError):
            pass
        return None

    def _scroll_settings_wheel(self,event):
        canvas=self._settings_canvas_for_event(event)
        if canvas is None: return None
        if getattr(event,'num',None)==4: direction=-1
        elif getattr(event,'num',None)==5: direction=1
        else:
            delta=getattr(event,'delta',0)
            direction=-1 if delta>0 else 1 if delta<0 else 0
        if direction:
            canvas.yview_scroll(direction*3,'units')
            return 'break'
        return None

    def _scroll_settings_key(self,event,direction):
        try:
            if event.widget.winfo_class() in ('Text','Treeview','Listbox'):
                return None
        except tk.TclError:
            return None
        canvas=self._settings_canvas_for_event(event)
        if canvas is None: return None
        canvas.yview_scroll(direction,'pages')
        return 'break'

    def _scroll_settings_end(self,event,end):
        canvas=self._settings_canvas_for_event(event)
        if canvas is None: return None
        if event.widget.winfo_class() in ('Entry','TEntry','Text','TCombobox','TSpinbox'):
            return None
        canvas.yview_moveto(float(end))
        return 'break'

    def refresh_all_views(self):
        self.refresh(); self.refresh_explorer()
        self.refresh_live_assistant(); self.refresh_historical()
        self.refresh_signal_catalog(); self.refresh_generic_signals(); self.refresh_watchlists()

    def refresh_cases(self):
        if not hasattr(self,'case_table'): return
        self.case_table.delete(*self.case_table.get_children())
        rows=self.monitor.current_visit_cases() if self.monitor and self.monitor.current_system else []
        for row in rows:
            self.case_table.insert('', 'end',values=(row[2],row[3],row[4],row[7],row[6]))
        visit=self.monitor.current_visit_intelligence() if self.monitor else {}
        if not rows:
            self.visit_intelligence.set('No surface-intelligence leads recorded during this visit.')
        else:
            self.visit_intelligence.set(
                f"{visit['cases']} linked investigation(s) - {visit['leads']} lead, "
                f"{visit['identified']} identified, {visit['confirmed']} confirmed, "
                f"{visit['completed']} completed - {visit['evidence']} evidence event(s)")

    def refresh_watchlists(self):
        if not hasattr(self,'watchlist_table'): return
        self.watchlist_table.delete(*self.watchlist_table.get_children()); self.watchlist_rows.clear()
        view_monitor=self.monitor or self._startup_monitor
        if view_monitor: rows=view_monitor.watchlists()
        else:
            with Monitor(self.folder.get(),create_session=False) as monitor: rows=monitor.watchlists()
        for row in rows:
            item=self.watchlist_table.insert('', 'end',values=(row[1],row[2],'Yes' if row[3] else 'No',
                                                               'Yes' if row[4] else 'No',row[5]))
            self.watchlist_rows[item]=row[0]

    def add_watchlist(self):
        name=simpledialog.askstring('Commander Watchlist','Target name:',parent=self)
        if not name: return
        pattern=simpledialog.askstring('Commander Watchlist','Journal text to match:',parent=self)
        if not pattern: return
        try:
            if self.monitor: self.monitor.add_watchlist(name,pattern)
            else:
                with Monitor(self.folder.get()) as monitor: monitor.add_watchlist(name,pattern)
            self.refresh_watchlists()
        except (ValueError,sqlite3.Error) as exc: messagebox.showerror('Watchlist not saved',str(exc))

    def _selected_watchlist_id(self):
        selected=self.watchlist_table.selection()
        return self.watchlist_rows.get(selected[0]) if selected else None

    def toggle_watchlist(self,field):
        watch_id=self._selected_watchlist_id()
        if watch_id is None: return
        if self.monitor: self.monitor.toggle_watchlist(watch_id,field)
        else:
            with Monitor(self.folder.get()) as monitor: monitor.toggle_watchlist(watch_id,field)
        self.refresh_watchlists()

    def delete_watchlist(self):
        watch_id=self._selected_watchlist_id()
        if watch_id is None or not messagebox.askyesno('Delete watchlist target?','Delete the selected Commander Watchlist target?'): return
        if self.monitor: self.monitor.delete_watchlist(watch_id)
        else:
            with Monitor(self.folder.get()) as monitor: monitor.delete_watchlist(watch_id)
        self.refresh_watchlists()

    def open_discovery_history(self):
        self.refresh(); self.tabs.select(1)
        try:
            self.state('normal'); self.deiconify(); self.lift(); self.focus_force()
        except tk.TclError:
            pass

    def create_detail_window(self,title,geometry='800x500'):
        """Create and raise a user-requested child window reliably on Linux desktops."""
        window=style_toplevel(tk.Toplevel(self))
        window.title(title); window.geometry(geometry); window.transient(self)
        def present():
            if not window.winfo_exists(): return
            try:
                window.state('normal'); window.deiconify(); window.lift(); window.focus_force()
                window.attributes('-topmost',True)
                window.after(250,lambda:self._release_detail_topmost(window))
            except tk.TclError:
                pass
        window.after_idle(present)
        return window

    @staticmethod
    def _release_detail_topmost(window):
        try:
            if window.winfo_exists(): window.attributes('-topmost',False)
        except tk.TclError:
            pass


    def refresh_explorer(self):
        selected = self.system_table.selection()
        current = self.system_table.item(selected[0], 'values')[0] if selected else None
        self.system_table.delete(*self.system_table.get_children())
        view_monitor=self.monitor or self._startup_monitor
        if view_monitor:
            rows = view_monitor.search_exploration(self.explorer_search.get(),self.incomplete_only.get())
        elif DB_PATH.exists():
            with Monitor(self.folder.get(),create_session=False) as monitor:
                rows = monitor.search_exploration(self.explorer_search.get(),self.incomplete_only.get())
        else:
            rows = []
        for row in rows:
            item = self.system_table.insert('', 'end', values=row)
            if row[0] == current:
                self.system_table.selection_set(item)
        self.explorer_status.set(f'{len(rows)} systems with recorded exploration events; current: ' +
                                 (self.monitor.current_system if self.monitor and self.monitor.current_system else 'not yet known'))

    def import_history(self):
        source = filedialog.askdirectory(title='Choose folder containing historical Journal files')
        if not source:
            return
        temporary = self.monitor is None
        monitor = self.monitor or Monitor(self.folder.get())
        try:
            result = monitor.import_journals(source, lambda done,total,name: (
                self.explorer_status.set(f'Importing {done}/{total}: {name}'), self.update_idletasks()))
            self.refresh_explorer()
            self.refresh_historical()
            messagebox.showinfo('Historical import complete', f"Files: {result['files']}\nAll journal events added: {result['historical_added']}\nExploration events added: {result['added']}\nExploration duplicates skipped: {result['duplicates']}\nErrors: {result['errors']}")
        except (OSError,sqlite3.Error) as exc:
            messagebox.showerror('Import failed',str(exc))
        finally:
            if temporary: monitor.db.close()

    def check_database(self):
        try:
            if self.monitor:
                result=self.monitor.integrity_check()
            else:
                with Monitor(self.folder.get()) as monitor: result=monitor.integrity_check()
            messagebox.showinfo('Database integrity', f"SQLite: {result['sqlite']}\nStored events: {result['events']}\nMissing required data: {result['orphaned']}\nInvalid JSON: {result['invalid_json']}")
        except sqlite3.Error as exc:
            messagebox.showerror('Integrity check failed',str(exc))

    def backup_database(self):
        destination=filedialog.asksaveasfilename(defaultextension='.sqlite3',filetypes=[('SQLite database','*.sqlite3')])
        if not destination:
            return
        try:
            if self.monitor:
                self.monitor.backup_database(destination)
            else:
                with Monitor(self.folder.get()) as monitor: monitor.backup_database(destination)
            messagebox.showinfo('Backup complete','Database backup created successfully.')
        except (OSError,sqlite3.Error) as exc:
            messagebox.showerror('Backup failed',str(exc))

    def delete_all_data(self):
        confirmed=messagebox.askyesno(
            'Delete all Discovery Watch data?',
            'This permanently deletes all Discovery Watch history, exploration records, '
            'anomalies, notes, review states, signal rules and preferences.\n\n'
            'Elite Dangerous journal files and game data will not be touched.\n\n'
            'Use Backup database first if you may want to recover this information.\n\n'
            'Delete everything and start fresh?',
            icon='warning',default='no')
        if not confirmed:
            return
        try:
            self.stop()
            reset_database(DB_PATH)
            self.mega.set(True); self.installations.set(True); self.unresolved.set(False)
            self.phenomena.set(True); self.unusual.set(True); self.popup.set(True)
            self.anomaly_alerts.set(False)
            for variable in self.exploration_criteria_vars.values():
                variable.set(True)
            self.planetary_mining_popups.set(False)
            for category,default in SURFACE_POPUP_DEFAULTS.items():
                self.surface_popup_vars[category].set(default)
            self.stratum_popups.set(True)
            self.before_leave.set(True)
            self.known_pois_on_arrival.set(True)
            self.arrival_discovery_status.set(False)
            self.edsm_enabled.set(False)
            self.generic_notify.set(True)
            self.folder.set(str(DEFAULT_JOURNAL)); self.auto_start_monitoring.set(False)
            self.popup_auto_close.set(True); self.popup_timeout.set(15)
            self.popup_above_game.set(True)
            self.popup_sound.set(True)
            self.popup_monitor.set('Main monitor')
            self.windows_notification_mode.set(WINDOWS_DEFAULT_NOTIFICATION_MODE)
            self.popup_test_choice.set(POPUP_TEST_SCENARIOS[0])
            self.search.set(''); self.level_filter.set('All levels'); self.finding_type_filter.set('All findings')
            for variable in self.quick_signal_vars.values(): variable.set(True)
            self.clear_events(); self.displayed_events=0
            self.latest_alert_findings=[]; self.latest_alert_time=None; self.update_home_alert_panel([])
            self.live_heading.set('Current system: waiting for journal data')
            self.live_stats.set('No live session data.')
            self.live_advice.set('Suggested follow-up: Start monitoring to begin a fresh session.')
            self.visit_intelligence.set('No confirmed system visit yet.')
            self.refresh(); self.refresh_explorer()
            self.refresh_historical(); self.refresh_signal_catalog(); self.refresh_generic_signals()
            self.active_journal.set('None'); self.event_count.set('0 events received')
            self.last_event.set('No events received'); self.journal_error.set('No errors')
            self.monitor_status.set('Stopped - fresh database will be created when monitoring starts')
            self.status.set('All Discovery Watch data deleted. Ready to start fresh.')
            self.current_summary.set('Current system: waiting for monitoring data')
            self.home_system.set('Waiting for monitoring'); self.home_known_pois.set('Waiting for location')
            self._set_edsm_disabled_state()
            messagebox.showinfo('Reset complete',
                                'All Discovery Watch data has been deleted. Elite Dangerous journal files were not changed.')
        except (OSError,sqlite3.Error) as exc:
            messagebox.showerror('Reset failed',str(exc))

    def clear_discovery_history_action(self):
        confirmed=messagebox.askyesno(
            'Clear Discovery History?',
            'This removes every finding from the Discovery History tab and clears the latest-alert panel.\n\n'
            'It does not delete Elite Dangerous journals, recorded exploration events, anomalies, settings, '
            'custom rules, watchlists or EDSM cache data.\n\n'
            'The history cannot be restored unless you have made a database backup.\n\n'
            'Clear Discovery History now?',icon='warning',default='no')
        if not confirmed:
            return
        try:
            removed=clear_discovery_history(connection=self.monitor.db) if self.monitor else \
                    clear_discovery_history(DB_PATH)
            if self.monitor:
                self.monitor.popup_findings=[]; self.monitor.popup_metadata=[]
                for visit in self.monitor.contact_visits.values():
                    visit['alert_id']=None
                    visit['popup_sent']=False
                    visit['due_at']=None
            self.latest_alert_findings=[]; self.latest_alert_time=None
            self.update_home_alert_panel([])
            self.search.set(''); self.level_filter.set('All levels'); self.finding_type_filter.set('All findings')
            self.refresh(); self.refresh_live_assistant()
            self.status.set(f'Discovery History cleared: {removed} finding(s) removed.')
            messagebox.showinfo('Discovery History cleared',
                f'{removed} finding(s) removed. Journal files and other Discovery Watch data were not changed.')
        except (OSError,sqlite3.Error) as exc:
            messagebox.showerror('Could not clear Discovery History',str(exc))

    def refresh_live_assistant(self):
        if not self.monitor:
            self.home_system.set('Waiting for monitoring')
            self.home_known_pois.set('Waiting for location')
            return
        summary=self.monitor.live_summary()
        self.home_system.set(summary['system'] or 'Waiting for journal data')
        self.home_known_pois.set(self.monitor.known_poi_overview_text(summary['system']))
        self.live_heading.set('Current system: '+(summary['system'] or 'waiting for journal data'))
        self.live_stats.set(f"Scans: {summary['scans']}  |  Maps: {summary['maps']}  |  Signal events: {summary['signals']}  |  Anomalies: {summary['anomalies']}  |  Completion: {summary['complete']}")
        self.current_summary.set('Current system: ' + (summary['system'] or 'waiting') +
                                 f"  |  Findings: {summary['findings']}  |  Anomalies: {summary['anomalies']}" +
                                 f"  |  Unresolved contacts: {summary['unresolved']}  |  FSS: {summary['complete']}")
        self.live_advice.set('Suggested follow-up: '+'  '.join(summary['suggestions']))

    def update_home_alert_panel(self,findings,received_at=None):
        """Mirror the newest popup information on Home, even when popups are disabled."""
        if findings:
            self.latest_alert_findings=list(findings)
            self.latest_alert_time=received_at or datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')
        shown=self.latest_alert_findings
        self.home_alert_text.configure(state='normal')
        self.home_alert_text.delete('1.0','end')
        if not shown:
            self.home_alert_heading.set('No discovery alerts yet')
            self.home_alert_received.set('No alert received this session')
            self.home_alert_text.insert('end','New popup-eligible discoveries will appear here.\n\n'
                                        'The information remains available after the popup closes.', 'detail')
        else:
            count=len(shown)
            self.home_alert_heading.set('Latest alert' if count==1 else f'Latest alert group - {count} findings')
            self.home_alert_received.set('Last alert received: '+str(self.latest_alert_time or 'Unknown time'))
            for index,(title,system,detail) in enumerate(shown):
                if index:
                    self.home_alert_text.insert('end','\n'+'-'*72+'\n\n','detail')
                self.home_alert_text.insert('end',popup_attention_label(title)+'\n','importance')
                self.home_alert_text.insert('end',(title or 'Discovery update')+'\n','title')
                self.home_alert_text.insert('end','SYSTEM  '+(system or 'Unknown system')+'\n\n','system')
                self.home_alert_text.insert('end',(detail or 'Journal evidence recorded.')+'\n','detail')
        self.home_alert_text.configure(state='disabled')
        self.home_alert_text.yview_moveto(0)

    def refresh_historical(self):
        self.historical_table.delete(*self.historical_table.get_children()); self.historical_rows.clear()
        view_monitor=self.monitor or self._startup_monitor
        if view_monitor:
            rows=view_monitor.historical_search(self.history_search.get(),self.history_event.get(),self.history_from.get(),self.history_to.get())
            sessions=view_monitor.historical_sessions()
        elif DB_PATH.exists():
            with Monitor(self.folder.get(),create_session=False) as monitor:
                rows=monitor.historical_search(self.history_search.get(),self.history_event.get(),self.history_from.get(),self.history_to.get()); sessions=monitor.historical_sessions()
        else: rows=[]; sessions=[]
        for row in rows:
            item=self.historical_table.insert('', 'end',values=row[:6]); self.historical_rows[item]=row
        self.history_status.set(f'{len(rows)} matching events displayed from {len(sessions)} journal session/file(s).')

    def show_historical_event(self,_event=None):
        selected=self.historical_table.selection()
        if not selected: return
        row=self.historical_rows[selected[0]]
        window=self.create_detail_window('Historical journal evidence')
        text=tk.Text(window,wrap='word'); text.pack(fill='both',expand=True)
        text.insert('1.0',f'Session/file: {row[4]}\nLine: {row[5]}\n\n'+json.dumps(json.loads(row[6]),indent=2,ensure_ascii=False)); text.configure(state='disabled')

    def refresh_signal_catalog(self):
        self.signal_table.delete(*self.signal_table.get_children()); self.signal_rows.clear()
        view_monitor=self.monitor or self._startup_monitor
        if view_monitor: rows=view_monitor.signal_catalog()
        elif DB_PATH.exists():
            with Monitor(self.folder.get(),create_session=False) as monitor: rows=monitor.signal_catalog()
        else: rows=[]
        query=self.advanced_rule_search.get().casefold().strip()
        for row in rows:
            if row[0] in self.quick_signal_vars:
                self.quick_signal_vars[row[0]].set(row[2]=='alert')
            policy_label=notification_behaviour(row[2],bool(row[4]))
            if query and query not in ' '.join(str(value or '') for value in (*row,policy_label)).casefold():
                continue
            item=self.signal_table.insert('', 'end',values=(row[1],policy_label,row[3],'Yes' if row[4] else 'No',row[7],row[5] or '',row[6] or '',row[8] or '',row[9] or ''))
            self.signal_rows[item]=row

    def select_signal_rule(self,_event=None):
        selected=self.signal_table.selection()
        if not selected: return
        row=self.signal_rows[selected[0]]; self.signal_priority.set(row[3]); self.signal_popup.set(bool(row[4]))

    def set_selected_signal_policy(self,policy):
        selected=self.signal_table.selection()
        if not selected: return
        key=self.signal_rows[selected[0]][0]
        if self.monitor: self.monitor.set_signal_policy(key,policy,self.signal_priority.get(),self.signal_popup.get())
        else:
            with Monitor(self.folder.get()) as monitor: monitor.set_signal_policy(key,policy,self.signal_priority.get(),self.signal_popup.get())
        self.refresh_signal_catalog()

    def refresh_generic_signals(self):
        self.generic_table.delete(*self.generic_table.get_children()); self.generic_rows.clear()
        view_monitor=self.monitor or self._startup_monitor
        if view_monitor:
            rows=view_monitor.generic_signals(); notify=view_monitor.generic_notify_once()
        elif DB_PATH.exists():
            with Monitor(self.folder.get(),create_session=False) as monitor:
                rows=monitor.generic_signals(); notify=monitor.generic_notify_once()
        else: rows=[]; notify=True
        self.generic_notify.set(notify)
        query=self.advanced_rule_search.get().casefold().strip()
        for row in rows:
            if query and query not in ' '.join(str(value or '') for value in row).casefold():
                continue
            item=self.generic_table.insert('', 'end',values=(row[1],row[2],row[3],row[4],row[13],row[5],row[6],row[7],row[9] or '',row[11] or ''))
            self.generic_rows[item]=row

    def select_generic_rule(self,_event=None):
        selected=self.generic_table.selection()
        if not selected: return
        row=self.generic_rows[selected[0]]
        self.generic_match.set(row[4]); self.generic_popup.set(row[5]); self.generic_priority.set(row[6]); self.generic_pattern.set(row[13])

    def set_selected_generic_rule(self,policy):
        selected=self.generic_table.selection()
        if not selected: return
        signature=self.generic_rows[selected[0]][0]
        try:
            if self.monitor:
                self.monitor.set_generic_rule(signature,policy,self.generic_match.get(),self.generic_popup.get(),self.generic_priority.get(),self.generic_pattern.get())
            else:
                with Monitor(self.folder.get()) as monitor:
                    monitor.set_generic_rule(signature,policy,self.generic_match.get(),self.generic_popup.get(),self.generic_priority.get(),self.generic_pattern.get())
        except (ValueError,sqlite3.Error) as exc:
            messagebox.showerror('Rule not saved',str(exc)); return
        self.refresh_generic_signals()

    def save_generic_notify(self):
        if self.monitor: self.monitor.generic_notify_once(self.generic_notify.get())
        elif DB_PATH.exists():
            with Monitor(self.folder.get()) as monitor: monitor.generic_notify_once(self.generic_notify.get())

    def change_alert(self,status):
        selected=self.table.selection()
        if not selected: return
        for item in selected:
            alert_id=self.rows[item][0]
            if self.monitor: self.monitor.update_alert(alert_id,status=status)
            else:
                with Monitor(self.folder.get()) as monitor: monitor.update_alert(alert_id,status=status)
        self.refresh()

    def edit_alert_note(self):
        selected=self.table.selection()
        if not selected: return
        row=self.rows[selected[0]]
        window=self.create_detail_window('Alert note','520x260')
        text=tk.Text(window,wrap='word'); text.pack(fill='both',expand=True,padx=8,pady=8); text.insert('1.0',row[9] or '')
        def save():
            note=text.get('1.0','end').strip()
            if self.monitor: self.monitor.update_alert(row[0],notes=note)
            else:
                with Monitor(self.folder.get()) as monitor: monitor.update_alert(row[0],notes=note)
            window.destroy(); self.refresh()
        ttk.Button(window,text='Save note',command=save).pack(pady=(0,8))

    def export_selected_alerts(self):
        selected=self.table.selection()
        if not selected: return
        destination=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('JSON files','*.json'),('CSV files','*.csv')])
        if not destination: return
        format='csv' if destination.lower().endswith('.csv') else 'json'; ids=[self.rows[item][0] for item in selected]
        if self.monitor: count=self.monitor.export_selected_alerts(ids,destination,format)
        else:
            with Monitor(self.folder.get()) as monitor: count=monitor.export_selected_alerts(ids,destination,format)
        messagebox.showinfo('Export complete',f'Exported {count} selected alert(s).')

    def select_system(self, _event=None):
        selected = self.system_table.selection()
        if not selected:
            return
        system = self.system_table.item(selected[0], 'values')[0]
        self.detail_table.delete(*self.detail_table.get_children())
        self.exploration_rows.clear()
        if self.monitor:
            rows = self.monitor.system_details(system)
        else:
            with Monitor(self.folder.get()) as monitor:
                rows = monitor.system_details(system)
        for row in rows:
            item = self.detail_table.insert('', 'end', values=row[:4])
            self.exploration_rows[item] = row

    def show_exploration_detail(self, _event=None):
        selected = self.detail_table.selection()
        if not selected or selected[0] not in self.exploration_rows:
            return
        row = self.exploration_rows[selected[0]]
        window=self.create_detail_window('Exploration journal evidence')
        text = tk.Text(window,wrap='word'); text.pack(fill='both',expand=True)
        text.insert('1.0',f'Journal: {row[5]}\nLine: {row[6]}\n\n' +
                    json.dumps(json.loads(row[4]),indent=2,ensure_ascii=False))
        text.configure(state='disabled')

    def export_exploration(self, format):
        destination = filedialog.asksaveasfilename(defaultextension='.'+format,
                                                   filetypes=[(format.upper()+' files','*.'+format)])
        if not destination:
            return
        try:
            if self.monitor:
                count = self.monitor.export_exploration(destination,format)
            else:
                with Monitor(self.folder.get()) as monitor:
                    count = monitor.export_exploration(destination,format)
            messagebox.showinfo('Export complete',f'Exported {count} exploration events.')
        except (OSError,sqlite3.Error,ValueError) as exc:
            messagebox.showerror('Export failed',str(exc))

    def browse(self):
        folder = filedialog.askdirectory(initialdir=self.folder.get() if Path(self.folder.get()).exists() else str(Path.home()))
        if folder:
            self.folder.set(folder)
            self.saved_folder_unavailable=False
            self.save_interface_settings()
            self.status.set('Journal folder remembered. Click Start monitoring when ready.')

    def save_detection_filters(self):
        try:
            save_detection_preferences(self.mega.get(),self.installations.get(),self.unresolved.get())
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_general_alert_settings(self):
        try:
            save_general_alert_preferences(self.phenomena.get(),self.unusual.get(),self.popup.get())
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_anomaly_alert_setting(self):
        try:
            save_anomaly_alert_preference(self.anomaly_alerts.get())
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_exploration_criteria_settings(self):
        try:
            save_exploration_criteria_preferences(
                {rule:variable.get() for rule,variable in self.exploration_criteria_vars.items()})
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_planetary_mining_popup_setting(self):
        try:
            save_planetary_mining_popup_preference(self.planetary_mining_popups.get())
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_surface_signal_popup_settings(self):
        try:
            save_surface_signal_popup_preferences(
                {category:variable.get() for category,variable in self.surface_popup_vars.items()})
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_stratum_popup_setting(self):
        try:
            save_stratum_popup_preference(self.stratum_popups.get())
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_before_leave_setting(self):
        try:
            save_before_leave_preference(self.before_leave.get())
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_popup_above_game_setting(self):
        try:
            save_popup_above_game_preference(self.popup_above_game.get())
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_popup_sound_setting(self):
        try:
            save_popup_sound_preference(self.popup_sound.get())
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_popup_monitor_setting(self):
        try:
            save_popup_monitor_preference(self.popup_monitor.get())
        except (sqlite3.Error,ValueError) as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_popup_appearance_setting(self):
        try:
            save_popup_appearance_preferences(self.popup_position_choice.get(),
                                              self.popup_font_choice.get())
        except (sqlite3.Error,ValueError) as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_windows_notification_mode_setting(self):
        try:
            save_windows_notification_mode_preference(self.windows_notification_mode.get())
        except (sqlite3.Error,ValueError) as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def _audit_popup_delivery(self,method,result,findings,source,detail=''):
        try:
            record_notification_delivery(method,result,findings,source,detail)
        except (OSError,sqlite3.Error,ValueError):
            pass

    def _start_next_windows_overlay(self,fallback_on_failure=False):
        """Launch one queued overlay and wait for its lifetime before the next."""
        if self.windows_overlay_active or not self.windows_overlay_queue:
            return True
        item=self.windows_overlay_queue.popleft()
        shown=send_windows_overlay(self,item['findings'],item['metadata'],item['timeout'],
                                   item['monitor'],position=item['position'],font_size=item['font_size'])
        if not shown:
            if fallback_on_failure:
                error=windows_overlay_error_details()['message']
                self._audit_popup_delivery('Windows game overlay','failed',item['findings'],
                                           item['source'],error)
                self.show_alert_popup(item['findings'],item['metadata'],item['source'],
                                      allow_windows_overlay=False)
                self.after(50,lambda:self._start_next_windows_overlay(True))
            return False
        self.windows_overlay_active=True
        if self.popup_sound.get():
            play_alert_sound(self)
        self._audit_popup_delivery('Windows game overlay','launched',item['findings'],item['source'])
        self.status.set('Windows game overlay displayed without taking focus from Elite.')
        delay_ms=(item['timeout']*1000)+350
        self.windows_overlay_timer=self.after(delay_ms,self._finish_windows_overlay)
        return True

    def _finish_windows_overlay(self):
        self.windows_overlay_active=False
        self.windows_overlay_timer=None
        self._start_next_windows_overlay(True)

    def _queue_windows_overlay(self,findings,metadata,timeout,monitor,source):
        """Queue Windows overlays so rapid journal events remain readable."""
        duration=max(5,min(60,int(timeout or 15)))
        position_var=self.__dict__.get('popup_position_choice')
        font_var=self.__dict__.get('popup_font_choice')
        self.windows_overlay_queue.append({
            'findings':list(findings),
            'metadata':list(metadata or []),
            'timeout':duration,
            'monitor':monitor,
            'position':position_var.get() if position_var else 'Bottom right',
            'font_size':font_var.get() if font_var else 'Normal',
            'source':source,
        })
        if self.windows_overlay_active:
            self.status.set('Discovery alert queued behind the current Windows overlay.')
            return True
        return self._start_next_windows_overlay(False)

    def show_alert_popup(self,findings,metadata=None,source='Live journal',allow_windows_overlay=True):
        """Create an alert without allowing a GUI failure to stop journal polling."""
        if metadata is None:
            metadata=getattr(self.monitor,'popup_metadata',None) if self.monitor else None
        findings,metadata=simplify_popup_content(findings,metadata)
        if not findings:
            return None
        native_timeout=self.popup_timeout.get() if self.popup_auto_close.get() else 0
        windows_mode=self.windows_notification_mode.get()
        if (platform.system()=='Windows' and not allow_windows_overlay and
                windows_mode==WINDOWS_NOTIFICATION_MODES[1]):
            windows_mode=WINDOWS_NOTIFICATION_MODES[0]
        if (allow_windows_overlay and platform.system()=='Windows' and
                windows_mode==WINDOWS_NOTIFICATION_MODES[1]):
            if self._queue_windows_overlay(findings,metadata,native_timeout,
                                           self.popup_monitor.get(),source):
                return None
            error=windows_overlay_error_details()['message']
            self._audit_popup_delivery('Windows game overlay','failed',findings,source,error)
            self.status.set('Windows game overlay could not start; trying a native Windows notification.')
            windows_mode=WINDOWS_NOTIFICATION_MODES[0]
        if platform.system()=='Windows' and windows_mode==WINDOWS_NOTIFICATION_MODES[0]:
            windows_result=send_windows_notification(findings,metadata,native_timeout,widget=self)
            if windows_result:
                if self.popup_sound.get(): play_alert_sound(self)
                if isinstance(windows_result,dict):
                    cleanup_seconds=max(20,int(native_timeout or 15)+5)
                    self.after(cleanup_seconds*1000,
                               lambda token=windows_result:close_windows_notification(token))
                    method=windows_result.get('method','Native Windows notification')
                else:
                    method='PowerShell toast fallback'
                self._audit_popup_delivery(method,'launched',findings,source)
                self.status.set(f'{method} displayed without taking game focus.')
                return None
            self._audit_popup_delivery('Native Windows notification','failed',findings,source,
                                       'Windows notification delivery was unavailable')
            self.status.set('Native Windows notification was unavailable; using the Discovery Watch popup.')
        native_result=send_native_notification(findings,metadata,native_timeout) if is_wayland_session() else False
        if native_result:
            if self.popup_sound.get(): play_alert_sound(self)
            self._audit_popup_delivery('Native Wayland notification','launched',findings,source)
            if self.popup_auto_close.get() and isinstance(native_result,int) and not isinstance(native_result,bool):
                self.after(max(1,self.popup_timeout.get())*1000,
                           lambda notification_id=native_result:close_native_notification(notification_id))
                self.status.set(f'Wayland notification displayed; closes in {self.popup_timeout.get()} seconds.')
            elif self.popup_auto_close.get():
                self.status.set('Wayland notification displayed; desktop controls its final dismissal.')
            else:
                self.status.set('Wayland notification displayed; automatic closing is disabled.')
            return None
        try:
            popup=AlertPopup(self,findings,self.popup_timeout.get(),
                             self.popup_auto_close.get(),self.open_discovery_history,
                             keep_above=self.popup_above_game.get(),
                             play_sound=self.popup_sound.get(),
                             monitor_choice=self.popup_monitor.get(),
                             metadata=metadata,position=self.popup_position_choice.get(),
                             font_size=self.popup_font_choice.get())
            self._audit_popup_delivery('Discovery Watch popup','launched',findings,source)
            return popup
        except tk.TclError as exc:
            message=f'Popup could not be displayed: {exc}'
            self._audit_popup_delivery('Discovery Watch popup','failed',findings,source,str(exc))
            self.journal_error.set(message)
            self.status.set(message)
            return None

    def test_notification(self):
        findings,metadata=popup_test_scenario(self.popup_test_choice.get())
        self.show_alert_popup(findings,metadata,source='Popup test')

    def show_popup_diagnostics(self):
        info=popup_diagnostics(self,self.popup_monitor.get(),self.popup_auto_close.get(),
                               self.popup_timeout.get(),self.popup_above_game.get(),
                               self.popup_sound.get(),windows_mode=self.windows_notification_mode.get())
        info['delivery_audit']=notification_delivery_summary()
        lines=[f'{key.replace("_"," ").title()}: {value}' for key,value in info.items()]
        messagebox.showinfo('Popup diagnostics','\n'.join(lines))

    def show_windows_overlay_error(self):
        details=windows_overlay_error_details()
        if not details['present']:
            messagebox.showinfo('Windows overlay error log',details['message']+'\n\n'+details['path'])
            return
        window=self.create_detail_window('Windows overlay error log','720x420')
        text=tk.Text(window,wrap='word'); text.pack(fill='both',expand=True,padx=8,pady=8)
        text.insert('1.0',f"File: {details['path']}\n\n{details['message']}")
        text.configure(state='disabled')

    def save_known_poi_arrival_setting(self):
        try:
            save_known_poi_arrival_preference(self.known_pois_on_arrival.get())
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_arrival_discovery_status_setting(self):
        try:
            save_arrival_discovery_status_preference(self.arrival_discovery_status.get())
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc))

    def save_edsm_setting(self):
        try:
            save_edsm_enabled_preference(self.edsm_enabled.get())
        except sqlite3.Error as exc:
            messagebox.showerror('Setting not saved',str(exc)); return
        if not self.edsm_enabled.get():
            self._set_edsm_disabled_state()
        elif self.monitor and self.monitor.current_system:
            self.request_edsm_lookup(self.monitor.current_system)
        else:
            self.edsm_status.set('EDSM enabled - waiting for a confirmed arrival.')
            self.edsm_details.set('No network request has been made yet.')
            self.edsm_leads.set('Possible leads: none evaluated.')

    def _set_edsm_disabled_state(self):
        self.edsm_current_system=None
        self.edsm_status.set('EDSM disabled - enable it in Settings to add community context.')
        self.edsm_details.set('Offline journal intelligence remains fully available.')
        self.edsm_leads.set('Possible leads: none evaluated.')
        self.edsm_open_button.configure(state='disabled')

    def request_edsm_lookup(self,system):
        system=str(system or '').strip()
        if not self.edsm_enabled.get() or not system or not self.monitor:
            return
        self.edsm_current_system=system
        self.edsm_open_button.configure(state='normal')
        cached=self.monitor.edsm_cache_entry(system)
        if cached:
            self._display_edsm_result(system,cached['payload'],cached=True,stale=cached['stale'])
            if not cached['stale']:
                return
        if system.casefold() in self.edsm_inflight:
            return
        self.edsm_inflight.add(system.casefold())
        self.edsm_status.set(('Refreshing stale EDSM cache for ' if cached else 'Looking up EDSM data for ')+system+'...')
        def worker():
            try: self.edsm_results.put((system,fetch_edsm_system(system),None))
            except Exception as exc: self.edsm_results.put((system,None,str(exc)))
        threading.Thread(target=worker,name='DiscoveryWatch-EDSM',daemon=True).start()

    def _drain_edsm_results(self):
        try:
            while True:
                system,result,error=self.edsm_results.get_nowait()
                self.edsm_inflight.discard(system.casefold())
                if result and self.monitor:
                    self.monitor.save_edsm_cache(system,result)
                if system!=self.edsm_current_system or not self.edsm_enabled.get():
                    continue
                if result:
                    self._display_edsm_result(system,result,cached=False,stale=False)
                else:
                    cached=self.monitor.edsm_cache_entry(system) if self.monitor else None
                    if cached:
                        self._display_edsm_result(system,cached['payload'],cached=True,stale=True,error=error)
                    else:
                        self.edsm_status.set(f'EDSM unavailable for {system}')
                        self.edsm_details.set('Lookup failed. Offline journal monitoring is unaffected. '+(error or ''))
                        self.edsm_leads.set('Possible leads: unavailable until community data can be retrieved.')
        except queue.Empty:
            pass
        try: self.after(250,self._drain_edsm_results)
        except tk.TclError: pass

    def _display_edsm_result(self,system,result,cached=False,stale=False,error=None):
        status=result.get('status')
        fetched=result.get('fetched_at') or 'unknown time'
        source='Cached EDSM' if cached else 'EDSM'
        if stale: source='Stale cached EDSM'
        self.edsm_status.set(f'{source} intelligence for {system} - updated {fetched}')
        self.edsm_open_button.configure(state='normal')
        if status=='not_found':
            self.edsm_details.set('System not found in the returned EDSM catalogue. Local journal data remains authoritative for this app.')
            self.edsm_leads.set('Possible lead: community catalogue coverage may be incomplete.')
            return
        body_data=result.get('body_data') or {}
        bodies=body_data.get('bodies') if isinstance(body_data.get('bodies'),list) else []
        expected=body_data.get('bodyCount')
        expected_text=str(expected) if isinstance(expected,(int,float)) and not isinstance(expected,bool) else 'unknown'
        local_names=self.monitor.local_body_names(system) if self.monitor else []
        catalogue='complete' if isinstance(expected,(int,float)) and expected<=len(bodies) else 'incomplete or unknown'
        info=result.get('system_info') or {}; primary=info.get('primaryStar') or {}
        primary_text=str(primary.get('type') or primary.get('name') or 'unknown') if isinstance(primary,dict) else 'unknown'
        partial_errors=result.get('partial_errors') or []
        self.edsm_details.set(f'EDSM bodies: {len(bodies)} detailed / {expected_text} reported | '
                              f'Local recorded bodies: {len(local_names)} | Catalogue: {catalogue} | Primary star: {primary_text}' +
                              (f' | Partial lookup warning: {"; ".join(partial_errors)}' if partial_errors else '') +
                              (f' | Refresh error: {error}' if error else ''))
        leads=score_edsm_leads(result,local_names)
        if leads:
            self.edsm_leads.set('Possible leads (inferred, verify in game): '+
                                '  |  '.join(f'[{score}] {title}: {explanation}' for score,title,explanation in leads[:4]))
        else:
            self.edsm_leads.set('Possible leads: none supported by the available local/EDSM comparison.')

    def open_current_edsm(self):
        system=self.edsm_current_system or (self.monitor.current_system if self.monitor else None)
        if system:
            webbrowser.open(edsm_system_url(system),new=2)

    def run_journal_replay(self):
        if self.replay_running:
            messagebox.showinfo('Replay already running','Wait for the current journal replay test to finish.')
            return
        paths=filedialog.askopenfilenames(title='Choose copied Elite Dangerous journal files',
                                          filetypes=[('Elite journal logs','Journal.*.log'),('Log files','*.log'),('All files','*')])
        if not paths: return
        self.replay_running=True
        self.status.set(f'Replay testing {len(paths)} journal file(s) in an isolated temporary database...')
        def worker():
            try: self.replay_results.put((replay_journal_paths(paths),None))
            except Exception as exc: self.replay_results.put((None,str(exc)))
        threading.Thread(target=worker,name='DiscoveryWatch-Replay',daemon=True).start()

    def run_builtin_reliability_check(self):
        try:
            report=run_reliability_self_check()
            checks='\n'.join(f"{'PASS' if passed else 'FAIL'} - {name.replace('_',' ')}"
                             for name,passed in report['checks'].items())
            messagebox.showinfo('Built-in reliability check',
                f"Overall: {'PASS' if report['passed'] else 'FAIL'}\n\n{checks}\n\n"
                f"Events: {report['events']}\nFindings: {report['findings']}\n"
                f"Potential popups: {report['potential_popups']}\n"
                f"Duplicates suppressed: {report['duplicates_suppressed']}\n\n"
                f"{report['isolation_note']}")
            self.status.set('Built-in reliability check passed.' if report['passed'] else
                            'Built-in reliability check found a failure; review the results.')
        except (OSError,sqlite3.Error,ValueError) as exc:
            messagebox.showerror('Reliability check failed',str(exc))

    def run_settings_behaviour_check(self):
        try:
            report=run_settings_behaviour_check()
            window=self.create_detail_window('Settings behaviour check','820x620')
            text=tk.Text(window,wrap='word')
            text.pack(fill='both',expand=True,padx=8,pady=8)
            checks='\n'.join(f"{'PASS' if passed else 'FAIL'} - {name.replace('_',' ')}"
                             for name,passed in report['checks'].items())
            matrix='\n'.join(f'{control}\n  Scope: {scope}\n  Record: {record}\n'
                             f'  Investigation: {lead}\n  Popup: {popup}'
                             for control,scope,record,lead,popup in SETTINGS_BEHAVIOUR)
            text.insert('1.0',f"Overall: {'PASS' if report['passed'] else 'FAIL'}\n\n"
                        f'{checks}\n\nDocumented Settings behaviour '
                        f"({report['controls_documented']} controls)\n\n{matrix}\n\n"
                        f"{report['isolation_note']}")
            text.configure(state='disabled')
            self.status.set('Settings behaviour check passed.' if report['passed'] else
                            'Settings behaviour check found a failure; review the results.')
        except (OSError,sqlite3.Error,ValueError) as exc:
            messagebox.showerror('Settings behaviour check failed',str(exc))

    def _drain_replay_results(self):
        try:
            while True:
                report,error=self.replay_results.get_nowait()
                self.replay_running=False
                if error:
                    self.status.set('Journal replay test failed.')
                    messagebox.showerror('Replay test failed',error)
                else:
                    self.status.set(f"Replay complete: {report['events']} events, {report['findings']} findings, {report['anomalies']} anomalies.")
                    self.show_replay_report(report)
        except queue.Empty:
            pass
        try: self.after(250,self._drain_replay_results)
        except tk.TclError: pass

    def show_replay_report(self,report):
        window=self.create_detail_window('Isolated journal replay report','760x620')
        summary=(f"Files: {report['files']}\nEvents: {report['events']}\nSystems: {report['systems']}\n"
                 f"Findings: {report['findings']}\nPotential popups: {report['potential_popups']}\n"
                 f"Duplicate findings suppressed: {report['duplicate_findings_suppressed']}\n"
                 f"Anomalies: {report['anomalies']}\nUnknown-system findings: {report['unknown_system_findings']}\n"
                 f"Read/JSON errors: {report['invalid_or_read_errors']}\n\n"
                 f"{report['isolation_note']}\n\nComplete report\n\n"+
                 json.dumps(report,indent=2,ensure_ascii=False))
        text=tk.Text(window,wrap='word'); text.pack(fill='both',expand=True,padx=8,pady=8)
        text.insert('1.0',summary); text.configure(state='disabled')
        def save():
            destination=filedialog.asksaveasfilename(defaultextension='.json',
                initialfile=f'discovery-watch-v{APP_VERSION}-replay-report.json',
                filetypes=[('JSON files','*.json')])
            if destination:
                with Path(destination).open('w',encoding='utf-8') as output:
                    json.dump(report,output,ensure_ascii=False,indent=2)
        ttk.Button(window,text='Save report...',command=save).pack(pady=(0,8))

    def show_first_run_help(self):
        messagebox.showinfo('How Discovery Watch monitoring works',
            '1. Choose the folder containing Elite Dangerous Journal.*.log files.\n\n'
            '2. Click Start monitoring before playing. Existing lines are skipped so old discoveries '
            'do not produce surprise alerts. New journal files are read from their beginning.\n\n'
            '3. Jump, honk and scan normally. Discovery Watch can only report information that Elite '
            'writes to the journal. The optional Experimental contact tracker can remind you to inspect the navigation panel or FSS.\n\n'
            '4. Configure common notifications in Settings > Basic alerts. Advanced matching remains available when needed.\n\n'
            'Home > Journal diagnostics is the quickest way to confirm that live events are arriving.')
        complete_first_run()

    def export_diagnostic_report(self):
        destination=filedialog.asksaveasfilename(defaultextension='.json',
                                                  initialfile=f'discovery-watch-v{APP_VERSION}-diagnostics.json',
                                                  filetypes=[('JSON files','*.json')])
        if not destination:
            return
        try:
            if self.monitor:
                report=self.monitor.diagnostic_report()
            else:
                with Monitor(self.folder.get(),DB_PATH,create_session=False) as monitor:
                    report=monitor.diagnostic_report()
            report['startup_performance']=self.startup_timings
            with Path(destination).open('w',encoding='utf-8') as output:
                json.dump(report,output,ensure_ascii=False,indent=2)
            messagebox.showinfo('Diagnostic report created',
                                'The report contains no raw journal events, but it does contain local paths and settings. Review it before sharing.')
        except (OSError,sqlite3.Error,ValueError) as exc:
            messagebox.showerror('Diagnostic export failed',str(exc))

    def start(self):
        if self.running:
            return
        folder = Path(self.folder.get()).expanduser()
        if not folder.is_dir():
            messagebox.showerror('Journal folder missing', 'Choose the folder containing Journal.*.log files.')
            return
        self.save_interface_settings()
        if self.monitor:
            self.monitor.db.execute('UPDATE live_sessions SET ended_at=? WHERE session_id=?',
                                    (datetime.now().isoformat(timespec='seconds'),self.monitor.session_id))
            self.monitor.db.commit()
            self.monitor.db.close()
        self.monitor = Monitor(folder)
        self.monitor.start_at_end()
        self.running = True
        self.displayed_events = 0
        self.clear_events()
        self.monitor_status.set('Watching - waiting for new journal events')
        self.active_journal.set('Folder: ' + str(folder))
        self.event_count.set('0 events received this session')
        self.last_event.set('No new events yet; start Elite Dangerous or perform an in-game action.')
        self.journal_error.set('No errors')
        self.status.set(f'Monitoring all systems in {folder} - new journal entries only.')
        self.set_activity_state('waiting')
        self.tick()

    def tick(self):
        if not self.running:
            return
        try:
            previous_total=self.monitor.total_events
            findings = self.monitor.poll((self.mega.get(),self.installations.get(),
                                          self.phenomena.get(),self.unusual.get(),self.unresolved.get(),
                                          self.anomaly_alerts.get(),self.known_pois_on_arrival.get(),
                                          self.planetary_mining_popups.get(),
                                          self.surface_popup_vars['thargoid'].get(),
                                          self.surface_popup_vars['guardian'].get(),
                                          self.surface_popup_vars['biological'].get(),
                                          self.surface_popup_vars['other'].get(),
                                          self.stratum_popups.get(),self.before_leave.get(),
                                          self.surface_popup_vars['geological'].get(),
                                          self.surface_popup_vars['human'].get(),
                                          self.arrival_discovery_status.get()))
            for arrived_system in self.monitor.arrived_systems:
                self.request_edsm_lookup(arrived_system)
            if self.monitor.total_events>previous_total:
                self.pulse_journal_activity()
            self.update_journal()
            if self.monitor.total_events != getattr(self, "explorer_last_count", -1):
                self.refresh_explorer()
                self.refresh_live_assistant()
                self.refresh_historical()
                self.refresh_signal_catalog()
                self.refresh_generic_signals()
                self.refresh_cases(); self.refresh_watchlists()
                self.explorer_last_count = self.monitor.total_events
            if findings:
                self.refresh()
            if self.monitor.popup_findings:
                self.update_home_alert_panel(self.monitor.popup_findings)
            if popup_delivery_allowed(self.popup.get(),self.monitor.popup_findings):
                self.show_alert_popup(self.monitor.popup_findings)
        except (OSError, sqlite3.Error) as exc:
            self.stop()
            self.monitor_status.set('Error - monitoring stopped')
            self.journal_error.set(str(exc))
            self.status.set(f'Monitoring stopped: {exc}')
            self.set_activity_state('error')
            return
        if self.running:
            self.after(1000, self.tick)

    def stop(self):
        self.running = False
        self.activity_generation+=1
        if self.monitor:
            self.monitor.db.execute('UPDATE live_sessions SET ended_at=? WHERE session_id=?',
                                    (datetime.now().isoformat(timespec='seconds'),self.monitor.session_id))
            self.monitor.db.commit()
            self.monitor.db.close()
            self.monitor = None
        self.status.set('Stopped.')
        self.current_summary.set('Current system: monitoring stopped')
        self.home_system.set('Monitoring stopped')
        self.home_known_pois.set('Monitoring stopped')
        if self.edsm_enabled.get():
            self.edsm_status.set('EDSM enabled - monitoring stopped.')
            self.edsm_details.set('Cached responses remain stored locally.')
            self.edsm_leads.set('Possible leads: waiting for the next confirmed arrival.')
        self.refresh_explorer()
        self.monitor_status.set('Stopped')
        self.set_activity_state('stopped')

    def update_journal(self):
        monitor = self.monitor
        if not monitor:
            return
        self.event_count.set(f'{monitor.total_events} events received this session')
        files = sorted(monitor.folder.glob('Journal.*.log'))
        self.active_journal.set('Active: ' + (monitor.active_file or 'None yet') + f' | {len(files)} journal file(s) found')
        if monitor.last_received:
            seconds = int((datetime.now() - monitor.last_received).total_seconds())
            self.last_event.set(f'Last received: {monitor.last_received:%Y-%m-%d %H:%M:%S} ({seconds}s ago)')
            self.monitor_status.set('Receiving data' if seconds < 5 else 'Watching - idle (no new events)')
        else:
            self.monitor_status.set('Watching - waiting for new journal events')
        self.journal_error.set(monitor.errors[-1] if monitor.errors else 'No errors')
        for sequence, name, line, event in monitor.events:
            if sequence <= self.displayed_events:
                continue
            item = self.event_table.insert('', 'end', values=(sequence, event.get('timestamp', ''), event.get('event', 'Unknown'), event.get('StarSystem', event.get('System', '')), Path(name).name, line))
            self.event_rows[item] = (name, line, event)
            self.displayed_events = sequence
        while len(self.event_rows) > 2000:
            item = self.event_table.get_children()[0]
            self.event_table.delete(item)
            self.event_rows.pop(item, None)

    def select_event(self, _event):
        selected = self.event_table.selection()
        if not selected or selected[0] not in self.event_rows:
            return
        name, line, event = self.event_rows[selected[0]]
        self.raw_text.configure(state='normal')
        self.raw_text.delete('1.0', 'end')
        self.raw_text.insert('1.0', f'Journal: {name}\nLine: {line}\n\n' + json.dumps(event, indent=2, ensure_ascii=False))
        self.raw_text.configure(state='disabled')

    def clear_events(self):
        for item in self.event_table.get_children():
            self.event_table.delete(item)
        self.event_rows.clear()
        if self.monitor:
            self.displayed_events = self.monitor.total_events
        self.raw_text.configure(state='normal')
        self.raw_text.delete('1.0', 'end')
        self.raw_text.configure(state='disabled')

    def export(self, format):
        destination = filedialog.asksaveasfilename(
            defaultextension='.' + format,
            filetypes=[(format.upper() + ' files', '*.' + format)])
        if not destination:
            return
        try:
            if self.monitor:
                count = self.monitor.export(destination, format)
            else:
                with Monitor(self.folder.get(), DB_PATH) as monitor:
                    count = monitor.export(destination, format)
            messagebox.showinfo('Export complete', f'Exported {count} records.')
        except (OSError, sqlite3.Error, ValueError) as exc:
            messagebox.showerror('Export failed', str(exc))

    def refresh(self):
        for item in self.table.get_children():
            self.table.delete(item)
        self.rows = {}
        view_monitor=self.monitor or self._startup_monitor
        if view_monitor:
            rows = view_monitor.recent()
        else:
            if not DB_PATH.exists():
                self.history_empty.set('No discoveries recorded yet. Start monitoring, enter a system and use the Discovery Scanner.')
                self.home_known_pois.set('Waiting for location')
                return
            # Opening through Monitor applies schema migrations before history is read.
            with Monitor(self.folder.get(), DB_PATH,create_session=False) as monitor:
                rows = monitor.recent()
        query = self.search.get().casefold().strip()
        selected_level=self.level_filter.get()
        selected_type=self.finding_type_filter.get()
        active_rows=[row for row in rows if row[8]!='dismissed']
        if not self.latest_alert_findings:
            latest_popup_row=next((row for row in active_rows
                                   if str(row[12] or '').startswith('Popup eligible')),None)
            if latest_popup_row:
                self.update_home_alert_panel([(latest_popup_row[3],latest_popup_row[2],latest_popup_row[4])],
                                             latest_popup_row[1] or 'Unknown time')
        displayed=0
        for row in rows:
            if query and not any(query in str(value or '').casefold() for value in row):
                continue
            if selected_level!='All levels' and row[10]!=selected_level:
                continue
            category=finding_type(row[13],row[3],row[4])
            if selected_type!='All findings' and category!=selected_type:
                continue
            tags=(row[10],row[8])
            compact_detail=discovery_history_detail_summary(
                row[3],row[4],row[5],row[13])
            item = self.table.insert('', 'end', values=(row[1] or '',row[10],category,row[2] or 'Unknown system',
                                                        row[3],compact_detail,row[8],row[9]),tags=tags)
            self.rows[item] = row
            displayed+=1
        if rows and not displayed:
            self.history_empty.set('No findings match the current search, importance and type filters.')
        elif rows:
            self.history_empty.set(f'{displayed} finding' + ('s' if displayed!=1 else '') + ' displayed. Double-click one for journal evidence.')
        else:
            self.history_empty.set('No discoveries recorded yet. Start monitoring, enter a system and use the Discovery Scanner.')

    def show_detail(self, _event):
        selection = self.table.selection()
        if not selection:
            return
        row = self.rows[selection[0]]
        window=self.create_detail_window(f'Journal evidence #{row[0]}')
        actions=ttk.Frame(window,padding=(8,4))
        actions.pack(side='bottom',fill='x')
        text = tk.Text(window, wrap='word')
        text.pack(fill='both', expand=True)
        try: event=json.loads(row[5])
        except (TypeError,ValueError): event={}
        ttk.Button(actions,text='Show raw journal data',
                   command=lambda:self.show_raw_journal_data(event,row[0])).pack(side='left')
        ttk.Button(actions,text='Close',command=window.destroy).pack(side='right')
        anomaly_details=''
        if row[13]=='ANOMALY_ALERT' and isinstance(event,dict):
            detected=detect_anomalies(event)
            if detected:
                lines=[f'- {rule} ({score}): {explanation} [evidence: {field}]'
                       for rule,score,explanation,field in detected]
                anomaly_details='Individual anomaly rules\n'+'\n'.join(lines)+'\n\n'
        text.insert('1.0',f'Why this finding exists\nFinding type: {finding_type(row[13],row[3],row[4])}\n'
                    f'{policy_explanation(row[13],row[3],row[4])}\n'
                    f'Rule detail: {row[4]}\nSource: {row[11]}\nNotification: {row[12]}\n\n'
                    f'{anomaly_details}Journal: {row[6]}\nLine: {row[7]}\n\n'
                    f'Journal event\n{journal_evidence_summary(event)}\n\n'
                    'The complete original event remains stored. Use Show raw journal data '
                    'for the full JSON evidence.')
        text.configure(state='disabled')

    def show_raw_journal_data(self,event,alert_id=None):
        """Open the complete immutable journal event on explicit request."""
        suffix=f' #{alert_id}' if alert_id is not None else ''
        window=self.create_detail_window('Raw journal data'+suffix)
        text=tk.Text(window,wrap='none')
        y_scroll=ttk.Scrollbar(window,orient='vertical',command=text.yview)
        x_scroll=ttk.Scrollbar(window,orient='horizontal',command=text.xview)
        text.configure(yscrollcommand=y_scroll.set,xscrollcommand=x_scroll.set)
        y_scroll.pack(side='right',fill='y'); x_scroll.pack(side='bottom',fill='x')
        text.pack(fill='both',expand=True)
        text.insert('1.0',json.dumps(event if isinstance(event,dict) else {},
                                    indent=2,ensure_ascii=False))
        text.configure(state='disabled')

    def close(self):
        self.stop()
        self.destroy()


if __name__ == '__main__':
    if len(sys.argv)>=3 and sys.argv[1]=='--windows-overlay':
        raise SystemExit(run_windows_overlay(decode_windows_overlay_payload(sys.argv[2])))
    App().mainloop()
