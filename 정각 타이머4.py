# 정각 알림이 프로그램 - 버전 2.0.0 Modern UI
# 모던 UI, 스누즈 기능, 10초 자동 닫힘, 로깅 기능

import time
import threading
import datetime
import sys
import os
import winsound
from tkinter import Tk, Label, Button, Toplevel, Frame, Canvas, Text, Scrollbar
from tkinter import ttk
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

# 모던 컬러 테마
COLORS = {
    'bg': '#1a1a2e',           # 다크 네이비
    'surface': '#16213e',      # 어두운 파란색
    'surface_light': '#0f3460',# 밝은 파란색
    'primary': '#00d4ff',      # 시안 블루
    'primary_hover': '#00b8e6',# 시안 블루 호버
    'accent': '#ff6b6b',       # 레드
    'accent_hover': '#ff5252', # 레드 호버
    'success': '#51cf66',      # 그린
    'warning': '#ffd93d',      # 옐로우
    'text': '#e8e8e8',         # 밝은 회색
    'text_dim': '#a0a0a0',     # 어두운 회색
    'snooze': '#9d4edd',       # 보라색
    'snooze_hover': '#7b2cbf', # 보라색 호버
}

# 전역 변수
running = True
tray_icon = None
status_label = None
time_label = None
root = None
pinned = True

# 경로 설정
STARTUP_DIR = os.path.join(os.getenv('APPDATA'),
    'Microsoft\\Windows\\Start Menu\\Programs\\Startup')
STARTUP_FILE = os.path.join(STARTUP_DIR, '정각 타이머.bat')

# 실행 경로 설정 (EXE 지원)
if getattr(sys, 'frozen', False):
    SCRIPT_PATH = sys.executable
else:
    SCRIPT_PATH = os.path.abspath(__file__)

LOG_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), 'alarm_log.txt')

# 전역 변수
auto_starting = os.path.exists(STARTUP_FILE)
skip_until = None
active_popup = None
auto_close_timer = None

# ------------------- 로깅 함수 ------------------- #

def write_log(message):
    """로그 파일에 타임스탬프와 함께 메시지 기록"""
    try:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f'{timestamp} - {message}\n')
    except Exception as e:
        print(f'로그 기록 실패: {e}')

# ------------------- UI 헬퍼 함수 ------------------- #

class ModernButton(Canvas):
    """모던 스타일의 커스텀 버튼"""
    def __init__(self, parent, text, command, bg_color, hover_color, 
                 text_color=COLORS['text'], width=200, height=50, font_size=14):
        super().__init__(parent, width=width, height=height, 
                        bg=COLORS['bg'], highlightthickness=0)
        
        self.command = command
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.text = text
        self.font_size = font_size
        
        self.rect = self.create_rectangle(0, 0, width, height, 
                                          fill=bg_color, outline='', 
                                          width=0)
        self.text_id = self.create_text(width//2, height//2, 
                                        text=text, fill=text_color,
                                        font=('Segoe UI', font_size, 'bold'))
        
        self.bind('<Enter>', self.on_enter)
        self.bind('<Leave>', self.on_leave)
        self.bind('<Button-1>', self.on_click)
    
    def on_enter(self, e):
        self.itemconfig(self.rect, fill=self.hover_color)
        self.config(cursor='hand2')
    
    def on_leave(self, e):
        self.itemconfig(self.rect, fill=self.bg_color)
        self.config(cursor='')
    
    def on_click(self, e):
        if self.command:
            self.command()
    
    def update_text(self, new_text):
        self.itemconfig(self.text_id, text=new_text)
    
    def update_colors(self, new_bg_color, new_hover_color):
        """버튼 색상 변경"""
        self.bg_color = new_bg_color
        self.hover_color = new_hover_color
        self.itemconfig(self.rect, fill=new_bg_color)

# ------------------- 기능 함수 ------------------- #

def toggle_autostart():
    """자동실행 설정 토글 - BAT 파일 복사 방식"""
    import shutil
    global auto_starting, auto_btn
    auto_starting = not auto_starting
    if auto_starting:
        # 현재 실행 중인 파일의 경로를 기반으로 BAT 파일 내용 생성
        current_dir = os.path.dirname(os.path.abspath(SCRIPT_PATH))
        script_name = os.path.basename(SCRIPT_PATH)
        
        bat_content = f'@echo off\nchcp 65001 > nul\ncd /d "{current_dir}"\nstart "" "pythonw" "{script_name}"\n'
        
        try:
            with open(STARTUP_FILE, 'w', encoding='utf-8') as f:
                f.write(bat_content)
            
            # 프로젝트 폴더 내의 BAT 파일도 동기화 (선택 사항이지만 일관성을 위해)
            local_bat = os.path.join(current_dir, '정각 타이머.bat')
            with open(local_bat, 'w', encoding='utf-8') as f:
                f.write(bat_content)
                
            auto_btn.update_text('🚀 자동실행 ON')
            auto_btn.update_colors(COLORS['primary'], COLORS['primary_hover'])
            write_log(f'자동실행 ON으로 설정됨 (경로: {current_dir})')
        except Exception as e:
            write_log(f'오류: 자동실행 설정 실패 ({e})')
            auto_starting = False
    else:
        if os.path.exists(STARTUP_FILE):
            os.remove(STARTUP_FILE)
        auto_btn.update_text('🚀 자동실행 OFF')
        auto_btn.update_colors(COLORS['surface_light'], COLORS['primary'])
        write_log('자동실행 OFF로 설정됨')




def draw_icon():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill='#00d4ff')
    d.ellipse((20, 20, 44, 44), fill='#1a1a2e')
    return img


def close_popup_manual(popup):
    """사용자가 직접 닫기 버튼을 눌렀을 때"""
    global active_popup, auto_close_timer
    if auto_close_timer:
        popup.after_cancel(auto_close_timer)
        auto_close_timer = None
    write_log('사용자가 직접 닫음')
    active_popup = None
    popup.destroy()


def close_popup_auto(popup):
    """10초 후 자동으로 닫힐 때"""
    global active_popup, auto_close_timer
    write_log('10초 후 자동 닫힘')
    auto_close_timer = None
    active_popup = None
    popup.destroy()


def skip_alarm(popup, hours):
    """스킵 기능 - 선택한 시간까지 알림 끄기"""
    global skip_until, active_popup, auto_close_timer
    
    # skip_until 먼저 계산
    skip_until = datetime.datetime.now() + datetime.timedelta(hours=hours)
    
    # 타이머 취소
    if auto_close_timer:
        active_popup.after_cancel(auto_close_timer)
        auto_close_timer = None
    
    # 로그 기록
    write_log(f'알림 스킵 설정 ({hours}시간) - 다음 알림: {skip_until.strftime("%H:%M")}')
    
    # 팝업 닫기
    popup.destroy()  # 스킵 선택 창 닫기
    if active_popup:
        active_popup.destroy()  # 정각 알림창 닫기
    active_popup = None


def show_skip_popup(parent_popup):
    """스킵 시간 선택 팝업"""
    snooze_window = Toplevel(parent_popup)
    snooze_window.title('알림 스킵 시간')
    snooze_window.attributes('-topmost', True)
    snooze_window.configure(bg=COLORS['bg'])
    snooze_window.resizable(False, False)
    
    # 제목
    title_frame = Frame(snooze_window, bg=COLORS['surface'], height=60)
    title_frame.pack(fill='x', padx=2, pady=2)
    title_frame.pack_propagate(False)
    
    Label(title_frame, text='⏰ 알림 스킵 시간 선택',
          font=('Segoe UI', 16, 'bold'),
          bg=COLORS['surface'], fg=COLORS['text']).pack(pady=15)
    
    # 버튼 그리드
    btn_frame = Frame(snooze_window, bg=COLORS['bg'])
    btn_frame.pack(padx=20, pady=20)
    
    # 1-6시간 (첫 번째 행)
    frame1 = Frame(btn_frame, bg=COLORS['bg'])
    frame1.pack(pady=5)
    for h in range(1, 7):
        btn = ModernButton(frame1, f'{h}h', 
                          lambda hours=h: skip_alarm(parent_popup, hours),
                          COLORS['snooze'], COLORS['snooze_hover'],
                          width=60, height=40, font_size=12)
        btn.pack(side='left', padx=3)
    
    # 7-12시간
    frame2 = Frame(btn_frame, bg=COLORS['bg'])
    frame2.pack(pady=5)
    for h in range(7, 13):
        btn = ModernButton(frame2, f'{h}h', 
                          lambda hours=h: skip_alarm(parent_popup, hours),
                          COLORS['snooze'], COLORS['snooze_hover'],
                          width=60, height=40, font_size=12)
        btn.pack(side='left', padx=3)
    
    # 13-18시간
    frame3 = Frame(btn_frame, bg=COLORS['bg'])
    frame3.pack(pady=5)
    for h in range(13, 19):
        btn = ModernButton(frame3, f'{h}h', 
                          lambda hours=h: skip_alarm(parent_popup, hours),
                          COLORS['snooze'], COLORS['snooze_hover'],
                          width=60, height=40, font_size=12)
        btn.pack(side='left', padx=3)
    
    # 19-24시간
    frame4 = Frame(btn_frame, bg=COLORS['bg'])
    frame4.pack(pady=5)
    for h in range(19, 25):
        btn = ModernButton(frame4, f'{h}h', 
                          lambda hours=h: skip_alarm(parent_popup, hours),
                          COLORS['snooze'], COLORS['snooze_hover'],
                          width=60, height=40, font_size=12)
        btn.pack(side='left', padx=3)
    
    # 중앙 배치
    snooze_window.update_idletasks()
    w = snooze_window.winfo_reqwidth()
    h = snooze_window.winfo_reqheight()
    sw = snooze_window.winfo_screenwidth()
    sh = snooze_window.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    snooze_window.geometry(f"{w}x{h}+{x}+{y}")


def show_popup():
    """정각 알림 팝업 - 모던 스타일"""
    global active_popup, auto_close_timer
    
    now = datetime.datetime.now().strftime('%H:%M')
    write_log('알림 표시')
    
    # 비프음 3회
    for _ in range(3):
        winsound.Beep(750, 150)
        time.sleep(0.1)

    popup = Toplevel(root)
    popup.title('정각 알림')
    popup.attributes('-topmost', True)
    popup.configure(bg=COLORS['bg'])
    popup.resizable(False, False)
    active_popup = popup

    # 메인 컨테이너
    main_frame = Frame(popup, bg=COLORS['bg'])
    main_frame.pack(padx=10, pady=10)
    
    # 헤더 - 그라데이션 효과
    header = Frame(main_frame, bg=COLORS['surface'], height=200)
    header.pack(fill='x')
    header.pack_propagate(False)
    
    # 시계 아이콘 (간단한 텍스트로)
    Label(header, text='⏰', font=('Segoe UI', 48),
          bg=COLORS['surface'], fg=COLORS['primary']).pack(pady=(20, 5))
    
    Label(header, text='정각 알림', font=('Segoe UI', 14),
          bg=COLORS['surface'], fg=COLORS['text_dim']).pack()
    
    # 시간 표시 영역
    time_frame = Frame(main_frame, bg=COLORS['bg'], height=200)
    time_frame.pack(fill='x', pady=20)
    time_frame.pack_propagate(False)
    
    Label(time_frame, text='현재 시각', font=('Segoe UI', 14),
          bg=COLORS['bg'], fg=COLORS['text_dim']).pack(pady=(20, 5))
    
    Label(time_frame, text=now, font=('Segoe UI', 56, 'bold'),
          bg=COLORS['bg'], fg=COLORS['primary']).pack()
    
    # 자동 닫힘 카운트다운
    countdown_label = Label(time_frame, text='10초 후 자동으로 닫힙니다', 
                           font=('Segoe UI', 11),
                           bg=COLORS['bg'], fg=COLORS['text_dim'])
    countdown_label.pack(pady=(15, 0))

    
    # 카운트다운 업데이트 함수
    countdown = [10]
    def update_countdown():
        if countdown[0] > 0:
            countdown[0] -= 1
            countdown_label.config(text=f'{countdown[0]}초 후 자동으로 닫힙니다')
            popup.after(1000, update_countdown)
    
    update_countdown()
    
    # 버튼 영역
    btn_container = Frame(main_frame, bg=COLORS['bg'])
    btn_container.pack(fill='x', padx=50, pady=(0, 40))
    
    # 닫기 버튼
    close_btn = ModernButton(btn_container, '닫기', 
                            lambda: close_popup_manual(popup),
                            COLORS['surface_light'], COLORS['primary'],
                            width=180, height=55, font_size=16)
    close_btn.pack(pady=5)
    
    # 스킵 버튼
    skip_btn = ModernButton(btn_container, '⏭️ 스킵 (1시간)', 
                             lambda: show_skip_popup(popup),
                             COLORS['snooze'], COLORS['snooze_hover'],
                             width=180, height=55, font_size=16)
    skip_btn.pack(pady=5)

    # 중앙 배치
    popup.update_idletasks()
    w = popup.winfo_reqwidth()
    h = popup.winfo_reqheight()
    sw = popup.winfo_screenwidth()
    sh = popup.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    popup.geometry(f"{w}x{h}+{x}+{y}")
    
    # 10초 후 자동 닫힘
    auto_close_timer = popup.after(10000, lambda: close_popup_auto(popup))


def clock_checker():
    """시간 체크 및 알림 트리거"""
    global skip_until
    
    while True:
        if running:
            now = datetime.datetime.now()
            
            # 스킵 종료 체크
            if skip_until and now >= skip_until:
                write_log(f'스킵 종료 - 알림 재개 (예약 시간: {skip_until.strftime("%H:%M")})')
                skip_until = None
                time.sleep(2)
            
            # 정각 알림 체크 (스킵 중이 아닐 때만)
            if now.minute == 0 and now.second == 0 and skip_until is None:
                root.after(0, show_popup)
                time.sleep(61)
        
        time.sleep(1)


def toggle_state():
    global running
    running = not running
    winsound.Beep(1000 if running else 600, 150)
    
    # UI 업데이트
    status_indicator.itemconfig(status_circle, 
                               fill=COLORS['success'] if running else COLORS['accent'])
    status_text.config(text='활성화' if running else '비활성화',
                      fg=COLORS['success'] if running else COLORS['accent'])
    
    write_log(f'알림 상태 변경: {"켜짐" if running else "꺼짐"}')


def toggle_pin():
    global pinned, pin_btn
    pinned = not pinned
    root.attributes('-topmost', pinned)
    pin_btn.update_text('📌 항상 위 ON' if pinned else '📌 항상 위 OFF')
    if pinned:
        pin_btn.update_colors(COLORS['primary'], COLORS['primary_hover'])
    else:
        pin_btn.update_colors(COLORS['surface_light'], COLORS['primary'])


def minimize_to_tray():
    root.withdraw()


def on_tray_icon_clicked(icon, item):
    root.deiconify()
    root.lift()
    root.focus_force()


def quit_app(icon=None, item=None):
    write_log('프로그램 종료')
    if tray_icon:
        tray_icon.visible = False
        tray_icon.stop()
    root.destroy()
    os._exit(0)


def open_log_file():
    """로그 파일을 깔끔한 표로 보기"""
    log_window = Toplevel(root)
    log_window.title('알림 로그')
    log_window.geometry('900x600')
    log_window.configure(bg=COLORS['bg'])
    
    # 헤더
    header = Frame(log_window, bg=COLORS['surface'], height=60)
    header.pack(fill='x', padx=2, pady=2)
    header.pack_propagate(False)
    
    Label(header, text='📋 알림 로그', font=('Segoe UI', 18, 'bold'),
          bg=COLORS['surface'], fg=COLORS['text']).pack(pady=15)
    
    # 표 프레임
    table_frame = Frame(log_window, bg=COLORS['bg'])
    table_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    # 스타일 설정
    style = ttk.Style()
    style.theme_use('default')
    style.configure('Treeview',
                    background=COLORS['surface'],
                    foreground=COLORS['text'],
                    fieldbackground=COLORS['surface'],
                    borderwidth=0,
                    font=('Segoe UI', 10))
    style.configure('Treeview.Heading',
                    background=COLORS['surface_light'],
                    foreground=COLORS['primary'],
                    borderwidth=0,
                    font=('Segoe UI', 11, 'bold'))
    style.map('Treeview', background=[('selected', COLORS['primary'])])
    
    # 트리뷰 (표) 생성
    columns = ('날짜', '시간', '이벤트')
    tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
    
    # 컬럼 설정
    tree.heading('날짜', text='날짜')
    tree.heading('시간', text='시간')
    tree.heading('이벤트', text='이벤트')
    
    tree.column('날짜', width=120, anchor='center')
    tree.column('시간', width=100, anchor='center')
    tree.column('이벤트', width=600, anchor='w')
    
    # 스크롤바
    scrollbar = Scrollbar(table_frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    
    # 로그 파일 읽기
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line in lines[::-1]:  # 최신 로그가 위로 (파일 끝부터)
            line = line.strip()
            if line:
                # 2025-12-05 14:00:00 - 알림 표시
                parts = line.split(' - ', 1)
                if len(parts) == 2:
                    datetime_str = parts[0]
                    event = parts[1]
                    
                    # 날짜와 시간 분리
                    date_time = datetime_str.split(' ')
                    if len(date_time) == 2:
                        date = date_time[0]
                        time = date_time[1]
                        tree.insert('', 'end', values=(date, time, event))
    else:
        tree.insert('', 'end', values=('', '', '아직 로그가 없습니다'))
    
    # 배치
    tree.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')
    
    # 닫기 버튼
    btn_frame = Frame(log_window, bg=COLORS['bg'])
    btn_frame.pack(fill='x', padx=10, pady=(0, 10))
    
    close_btn = ModernButton(btn_frame, '닫기',
                            log_window.destroy,
                            COLORS['surface_light'], COLORS['primary'],
                            width=200, height=45, font_size=13)
    close_btn.pack()


# ------------------- 초기화 ------------------- #

def setup_tray():
    global tray_icon
    menu = pystray.Menu(
        item(lambda _: '알림 끄기' if running else '알림 켜기', lambda _: toggle_state()),
        item('열기', on_tray_icon_clicked),
        item('종료', quit_app))
    tray_icon = pystray.Icon('정각 알림이', icon=draw_icon(), title='정각 알림이', menu=menu)
    threading.Thread(target=tray_icon.run, daemon=True).start()


def launch_gui():
    global root, status_text, time_label, status_indicator, status_circle, pin_btn, auto_btn
    
    root = Tk()
    root.title('정각 알림이')
    root.geometry('800x800')
    root.configure(bg=COLORS['bg'])
    root.resizable(False, False)
    if pinned:
        root.attributes('-topmost', True)

    # 메인 컨테이너
    container = Frame(root, bg=COLORS['bg'])
    container.pack(fill='both', expand=True, padx=25, pady=15)
    
    # 헤더
    header = Frame(container, bg=COLORS['bg'])
    header.pack(fill='x', pady=(0, 20))
    
    Label(header, text='⏰', font=('Segoe UI', 32),
          bg=COLORS['bg'], fg=COLORS['primary']).pack()
    
    Label(header, text='정각 알림이', font=('Segoe UI', 24, 'bold'),
          bg=COLORS['bg'], fg=COLORS['text']).pack(pady=(5, 0))
    
    Label(header, text='Modern Edition', font=('Segoe UI', 10),
          bg=COLORS['bg'], fg=COLORS['text_dim']).pack()
    
    # 시계 카드
    clock_card = Frame(container, bg=COLORS['surface'], relief='flat')
    clock_card.pack(fill='x', pady=10)
    
    clock_inner = Frame(clock_card, bg=COLORS['surface'])
    clock_inner.pack(padx=20, pady=20)
    
    Label(clock_inner, text='현재 시각', font=('Segoe UI', 11),
          bg=COLORS['surface'], fg=COLORS['text_dim']).pack()
    
    time_label = Label(clock_inner, text='--:--:--', font=('Segoe UI', 32, 'bold'),
                      bg=COLORS['surface'], fg=COLORS['primary'])
    time_label.pack(pady=(5, 0))
    
    # 스누즈 정보 라벨 먼저 생성
    snooze_info = Label(clock_inner, text='', font=('Segoe UI', 9),
                       bg=COLORS['surface'], fg=COLORS['warning'])
    snooze_info.pack(pady=(5, 0))
    
    def tick():
        current = datetime.datetime.now()
        time_label.config(text=current.strftime('%H:%M:%S'))
        
        # 스누즈 정보 표시
        if skip_until:
            diff = skip_until - current
            hours = int(diff.total_seconds() // 3600)
            minutes = int((diff.total_seconds() % 3600) // 60)
            snooze_info.config(text=f'알림 스킵 중: {hours}시간 {minutes}분 후 재개')

        else:
            snooze_info.config(text='')
        
        root.after(1000, tick)
    
    tick()
    
    # 상태 카드
    status_card = Frame(container, bg=COLORS['surface'])
    status_card.pack(fill='x', pady=10)
    
    status_inner = Frame(status_card, bg=COLORS['surface'])
    status_inner.pack(padx=20, pady=15)
    
    status_row = Frame(status_inner, bg=COLORS['surface'])
    status_row.pack()
    
    # 상태 인디케이터
    status_indicator = Canvas(status_row, width=16, height=16, 
                             bg=COLORS['surface'], highlightthickness=0)
    status_indicator.pack(side='left', padx=(0, 10))
    status_circle = status_indicator.create_oval(2, 2, 14, 14, 
                                                 fill=COLORS['success'], outline='')
    
    status_text = Label(status_row, text='활성화', font=('Segoe UI', 14, 'bold'),
                       bg=COLORS['surface'], fg=COLORS['success'])
    status_text.pack(side='left')
    
    # 설정 버튼 섹션
    settings_frame = Frame(container, bg=COLORS['bg'])
    settings_frame.pack(fill='x', pady=15)
    
    settings_row = Frame(settings_frame, bg=COLORS['bg'])
    settings_row.pack()
    
    # 항상 위 버튼
    pin_btn = ModernButton(settings_row, '📌 항상 위 ON' if pinned else '📌 항상 위 OFF',
                          toggle_pin,
                          COLORS['primary'] if pinned else COLORS['surface_light'],
                          COLORS['primary_hover'] if pinned else COLORS['primary'],
                          width=270, height=45, font_size=12)
    pin_btn.pack(side='left', padx=3)
    
    # 자동 실행 버튼
    auto_btn = ModernButton(settings_row, '🚀 자동실행 ON' if auto_starting else '🚀 자동실행 OFF',
                           toggle_autostart,
                           COLORS['primary'] if auto_starting else COLORS['surface_light'],
                           COLORS['primary_hover'] if auto_starting else COLORS['primary'],
                           width=270, height=45, font_size=12)
    auto_btn.pack(side='left', padx=3)

    
    # 버튼 그룹
    btn_group = Frame(container, bg=COLORS['bg'])
    btn_group.pack(fill='x', pady=15)
    
    # 첫 번째 줄 (알림 ON/OFF, 테스트 알림)
    btn_row1 = Frame(btn_group, bg=COLORS['bg'])
    btn_row1.pack(pady=3)
    
    toggle_btn = ModernButton(btn_row1, '알림 ON/OFF',
                             toggle_state,
                             COLORS['primary'], COLORS['primary_hover'],
                             width=270, height=50, font_size=13)
    toggle_btn.pack(side='left', padx=3)
    
    test_btn = ModernButton(btn_row1, '🔔 테스트',
                           show_popup,
                           COLORS['warning'], '#e6c200',
                           COLORS['bg'],
                           width=270, height=50, font_size=13)
    test_btn.pack(side='left', padx=3)
    
    # 두 번째 줄 (로그 보기, 최소화)
    btn_row2 = Frame(btn_group, bg=COLORS['bg'])
    btn_row2.pack(pady=3)
    
    log_btn = ModernButton(btn_row2, '📄 로그',
                          open_log_file,
                          COLORS['surface_light'], COLORS['primary'],
                          width=270, height=50, font_size=13)
    log_btn.pack(side='left', padx=3)
    
    minimize_btn = ModernButton(btn_row2, '최소화',
                               minimize_to_tray,
                               COLORS['surface_light'], COLORS['primary'],
                               width=270, height=50, font_size=13)
    minimize_btn.pack(side='left', padx=3)
    
    # 세 번째 줄 (종료 - 전체 너비)
    btn_row3 = Frame(btn_group, bg=COLORS['bg'])
    btn_row3.pack(pady=3)
    
    quit_btn = ModernButton(btn_row3, '종료',
                           quit_app,
                           COLORS['accent'], COLORS['accent_hover'],
                           width=546, height=50, font_size=14)
    quit_btn.pack()

    
    # 푸터
    footer = Label(container, text='v2.0.0 Modern | Made with ❤️', 
                  font=('Segoe UI', 8),
                  bg=COLORS['bg'], fg=COLORS['text_dim'])
    footer.pack(side='bottom', pady=(10, 0))
    
    root.protocol('WM_DELETE_WINDOW', minimize_to_tray)
    write_log('프로그램 시작')
    
    root.mainloop()


# ------------------- main ------------------- #
if __name__ == '__main__':
    threading.Thread(target=clock_checker, daemon=True).start()
    setup_tray()
    launch_gui()
