import sys
import json
from PyQt5.QtGui import QPixmap, QPainter, QIcon, QColor, QMovie, QFont, QIntValidator,  QPen
from PyQt5.QtCore import QRect, Qt, QObject, QEvent, QSize, QTimer, QUrl,QPropertyAnimation, QEasingCurve ,QPoint, pyqtSignal, QDateTime, QEventLoop
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QStackedWidget, QSlider, QStackedLayout, QTextEdit
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QLineEdit, QListWidgetItem, QSizePolicy, QScrollArea, QFrame
from PyQt5.QtWidgets import QGridLayout, QListWidget, QLabel, QGraphicsOpacityEffect, QButtonGroup
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QSoundEffect, QSound
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import os
import random
from login_window import LoginWindow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from notification_sender import send_push_notification
FCM_TOKEN = "eiAR5Oa7TbSnBqEtzrn_5d:APA91bFOIevik8uMQlHeAl5IYItNklGLOjoLA4jtwmdtmBy5OpaWY33GrxNVqMCMSnkaGW-dhnDEtQs3GCrIjJ49d7klQThvYCFaFUSgnHK8z_9j0LfThNM"

def load_frames_from_xml(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    frames = []
    for subtexture in root.findall("SubTexture"):
        x = int(subtexture.attrib["x"])
        y = int(subtexture.attrib["y"])
        width = int(subtexture.attrib["width"])
        height = int(subtexture.attrib["height"])
        frameX = int(subtexture.attrib.get("frameX", "0"))
        frameY = int(subtexture.attrib.get("frameY", "0"))
        frameWidth = int(subtexture.attrib.get("frameWidth", str(width)))
        frameHeight = int(subtexture.attrib.get("frameHeight", str(height)))
        frames.append({
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "frameX": frameX,
            "frameY": frameY,
            "frameWidth": frameWidth,
            "frameHeight": frameHeight
        })
    return frames

class SpriteAnimator(QLabel):
    def __init__(self, sprite_path, frames, parent=None):
        super().__init__(parent)
        self.frames = frames
        self.sprite = QPixmap(sprite_path)
        self.frame_index = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance_frame)
        self.loop_count = 1
        self.current_loop = 0

        #self.setFixedSize(900, 900)
        first_frame = frames[0]
        self.setFixedSize(first_frame["frameWidth"], first_frame["frameHeight"])
        self.setAlignment(Qt.AlignCenter)

    def start_animation(self, interval, loops):
        self.loop_count = loops
        self.current_loop = 0
        self.frame_index = 0
        self.show()
        self.display_frame(0)  # 最初のフレームを表示
        self.timer.start(interval)

    def advance_frame(self):
        if self.frame_index >= len(self.frames):
            self.current_loop += 1
            if self.current_loop >= self.loop_count:
                self.timer.stop() # 最後のフレームを表示
                last_frame = self.frames[-1]
                rect = QRect(last_frame["x"], last_frame["y"], last_frame["width"], last_frame["height"])
                cropped = self.sprite.copy(rect)
                self.setPixmap(cropped)
                return
            else:
                self.frame_index = 0

        frame = self.frames[self.frame_index]
        rect = QRect(frame["x"], frame["y"], frame["width"], frame["height"])
        cropped = self.sprite.copy(rect)
        self.setPixmap(cropped)
        self.frame_index += 1

    def display_frame(self, index):
        frame = self.frames[index]
        rect = QRect(frame["x"], frame["y"], frame["width"], frame["height"])
        cropped = self.sprite.copy(rect)
        self.setPixmap(cropped)

class TalkAnimation(QWidget):
    def __init__(self, xml_path, png_path, text, parent=None):
        super().__init__(parent)
        frames = load_frames_from_xml(xml_path)
        self.animator = SpriteAnimator(png_path, frames, parent=self)
        self.font = QFont("Mv Boli", 20)
        self.full_text = text
        self.current_index = 0
        self.text_timer = QTimer(self)
        self.text_timer.timeout.connect(self._show_next_char)
        self.is_text_animating = False

        self.balloon = QLabel(self)
        self.balloon.setPixmap(QPixmap("assets/images/吹き出し.png"))
        self.balloon.setFixedSize(1240, 380)
        self.balloon.move(400, 700)

        self.text_label = QLabel(self.balloon)
        self.text_label.setText(text)
        self.text_label.setFont(self.font)
        self.text_label.setStyleSheet("color: black;")
        self.text_label.setWordWrap(True) 
        self.text_label.setGeometry(30, 30, 1240-60, 380-60)

        self.animator.setParent(self) 
        self.animator.move(480, 20)
        self.setFixedSize(1920, 1080)
        self.balloon.raise_()
        self.text_label.raise_()
        # Enter待ち用
        self.enter_loop = None
        self.sound = QSoundEffect()
        self.sound.setSource(QUrl.fromLocalFile("assets\sounds\chara.wav"))
        self.sound.setVolume(0.5)

    def play(self, loops, interval, text_speed):
        #アニメーション再生 → Enter待
        self.is_text_animating = True
        self.animator.start_animation(interval=interval, loops=loops)
        self.current_index = 0 
        self.text_label.setText("") 
        self.text_timer.start(text_speed)

        # アニメ終了待ち（SpriteAnimator が止まるまで待つ）
        wait = QEventLoop()
        def check_end():
            if not self.animator.timer.isActive():
                wait.quit()

        self.animator.timer.timeout.connect(check_end)
        #wait.exec_()
        # self.enter_loop = QEventLoop()
        # self.enter_loop.exec_()

    def _show_next_char(self):
        if self.current_index < len(self.full_text):
            self.current_index += 1
            self.text_label.setText(self.full_text[:self.current_index])
            if self.sound: 
                self.sound.play()
        else:
            self.text_timer.stop()
            self.is_text_animating = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            if self.is_text_animating:
                self.text_timer.stop()
                self.text_label.setText(self.full_text)
                self.is_text_animating = False
                return

class ArrowKeyFilter(QObject):
    def __init__(self, input_widget, list_widget):
        super().__init__()
        self.input_widget = input_widget
        self.list_widget = list_widget

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if obj == self.input_widget and event.key() == Qt.Key_Down:
                self.list_widget.setFocus()
                self.list_widget.setCurrentRow(0)
                return True
            elif obj == self.list_widget and event.key() == Qt.Key_Up:
                current_row = self.list_widget.currentRow()
                if current_row == 0:
                    self.input_widget.setFocus()
                    return True
        return False

class TextRenderer(QWidget):
    def __init__(self, text, glyphs, sheets, max_width):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self.text = text
        self.glyphs = glyphs
        self.sheets = sheets
        self.max_width = max_width
        self.hovered = False
        self.frame = 0
        self.strike_out = False

        self.setMouseTracking(True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance_frame)

        self.outer_layout = QVBoxLayout()
        self.outer_layout.setAlignment(Qt.AlignLeft)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)
        self.setLayout(self.outer_layout)

        self.render_text()

    def render_text(self):
        while self.outer_layout.count():
            item = self.outer_layout.takeAt(0)
            if item.layout():
                line_layout = item.layout()
                while line_layout.count():
                    sub_item = line_layout.takeAt(0)
                    widget = sub_item.widget()
                    if widget:
                        widget.deleteLater()
            elif item.widget():
                item.widget().deleteLater()

        current_line = QHBoxLayout()
        current_line.setSpacing(0)
        current_line.setAlignment(Qt.AlignLeft)
        current_width = 0

        for char in self.text:
            glyph = self.glyphs.get(char, self.glyphs["_fallback"])
            anim = glyph.get("animations", {}).get("bounce", None)
            if self.hovered and anim:
                sequence = anim.get("sequence", ["idle"])
                frame_key = sequence[self.frame % len(sequence)]
                info = glyph.get(frame_key, glyph["idle"])
            else:
                info = glyph["idle"]
            sheet_name = info["sheet"]
            sprite = self.sheets[sheet_name]
            rect = QRect(info["x"], info["y"], info["width"], info["height"])

            cropped = sprite.copy(rect)

            label = QLabel()
            label.setContentsMargins(0, 17, 0, 16)
            label.setFixedSize(cropped.width(), cropped.height() + 33)
            label.setPixmap(cropped)

            char_width = cropped.width()
            if current_width + char_width > self.max_width:
                self.outer_layout.addLayout(current_line)
                current_line = QHBoxLayout()
                current_line.setSpacing(0)
                current_line.setAlignment(Qt.AlignLeft)
                current_width = 0

            current_line.addWidget(label)
            current_width += char_width

        self.outer_layout.addLayout(current_line)
    def enterEvent(self, event):
        self.hovered = True
        self.frame = 0
        anim = self.glyphs.get(self.text[0], {}).get("animations", {}).get("bounce", None)
        if anim:
            duration = anim.get("frameDuration", 200)
            self.timer.start(duration)
        self.render_text()

    def leaveEvent(self, event):
        self.hovered = False
        self.timer.stop()
        self.frame = 0
        self.render_text()

    def advance_frame(self):
        self.frame += 1
        self.render_text()

    def set_text(self, new_text):
        self.text = new_text
        self.render_text()

    def setStrikeOut(self, enabled: bool):
        self.strike_out = enabled
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.strike_out:
            pen = QPen(Qt.black, 2)
            painter.setPen(pen)
            painter.drawLine(0, 0, self.width(), self.height())# 左上から右下へ斜線
        super().paintEvent(event)

class NumberRenderer(QWidget):
    def __init__(self, text, glyphs, sheets, size):
        super().__init__()
        self.text = text
        self.glyphs = glyphs
        self.sheets = sheets
        self.size = size
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self.resize(size * len(text), size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        x_offset = 0
        for char in self.text:
            glyph = self.glyphs.get(char, self.glyphs["_fallback"])
            info = glyph["idle"]
            sprite = self.sheets[info["sheet"]]
            rect = QRect(info["x"], info["y"], info["width"], info["height"])
            cropped = sprite.copy(rect)

            scaled = cropped.scaled(
                self.size, self.size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(x_offset, 0, scaled)
            x_offset += scaled.width()

class HoverButton(QPushButton):#特殊なやつ。ジャンル帰るボタン用につくったやつ。
    def __init__(self, target_widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_widget = target_widget
        self.anim = None
        self.original_pos = target_widget.pos()
        self.setMouseTracking(True)  

    def enterEvent(self, event):
        self.animate_shift(-20)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animate_shift(0)
        super().leaveEvent(event)

    def animate_shift(self, shift_x):
        if self.anim and self.anim.state() == QPropertyAnimation.Running:
            self.anim.stop()

        target_pos = self.original_pos + QPoint(shift_x, 0)
        self.anim = QPropertyAnimation(self.target_widget, b"pos")
        self.anim.setDuration(300)
        self.anim.setStartValue(self.target_widget.pos())
        self.anim.setEndValue(target_pos)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

class HoverIconSoundButton(QPushButton):
    def __init__(self, normal_icon_path=None, hover_icon_path=None, sound_path=None, parent=None):
        super().__init__(parent)

        # アイコン設定
        self.normal_icon = QIcon(normal_icon_path) if normal_icon_path else None
        self.hover_icon = QIcon(hover_icon_path) if hover_icon_path else None
        if self.normal_icon:
            self.setIcon(self.normal_icon)

        # サウンド設定
        self.hover_sound = None
        if sound_path:
            self.hover_sound = QSoundEffect()
            self.hover_sound.setSource(QUrl.fromLocalFile(sound_path))
            self.hover_sound.setVolume(0.8)

        self.setStyleSheet("""QPushButton {#必要なら統合
                letter-spacing: 4px;
                background: transparent;
                border: none;}
            QPushButton:hover {
                letter-spacing: 12px;}""")

        self.setFixedSize(100, 100)

    def enterEvent(self, event):
        # アイコン切り替え
        if self.hover_icon:
            self.setIcon(self.hover_icon)
        # サウンド再生
        if self.hover_sound:
            self.hover_sound.play()
        super().enterEvent(event)

    def leaveEvent(self, event):#戻す
        if self.normal_icon:
            self.setIcon(self.normal_icon)

        super().leaveEvent(event)

class HoverSoundButton(QPushButton):
    def __init__(self, text, sound_path, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""QPushButton {
                color: white;
                font-size: 36px;
                letter-spacing: 4px;
                background: transparent;
                border: none;}
            QPushButton:hover {
                letter-spacing: 12px;}""")
        self.hover_sound = QSoundEffect()
        self.hover_sound.setSource(QUrl.fromLocalFile(sound_path))
        self.hover_sound.setVolume(0.8)

    def enterEvent(self, event):
        self.hover_sound.play()
        super().enterEvent(event)

class StartScreen(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(100)

        self.movie_label = QLabel()
        self.movie_label.setAlignment(Qt.AlignCenter)

        self.movie = QMovie("assets\movie\Title.gif")
        self.movie.setScaledSize(QSize(1260, 650))
        self.movie.setCacheMode(QMovie.CacheAll)
        self.movie_label.setMovie(self.movie)
        layout.addWidget(self.movie_label)

        self.movie.frameChanged.connect(self.check_last_frame)
        self.movie.start()

        self.sound_player = QMediaPlayer()
        self.sound_player.setMedia(QMediaContent(QUrl.fromLocalFile("assets\sounds\start.wav")))
        self.sound_player.setVolume(100)
        self.sound_player.play()

        self.enter_label = QLabel("Press  Enter  to  Begin")
        self.enter_label.setAlignment(Qt.AlignCenter)
        self.enter_label.setStyleSheet('color: white; font-size: 50px; font-family: "Mv Boli";')

        layout.addWidget(self.enter_label)

        self.opacity_effect = QGraphicsOpacityEffect()
        self.enter_label.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)  # 最初透明

        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(3000)  # 2秒かけて表示
        self.fade_animation.setStartValue(0)
        self.fade_animation.setEndValue(1)
        QTimer.singleShot(6000, self.fade_animation.start)# 5秒後開く

    def check_last_frame(self, frame_number):
        total_frames = self.movie.frameCount()
        if total_frames > 0 and frame_number == total_frames - 1:
            self.movie.stop()
            self.movie.jumpToFrame(frame_number)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.sound_player.stop()
            self.main_window.fade_to(self.main_window.menu_screen)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        super().paintEvent(event)

class MenuScreen(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.main_window = main_window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.bg = QPixmap("assets/images/background0-1.png")

        self.hover_sound = QSoundEffect()
        self.hover_sound.setSource(QUrl.fromLocalFile("assets\sounds\hover.wav"))
        self.hover_sound.setVolume(0.8)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(40)
        self.button_style = """QPushButton {
                color: black;
                font-size: 100px;
                letter-spacing: 4px;
                background: transparent;
                border: none;
                font-family: "Mv Boli";
                padding: 0px;
                margin: 0px;}
            QPushButton:hover {
                letter-spacing: 12px;}"""
        self.todo_btn = HoverSoundButton("ToDo List", "assets\sounds\hover.wav")
        self.option_btn = HoverSoundButton("Option", "assets\sounds\hover.wav")
        self.award_btn = HoverSoundButton("Award", "assets\sounds\hover.wav")
        self.back_btn = HoverSoundButton("Back", "assets\sounds\hover.wav")

        self.selected_index = 0
        self.buttons = [self.todo_btn, self.option_btn, self.award_btn, self.back_btn]
        self.update_selection()

        for btn in [self.todo_btn, self.option_btn, self.award_btn, self.back_btn]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet(self.button_style)
            layout.addWidget(btn)

        self.todo_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.todo_btn, lambda: self.main_window.fade_to(self.main_window.todo_screen)))
        self.option_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.option_btn, lambda: self.main_window.fade_to(self.main_window.option_screen)))  
        self.award_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.option_btn, lambda: self.main_window.fade_to(self.main_window.award_screen)))
        self.back_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.back_btn, lambda: self.main_window.fade_to(self.main_window.start_screen)))

        self.setFocus()
    
    def update_selection(self):
        for i, btn in enumerate(self.buttons):
            if i == self.selected_index:
                btn.setStyleSheet(self.button_style + """QPushButton {
                    letter-spacing: 12px;
                    border: none;}""")
            else:
                btn.setStyleSheet(self.button_style)
        self.hover_sound.play()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self.selected_index = (self.selected_index - 1) % len(self.buttons)
            self.update_selection()
        elif event.key() == Qt.Key_Down:
            self.selected_index = (self.selected_index + 1) % len(self.buttons)
            self.update_selection()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            selected_btn = self.buttons[self.selected_index]
            self.main_window.flash_widget_color(selected_btn, lambda: selected_btn.click())
        elif event.key() == Qt.Key_Backspace:
            self.main_window.flash_widget_color(self.back_btn, lambda: self.back_btn.click())

    def paintEvent(self, event):
        if self.bg.isNull():
            return

        painter = QPainter(self)
        if not painter.isActive():
            print("Painterが非アクティブ")  #デバッグ
            return

        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

class AwardScreen(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.main_window = main_window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.bg = QPixmap("assets/images/background0-1.png")
        self.font = QFont("Mv Boli", 20)
        self.today_str = datetime.now().strftime("%Y/%m/%d")

        self.back_btn = HoverIconSoundButton("戻る.png", "戻るh.png", "hover.wav")
        self.back_btn.setFixedWidth(100)
        self.back_btn.setIconSize(QSize(80, 80))
        self.back_btn.setStyleSheet("background: transparent; border: none; margin: 0px;")
        self.back_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.back_btn, lambda: self.main_window.fade_to(self.main_window.menu_screen)))
        self.label_username = QLabel()
        self.label_now = QLabel()
        self.label_now.setText(self.today_str)
        self.label_login = QLabel("0")
        self.label_delete = QLabel("0")
        self.label_again = QLabel("0")
        self.label_weekly = QLabel("0")
        self.label_daily = QLabel("0")
        self.label_save = QLabel("0")
        self.label_achieve = QLabel("0")
        self.label_username.setFixedWidth(400)
        self.label_now.setFixedWidth(250)
        self.label_login.setFixedWidth(400)
        self.label_delete.setFixedWidth(400)
        self.label_again.setFixedWidth(400)
        self.label_weekly.setFixedWidth(600)
        self.label_daily.setFixedWidth(600)
        self.label_save.setFixedWidth(400)
        self.label_achieve.setFixedWidth(400)
        self.label_username.setFont(self.font)
        self.label_now.setFont(self.font)
        self.label_login.setFont(self.font)
        self.label_delete.setFont(self.font)
        self.label_again.setFont(self.font)
        self.label_weekly.setFont(self.font)
        self.label_daily.setFont(self.font)
        self.label_save.setFont(self.font)
        self.label_achieve.setFont(self.font)
        
        self.top_layout = QHBoxLayout()
        self.top_layout.addWidget(self.back_btn, alignment=Qt.AlignLeft)
        self.top_layout.addStretch()
        self.top_layout.addWidget(self.label_username)
        self.top_layout.addStretch()
        self.top_layout.addWidget(self.label_now)

        self.layout1 = QHBoxLayout()
        self.layout2 = QHBoxLayout()
        self.layout3 = QHBoxLayout()
        self.layout4 = QHBoxLayout()
        self.layout1.addWidget(self.label_login)
        self.layout1.addWidget(self.label_save)
        self.layout2.addWidget(self.label_achieve)
        self.layout2.addWidget(self.label_delete)
        self.layout3.addWidget(self.label_weekly)
        self.layout3.addWidget(self.label_daily)
        self.layout4.addWidget(self.label_again)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.addLayout(self.top_layout)
        self.main_layout.addLayout(self.layout1)
        self.main_layout.addLayout(self.layout2)
        self.main_layout.addLayout(self.layout3)
        self.main_layout.addLayout(self.layout4)

    def update_display(self):
        info = self.main_window.info

        self.label_username.setText(f"User: {info.get('username', '')}")
        self.label_login.setText(f"Login count: {info.get('login_count', 0)}")
        self.label_delete.setText(f"Deleted tasks: {info.get('delete_count', 0)}")
        self.label_again.setText(f"Max repeat: {info.get('again_max', 0)}")
        self.label_weekly.setText(f"Weekly motivation max: {int(info.get('weekly_mochivation_max', 0))}")
        self.label_daily.setText(f"Daily motivation max: {info.get('day_mochivation_max', 0)}")
        self.label_save.setText(f"Save count: {info.get('save_count', 0)}")
        self.label_achieve.setText(f"Achieve count: {info.get('achieve_count', 0)}")

    def paintEvent(self, event):
        painter = QPainter(self)
        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

class NameDetailPanel(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.user_name = ""
        layout = QVBoxLayout(self)
        #layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(0)

        self.label = QLabel("Please enter your name;")
        self.label.setStyleSheet("""QLabel {
                color: black;
                font-size: 50px;
                font-family: "Mv Boli";
                margin: 0px;}""")
        layout.addWidget(self.label)

        self.label_sub = QLabel("※It is recommended to enter in English;<br>Click '↵' to return to the state before saving;")
        self.label_sub.setStyleSheet("""QLabel {
                color: black;
                font-size: 30px;
                font-family: "Mv Boli";
                margin: 0px;}""")
        layout.addWidget(self.label_sub)

        self.input = QLineEdit()
        self.input.setText(self.user_name)
        self.input.setFixedWidth(600)
        self.input.setPlaceholderText("ex)User Name")
        self.input.setStyleSheet("""QLineEdit {
                font-size: 28px;
                padding: 12px;
                border-radius: 10px;
                font-family: "Mv Boli";
                background-color: rgba(255, 255, 255, 180);
                margin: 0px;}""")
        layout.addWidget(self.input)

        self.save_btn = QPushButton("save")
        self.save_btn.setFixedWidth(200)
        self.save_btn.resize(200, 80)
        self.save_btn.setStyleSheet("""QPushButton {
                font-size: 28px;
                padding: 12px 24px;
                border-radius: 10px;
                background-color: #333333;
                color: white;
                font-family: "Mv Boli";
                margin-bottom: 100px;
                margin-top: 20px;
                margin-right: 0px;
                margin-left: 60px;}
            QPushButton:hover {
                background-color: #4d4d4d;}""")
        layout.addWidget(self.save_btn)

        self.reset_btn = QPushButton("↵")
        self.reset_btn.setFixedWidth(120)
        self.reset_btn.resize(120, 80)
        self.reset_btn.setStyleSheet("""QPushButton {
                font-size: 28px;
                padding: 12px;
                border-radius: 10px;
                background-color: #333333;
                color: white;
                font-family: "Mv Boli";
                margin-bottom: 100px;
                margin-top: 20px;
                margin-right: 0px;
                margin-left: 60px;}
            QPushButton:hover {
                background-color: #4d4d4d;}""")
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_btn)
        layout.setSpacing(0)
        button_layout.addWidget(self.reset_btn)
        layout.addLayout(button_layout)

        self.reset_btn.clicked.connect(self.reset_name)
        self.save_btn.clicked.connect(self.save_name)

    def save_name(self):
        self.user_name = self.input.text()
        print("保存された名前:", self.user_name)
        self.main_window.user_name = self.user_name
        self.main_window.todo_screen.header_overlay.update_user_name(self.user_name)
        self.main_window.todo_screen.start_log.update_user_name(self.user_name)
        self.main_window.info["username"] = self.user_name
        self.main_window.save_data()

    def reset_name(self):
        self.input.setText(self.user_name)

    def showEvent(self, event):
        super().showEvent(event)
        self.reset_panel()

    def reset_panel(self):
        self.input.setText(self.main_window.user_name)
        print("パネル初期化：現在の名前 →", self.main_window.user_name)

class VolumeDetailPanel(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        layout = QVBoxLayout(self)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(80)
        layout.addWidget(QLabel("音量"))
        layout.addWidget(self.slider)

class ResetDetailPanel(QWidget):
    def __init__(self,main_window,parent=None):
        super().__init__(parent)
        self.main_window = main_window
        font = QFont("Mv Boli", 25)
        font1 = QFont("Mv Boli", 15)
        self.clear_button = QPushButton("Reset")
        self.reset_status_label = QLabel("")
        self.reset_status_label.setAlignment(Qt.AlignCenter)
        self.label = QLabel("Press 'Reset' to clear all list items "
                            "<br>and notifications;"
        "<br>Reset will erase all list data "
        "<br>and remove notifications;")
        self.label.setFixedSize(757, 500)
        self.reset_status_label.setFixedSize(757, 200)
        self.clear_button.setFixedSize(757, 100)
        self.label.setStyleSheet("color: black; margin-top:100px;")
        self.reset_status_label.setStyleSheet("color: black; margin:0px;")
        self.clear_button.setStyleSheet("color: black; margin:0px;margin-bottom:0px; padding:0px;")

        self.reset_status_label.setFont(font)
        self.clear_button.setFont(font)
        self.label.setFont(font1)
        self.clear_button.clicked.connect(self.clear_data_store)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.reset_status_label)
        layout.addWidget(self.clear_button)
        self.setLayout(layout)

    def clear_data_store(self):
    # メインウィンドウのデータを空
        self.main_window.todo_data_store = []
    # JSONファイルも空
        try:
            with open("data/todo_data.json", "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print("データストアとJSONをクリアしました")
        except Exception as e:
            print("クリア失敗:", e)
    # 画面反映
        self.main_window.todo_screen.todo_data_store = []
        self.main_window.todo_screen.apply_sorting(
            self.main_window.current_sort_index,
            self.main_window.current_sort_order)
        
        self.reset_status_label.setText("Reseted")

    def showEvent(self, event):
        super().showEvent(event)
        self.reset_status_label.setText("")

class OptionScreen(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.main_window = main_window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.bg = QPixmap("assets/images/background0-1.png")
        self.animations = []
        self.bg_animation_played = False  

        self.hover_sound = QSoundEffect()
        self.hover_sound.setSource(QUrl.fromLocalFile("assets\sounds\hover.wav"))
        self.hover_sound.setVolume(0.8)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(40)
        self.button_style = """QPushButton {
                color: black;
                font-size: 100px;
                letter-spacing: 4px;
                background: transparent;
                border: none;
                font-family: "Mv Boli";
                padding: 0px;
                margin: 0px;}
            QPushButton:hover {
                letter-spacing: 12px;}"""
        self.name_btn = HoverSoundButton("User name", "assets\sounds\hover.wav")
        self.volume_btn = HoverSoundButton("Volume", "assets\sounds\hover.wav")
        self.login_btn = HoverSoundButton("Login", "assets\sounds\hover.wav")
        self.reset_btn = HoverSoundButton("Reset", "assets\sounds\hover.wav")
        self.back_btn = HoverSoundButton("Back", "assets\sounds\hover.wav")

        self.selected_index = 0
        self.buttons = [self.name_btn, self.volume_btn, self.login_btn, self.reset_btn, self.back_btn]

        for i, btn in enumerate(self.buttons):
            btn.setParent(self)
            btn.setStyleSheet(self.button_style)
            btn.resize(600, 120)
            btn.move(600, 200 + i * 150)

        self.detail_container = QWidget(self)
        self.detail_container.setGeometry(1100, 0, 1920-1100, 1080)
        self.detail_stack = QStackedWidget(self.detail_container)
        self.detail_stack.setGeometry(0, 0, 960, 1080)

        self.name_panel = NameDetailPanel(main_window=self.main_window)
        self.detail_stack.addWidget(self.name_panel)

        self.volume_panel = VolumeDetailPanel(main_window=self.main_window)
        self.detail_stack.addWidget(self.volume_panel)

        self.login_panel = LoginWindow(main_window=self.main_window)
        self.detail_stack.addWidget(self.login_panel)

        self.reset_panel = ResetDetailPanel(main_window=self.main_window)
        self.detail_stack.addWidget(self.reset_panel)

        self.bg_movie = QMovie("assets\movie\option.gif")
        self.bg_movie.finished.connect(self.bg_movie.stop)
        self.bg_movie.setScaledSize(self.size())
        self.bg_movie.frameChanged.connect(self.stop_on_last_frame)
        self.bg_label = QLabel(self)
        self.bg_label.setMovie(self.bg_movie)
        self.bg_label.setGeometry(0, 0, self.width(), self.height())
        self.bg_label.lower()

        self.original_positions = [btn.pos() for btn in self.buttons]
        self.name_btn.clicked.connect(lambda: self.enter_detail_mode(0))
        self.volume_btn.clicked.connect(lambda: self.enter_detail_mode(1))
        self.login_btn.clicked.connect(lambda: self.enter_detail_mode(2))
        self.reset_btn.clicked.connect(lambda: self.enter_detail_mode(3))
        self.back_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.back_btn, lambda: self.main_window.fade_to(self.main_window.menu_screen)))
        #self.setFocus()
        self.bg_start_sound = QSoundEffect()
        self.bg_start_sound.setSource(QUrl.fromLocalFile("assets\sounds\cut.wav"))
        self.bg_start_sound.setVolume(0.4)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.bg_label.setGeometry(0, 0, self.width(), self.height())
        self.bg_movie.setScaledSize(self.size())

    def stop_on_last_frame(self,frame_number):
        total = self.bg_movie.frameCount()
        if total > 0 and frame_number == total - 1:
            self.bg_movie.stop()
    
    def showEvent(self, event):
        super().showEvent(event)
        self.reset_option_screen()
        self.setFocus()

    def animate_button_to_left(self, btn, target_x):
        anim = QPropertyAnimation(btn, b"pos")
        anim.setDuration(500)
        anim.setStartValue(btn.pos())
        anim.setEndValue(QPoint(target_x, btn.y()))
        anim.setEasingCurve(QEasingCurve.OutCubic)  #イージング
        anim.start()
        self.animations.append(anim)  #保持

    def fade_in_widget(self, widget, duration=500):
        if not widget.graphicsEffect():
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(0.0)
            widget.setGraphicsEffect(effect)

        effect = widget.graphicsEffect()
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

        self.animations.append(anim)  #保持

    def safe_fade_in(self, widget, duration=500):
        if not widget.graphicsEffect():
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(0.0)
            widget.setGraphicsEffect(effect)

        widget.show()
        widget.raise_()

        anim = QPropertyAnimation(widget.graphicsEffect(), b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

        self.animations.append(anim)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Polish and hasattr(self, "pending_fade_widget") and obj == self.pending_fade_widget: 
            obj.removeEventFilter(self)
            self.safe_fade_in(obj)
            del self.pending_fade_widget
        return super().eventFilter(obj, event)

    def prepare_and_fade_in(self, index):
        widget = self.detail_stack.widget(index)
        self.detail_stack.setCurrentIndex(index)
        self.detail_stack.show()

        widget.installEventFilter(self)
        self.pending_fade_widget = widget

    def enter_detail_mode(self, index):
        self.play_background_animation()
        self.detail_stack.setCurrentIndex(index)
        #self.detail_stack.show()
        for i, btn in enumerate(self.buttons):
            self.animate_button_to_left(btn, 100)
        QTimer.singleShot(300, lambda: self.prepare_and_fade_in(index))
       
    def exit_detail_mode(self):
        for btn, pos in zip(self.buttons, self.original_positions):
            self.animate_button_to_left(btn, pos.x())

    def update_selection(self):
        for i, btn in enumerate(self.buttons):
            if i == self.selected_index:
                btn.setStyleSheet(self.button_style + """QPushButton {
                    letter-spacing: 12px;
                    border: none;}""")
            else:
                btn.setStyleSheet(self.button_style)
        self.hover_sound.play()

    def play_background_animation(self):
        if not self.bg_animation_played:
            self.bg_start_sound.play()
            self.bg_movie.start()
            self.bg_animation_played = True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self.selected_index = (self.selected_index - 1) % len(self.buttons)
            self.update_selection()
        elif event.key() == Qt.Key_Down:
            self.selected_index = (self.selected_index + 1) % len(self.buttons)
            self.update_selection()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            selected_btn = self.buttons[self.selected_index]
            self.main_window.flash_widget_color(selected_btn, lambda: selected_btn.click())
        elif event.key() == Qt.Key_Backspace:
            self.main_window.flash_widget_color(self.back_btn, lambda: self.back_btn.click())

    def reset_option_screen(self):
        for btn, pos in zip(self.buttons, self.original_positions):
            btn.move(pos)
        self.bg_movie.stop()
        self.bg_movie.jumpToFrame(0)
        self.bg_animation_played = False
        self.detail_stack.setCurrentIndex(-1)  #何もない
        self.detail_stack.hide()

        for btn in self.buttons:
            btn.setStyleSheet(self.button_style)

        self.selected_index = 0
        self.update_selection()

    def paintEvent(self, event):
        painter = QPainter(self)
        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

class ChangeDialog(QWidget):
    def __init__(self, main_window=None):
        super().__init__(main_window)
        self.main_window = main_window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.setFixedSize(1920, 1080)
        self.bg = QPixmap("assets/images/usukuro.png")

        self.layout = QVBoxLayout()
        self.label = QLabel("You can change the display order of list items;"
        "<br>The item marked with '→' is currently selected;"
        "<br>You can also choose ascending or descending order;"
        "<br>The order you set here will be applied to all lists;"
        "<br>Press Save to apply the changes and return to the previous screen;")
        self.ok_btn = QPushButton("Save")
        self.font = QFont("Mv Boli", 25)
        self.font1 = QFont("Mv Boli", 15)
        self.label.setFont(self.font1)
        self.ok_btn.setFont(self.font)
        self.ok_btn.setStyleSheet("color: white; margin:100px; ")
        self.label.setStyleSheet("color: white; margin:100px;")

        self.order_toggle = QButtonGroup(self)
        self.asc_btn = HoverSoundButton("Ascending","assets\sounds\hover.wav")
        self.desc_btn = HoverSoundButton("Descending","assets\sounds\hover.wav")
        self.asc_btn.setFont(self.font1)
        self.desc_btn.setFont(self.font1)
        self.asc_btn.setCheckable(True)
        self.desc_btn.setCheckable(True)
        self.asc_btn.setChecked(True)  
        self.order_toggle.addButton(self.asc_btn, 0)
        self.order_toggle.addButton(self.desc_btn, 1)
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.HLine) 
        self.separator.setFrameShadow(QFrame.Sunken) 
        self.separator.setStyleSheet("color: white; background-color: white; height: 1px; margin: 20px 0px;")

        order_layout = QHBoxLayout()
        order_layout.addWidget(self.asc_btn)
        order_layout.addWidget(self.desc_btn)

        self.sort_options = ["Completed", "Priority", "Progress", "Duration", "Deadline", "Created"]#Deadline締切日Duration所要時間
        self.sort_buttons = []
        self.sort_group = QButtonGroup(self)  #ラジオボタン
        grid = QGridLayout()
        grid.setSpacing(20)

        for i, label in enumerate(self.sort_options):
            btn = HoverSoundButton(label,"assets\sounds\hover.wav")
            btn.setCheckable(True)
            btn.setFont(self.font1)
            btn.setStyleSheet("color: white; margin:0px; padding: 0px;")
            self.sort_group.addButton(btn, i)
            self.sort_buttons.append(btn)
            grid.addWidget(btn, i // 3, i % 3)  # 3列2行
        self.sort_buttons[4].setChecked(True)

        self.arrow_label = QLabel("→", self)
        self.arrow_label.setFont(self.font1)
        self.arrow_label.setStyleSheet("color: white; font-size: 30px; margin:0px;")
        #self.arrow_label.setFixedSize(70, 70)
        self.arrow_label.hide()
        self.sort_group.buttonClicked.connect(lambda _: update_arrow())

        self.layout.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)
        self.layout.addLayout(order_layout)       # 昇降順
        self.layout.addWidget(self.separator)  #白線
        self.layout.addLayout(grid)               # 並び替えボタン
        self.layout.addWidget(self.ok_btn)
        self.setLayout(self.layout)
        if main_window:
            self.setGeometry(main_window.geometry())

        def update_arrow():
            checked_btn = self.sort_group.checkedButton()
            for btn in self.sort_buttons:
                if btn == checked_btn:
                    btn.setStyleSheet("color: white; margin:0px; padding: 0px;")
                else:
                    btn.setStyleSheet("color: #888888; margin:0px; padding: 0px;")
            if checked_btn:
                pos = checked_btn.pos()
                self.arrow_label.move(pos.x() - 40, pos.y() + 10)
                self.arrow_label.show()

        def update_order_styles():
            for btn in [self.asc_btn, self.desc_btn]:
                if btn.isChecked():
                    btn.setStyleSheet("color: white;")
                else:
                    btn.setStyleSheet("color: #888888;")

        self.order_toggle.buttonClicked.connect(lambda _: update_order_styles())
        update_order_styles()
        self.sort_buttons[5].setChecked(True)
        update_arrow()

        # self.ok_btn.clicked.connect(lambda: (
        # self.main_window.todo_screen.apply_sorting(
        # self.sort_group.checkedId(),
        # 0 if self.asc_btn.isChecked() else 1),self.hide()))

        self.ok_btn.clicked.connect(lambda: (
    setattr(self.main_window, "current_sort_index", self.sort_group.checkedId()),
    setattr(self.main_window, "current_sort_order", 0 if self.asc_btn.isChecked() else 1),
    self.main_window.todo_screen.apply_sorting(
        self.main_window.current_sort_index,
        self.main_window.current_sort_order
    ),self.hide()))

    def paintEvent(self, event):    
        painter = QPainter(self)
        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

class ConfirmDialog(QWidget):
    def __init__(self, main_window=None):
        super().__init__(main_window)
        self.main_window = main_window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.setFixedSize(1920, 1080)
        self.bg = QPixmap("assets/images/usukuro.png")
        self.step = 0
        self.choice_mode = False

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignCenter)
        self.font = QFont("Mv Boli", 25)
        self.font1 = QFont("Mv Boli", 15)
        self.label = QLabel("This action cannot be undone;")
        self.label.setFont(self.font1)
        self.label.setStyleSheet("color: white; margin:100px;")
        self.talk = TalkAnimation("data/log1.xml", "assets/images/log1.png", "Once you decide, you can't undo it. <br>Do you really want to save?", parent=self)
        self.talk.setGeometry(0, -100, 1920, 1080)
        self.talk.show()

        btn_layout = QHBoxLayout()
        self.yes_btn = HoverSoundButton("Save","assets\sounds\hover.wav")
        self.no_btn = HoverSoundButton("Cansel","assets\sounds\hover.wav")
        self.yes_btn.setFont(self.font)
        self.no_btn.setFont(self.font)#background-color: red;
        self.yes_btn.setStyleSheet("color: white; margin:20px; margin-bottom:200px;")
        self.no_btn.setStyleSheet("color: white; margin:20px; margin-bottom:200px;")
        self.yes_btn.clicked.connect(self.on_yes_clicked)
        self.no_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.yes_btn)
        btn_layout.addWidget(self.no_btn)
        self.yes_btn.hide() 
        self.no_btn.hide()
        ########self.layout.addWidget(self.label)
        # self.layout.addWidget(self.talk)
        self.layout.addLayout(btn_layout)
        
        self.setLayout(self.layout)
        if main_window:
            self.setGeometry(main_window.geometry())

    def next_step(self):
        self.step += 1
        if self.step == 1:
            self.show_buttons()
            return
        
        if self.step == 2:#いらん
            self.close()

    def show_buttons(self):
        # if hasattr(self, "talk"):
        #     self.talk.hide()
            #del self.talk
        print("show?")#一回ボタンが表示されなくなることが。ゴミボタンを押した後の現象。print()を入れたら元に戻った。原因不明。
        self.choice_mode = True
        self.yes_btn.show()
        self.no_btn.show()
       
    def show_talk(self, xml, png, text):
        if hasattr(self, "talk"): # 既存talk消す
            self.talk.hide()

        self.talk = TalkAnimation(xml, png, text, parent=self)
        self.talk.setGeometry(0, 700, 1920, 380)
        self.talk.show()

    def on_yes_clicked(self):
        self.choice_mode = False
        if self.main_window:
            self.main_window.confirm_changes()
        self.close()

    def reset_dialog(self):
        self.step = 0
        self.choice_mode = False
        self.talk.full_text = "Once you decide, you can't undo it. Do you really want to save?"
        self.talk.current_index = 0 
        self.talk.text_label.setText("") 
        self.talk.is_text_animating = False
        self.yes_btn.hide()
        self.no_btn.hide()
        self.talk.show()
        self.talk.play(15, 40, 30)
    
    def showEvent(self, event):
        super().showEvent(event)# ウィンドウが表示された後にアニメ開始
        self.reset_dialog()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

    def keyPressEvent(self, event):
        print("どう？")
        if event.key() == Qt.Key_Return:
            if self.choice_mode:
                return
            if self.talk.is_text_animating:
                self.talk.text_timer.stop()
                self.talk.text_label.setText(self.talk.full_text)
                self.talk.is_text_animating = False
                return
            self.next_step()

class StartupLogDialog(QWidget):
    def __init__(self, main_window=None):
        super().__init__(main_window)
        self.main_window = main_window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.setFixedSize(1920, 1080)
        self.bg = QPixmap("assets/images/usukuro.png")
        self.step = 0
        self.choice_mode = False
        self.is_correct = None
        self.now = datetime.now()
        self.now_str = self.now.strftime("%Y/%m/%d %H:%M")
        self.username_text = ""

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignCenter)
        self.font = QFont("Mv Boli", 25)
        self.font1 = QFont("Mv Boli", 15)
        self.label = QLabel("This action cannot be undone;")
        self.label.setFont(self.font1)
        self.label.setStyleSheet("color: white; margin:100px;")
        self.talk = TalkAnimation("data/log1.xml", "log1.png",f"Hi! {self.username_text}!", parent=self)
        self.talk.setGeometry(0, -100, 1920, 1080)
        self.talk.show()

        btn_layout = QHBoxLayout()
        self.btn1 = HoverSoundButton("1","assets\sounds\hover.wav")
        self.btn2 = HoverSoundButton("2","assets\sounds\hover.wav")
        self.btn3 = HoverSoundButton("3","assets\sounds\hover.wav")
        self.btn1.setFont(self.font)
        self.btn2.setFont(self.font)
        self.btn3.setFont(self.font)#background-color: red;
        self.btn1.setStyleSheet("color: white; margin:20px; margin-bottom:200px;")
        self.btn2.setStyleSheet("color: white; margin:20px; margin-bottom:200px;")
        self.btn3.setStyleSheet("color: white; margin:20px; margin-bottom:200px;")
        self.btn1.clicked.connect(lambda: self.on_choice_clicked(self.btn1))
        self.btn2.clicked.connect(lambda: self.on_choice_clicked(self.btn2))
        self.btn3.clicked.connect(lambda: self.on_choice_clicked(self.btn3))
        btn_layout.addWidget(self.btn1)
        btn_layout.addWidget(self.btn2)
        btn_layout.addWidget(self.btn3)
        self.btn1.hide() 
        self.btn2.hide()
        self.btn3.hide()
        ########self.layout.addWidget(self.label)
        # self.layout.addWidget(self.talk)
        self.layout.addLayout(btn_layout)
        
        self.setLayout(self.layout)
        if main_window:
            self.setGeometry(main_window.geometry())

    def next_step(self):
        self.step += 1
        if self.step == 1:
            self.show_talk("data/log1.xml", "assets/images/log1.png", f"It's now {self.now_str}", 
                           loop_count=4, interval=40, text_speed=30)
            return
        if self.step == 2:
            self.show_talk("data/log_n.xml", "assets/images/log_n.png", "By the way, how many things do you think we need to get done by today?", 
                           loop_count=16, interval=40, text_speed=30)
            return
        if self.step == 3:
            self.show_buttons()
            return
        if self.step == 4:
            if self.is_correct:
                self.show_talk("data/log_si.xml", "assets/images/log_si.png", ".......", 
                               loop_count=6, interval=40, text_speed=30)
            else:
                self.show_talk("data/log1.xml", "assets/images/log1.png", "Wow! Nicely done!!", 
                               loop_count=5, interval=40, text_speed=30)
            return
        if self.step == 5:
            if self.is_correct:
                self.show_talk("data/log1.xml", "assets/images/log1.png", "That's right!", 
                               loop_count=6, interval=40, text_speed=30)
            else:
                self.show_talk("data/log_K.xml", "assets/images/log_K.png", "Incorrect.", 
                               loop_count=1, interval=100, text_speed=150)
        if self.step == 6:
            if self.is_correct:
                self.step += 1
                self.next_step()
            else:
                self.show_talk("data/log_lol.xml", "assets/images/log_lol.png", "Kidding!!!!! Just joking!!!!!", 
                               loop_count=1, interval=1, text_speed=30)
            return
        if self.step == 7:
            self.show_talk("data/log1.xml", "assets/images/log1.png",  f"The tasks due today are \n{self.title}\n a total of '{self.correct}' items.", 
                           loop_count=8, interval=40, text_speed=30)
            return
        if self.step == 8:
            if self.overdue_count > 0:
                self.show_talk("data/log_lol.xml", "assets/images/log_lol.png", f"And hey, there are also '{self.overdue_count}' items that are already past the deadline.(lol)", 
                               loop_count=16, interval=40, text_speed=30)
            else:
                self.step += 1
                self.next_step()
            return
        if self.step == 9:
            if self.overdue_count > 0:
                self.show_talk("data/log1.xml", "assets/images/log1.png", f"The one that's the most overdue is the one that was due by '{self.earliest_overdue_time}'.\n Is that alright?", 
                               loop_count=15, interval=40, text_speed=30)
            else:
                self.step += 1
                self.next_step()
            return
        if self.step == 10:
            if self.overdue_count > 0:
                self.show_talk("data/log1.xml", "assets/images/log1.png", f"By the way, the soonest deadline coming up is '{self.earliest_not_overdue_time}'.", 
                               loop_count=10, interval=40, text_speed=30)
            else:
                self.show_talk("data/log1.xml", "assets/images/log1.png", f"The next upcoming deadline is '{self.earliest_not_overdue_time}'.", 
                               loop_count=10, interval=40, text_speed=30)
            return
        if self.step == 11:
            if self.earliest_not_overdue_time == None:
                self.step += 1
                self.next_step()
            else:
                self.show_talk("data/log1.xml", "assets/images/log1.png", f"You've got '{self.remaining_hours}' hours and '{self.remaining_minutes}' minutes left.", 
                               loop_count=6, interval=40, text_speed=30)
            return
        if self.step == 12:
            self.show_talk("data/log1.xml", "assets/images/log1.png", "Have a nice day!", 
                           loop_count=6, interval=40, text_speed=30)
            return
        if self.step == 13:
            self.close()

    def show_buttons(self):
        self.choice_mode = True
        self.btn1.show()
        self.btn2.show()
        self.btn3.show()
        self.btn1.raise_() 
        self.btn2.raise_() 
        self.btn3.raise_()
       
    def show_talk(self, xml, png, text, loop_count, interval, text_speed):
        self.choice_mode = False
        if hasattr(self, "talk"): # 既存talk消す
            self.talk.hide()

        self.btn1.hide()
        self.btn2.hide()
        self.btn3.hide()
        self.talk = TalkAnimation(xml, png, text, parent=self)
        self.talk.setGeometry(0, -100, 1920, 380)
        self.talk.show()
        self.talk.play(loop_count, interval, text_speed)

    def update_user_name(self, new_name):
        self.username_text = new_name

    def update_count(self, due_today_count, due_today_titles, overdue_count, earliest_overdue_time, earliest_not_overdue_time, remaining_hours, remaining_minutes):
        self.correct = due_today_count
        self.due_today_titles = due_today_titles
        self.overdue_count = overdue_count#0もある
        self.earliest_overdue_time = earliest_overdue_time#0もある
        self.earliest_not_overdue_time = earliest_not_overdue_time
        self.remaining_hours = remaining_hours
        self.remaining_minutes = remaining_minutes

        self.title = "\n".join(f"「{item}」" for item in self.due_today_titles)
        self.generate_choices()

    def generate_choices(self):
        choices = {self.correct}
        while len(choices) < 3:
            offset = random.randint(-3, 3)
            wrong = self.correct + offset

            if wrong < 0:
                continue
            choices.add(wrong)
        sorted_choices = sorted(list(choices), reverse=True)
        self.btn1.setText(str(sorted_choices[0])) 
        self.btn2.setText(str(sorted_choices[1])) 
        self.btn3.setText(str(sorted_choices[2]))
    
    def on_choice_clicked(self, btn):
        self.choice_mode = False
        selected = int(btn.text())  # ボタンの数字
        self.is_correct = (selected == self.correct)
        self.setFocus()
        self.next_step()

    def reset_dialog(self):
        self.step = 0
        self.talk.full_text = f"Hi! {self.username_text}!"
        self.talk.current_index = 0 
        self.talk.text_label.setText("") 
        self.talk.is_text_animating = False
        self.btn1.hide()
        self.btn2.hide()
        self.btn3.hide()
        self.talk.show() 
        self.talk.play(15, 4, 30)
    
    def showEvent(self, event):
        super().showEvent(event)# ウィンドウが表示された後にアニメ開始
        self.reset_dialog()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()
        
    def paintEvent(self, event):    
        painter = QPainter(self)
        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            if self.choice_mode:
                return

            if self.talk.is_text_animating:
                self.talk.text_timer.stop()
                self.talk.text_label.setText(self.talk.full_text)
                self.talk.is_text_animating = False
                return
            self.next_step()

class HeaderOverlay(QWidget):
    def __init__(self, parent=None ,main_window=None, user_name=""):
        super().__init__(parent)
        self.main_window = main_window
        self.user_name = user_name
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.bg = QPixmap("assets/images/ヘッダー.png")
        self.setGeometry(0, 0, parent.width(), 180)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(30)

        self.username_label = QLabel("unknown")
        self.username_label.setText(user_name)
        self.username_label.setStyleSheet("""QLabel {
                font-size: 100px;
                letter-spacing: 10px;
                font-weight: bold;
                color: white;
                font-family: "Mv Boli";}""")
        
        self.label_completed = QLabel()
        base = QPixmap("assets/images/空白下用.png").scaled(160, 130)
        badge0 = QPixmap("assets/images/達成度せん.png").scaled(160, 130)
        badge = QPixmap("assets/images/達成度せん.png").scaled(160, 130)
        p = QPainter(base)
        p.drawPixmap(0, 0, badge0)
        p.drawPixmap(0, 0, badge)
        p.setPen(QColor("white"))
        p.setFont(QFont("Mv Boli", 24))
        p.drawText(0, 130, "100%")
        p.end()
        self.label_completed.setPixmap(base)
        self.label_completed.setFixedWidth(160)

        self.label_mochivation = QLabel()
        base2 = QPixmap("assets/images/空白下用.png").scaled(160, 130)
        badge02 = QPixmap("assets/images/やる気せん.png").scaled(160, 130)
        badge2 = QPixmap("assets/images/やる気せん.png").scaled(160, 130)
        p2 = QPainter(base2)
        p2.drawPixmap(0, 0, badge02) 
        p2.drawPixmap(0, 0, badge2)  
        p2.setPen(QColor("white"))
        p2.setFont(QFont("Mv Boli", 24))
        p2.drawText(0, 130, "100%")
        p2.end()
        self.label_mochivation.setPixmap(base2)
        self.label_mochivation.setFixedWidth(160)

        self.change_btn = QPushButton()
        self.change_btn.setFixedSize(100, 100)
        self.change_btn = HoverIconSoundButton("assets/images/並び替え.png", "assets/images/並び替え.png", "assets\sounds\hover.wav")
        self.change_btn.setIconSize(QSize(100, 100))
        self.change_btn.setStyleSheet("background: transparent; border: none;")

        self.option_btn = QPushButton()
        self.option_btn.setFixedSize(100, 100)
        self.option_btn = HoverIconSoundButton("assets/images/設定.png", "assets/images/設定h.png", "assets\sounds\hover.wav")
        self.option_btn.setIconSize(QSize(100, 100))
        self.option_btn.setStyleSheet("background: transparent; border: none;")

        self.award_btn = QPushButton()
        self.award_btn.setFixedSize(100, 100)
        self.award_btn = HoverIconSoundButton("assets/images/実績.png", "assets/images/実績h.png", "assets\sounds\hover.wav")
        self.award_btn.setIconSize(QSize(100, 100))
        self.award_btn.setStyleSheet("background: transparent; border: none;")

        self.menu_btn = QPushButton()
        self.menu_btn.setFixedSize(100, 100)
        self.menu_btn = HoverIconSoundButton("assets/images/メニュー.png", "assets/images/メニューh.png", "assets\sounds\hover.wav")
        self.menu_btn.setIconSize(QSize(100, 100))
        self.menu_btn.setStyleSheet("background: transparent; border: none;")

        layout.addWidget(self.label_completed)
        layout.addWidget(self.label_mochivation)
        layout.addWidget(self.username_label)
        layout.addWidget(self.change_btn)
        layout.addWidget(self.option_btn)
        layout.addWidget(self.award_btn)
        layout.addWidget(self.menu_btn)
        
        self.option_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.option_btn, lambda: self.main_window.fade_to(self.main_window.option_screen)))
        self.award_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.award_btn, lambda: self.main_window.fade_to(self.main_window.award_screen)))
        self.menu_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.menu_btn, lambda: self.main_window.fade_to(self.main_window.menu_screen)))
        self.change_btn.clicked.connect(lambda checked=False: self.open_change())
        self.change_dialog = ChangeDialog(main_window=self.main_window)
        self.change_dialog.hide()
        self.update_achievement()

    def update_achievement(self):
        data = self.main_window.todo_data_store
        self.high = 0
        self.task = 0
        achieve_count_now = 0
        if not data:
        # データがないときは0%の画像を作る
            rate_text = "0%"
        else:
            # self.main_windiw.save_count = max(int(item["id"].replace("data", "")) for item in data)
            self.task = len(data)
            achieve_count_now = sum(item.get("completed", 0) for item in data)
            rate = achieve_count_now / self.task if self.task > 0 else 0
            self.high = max(1, int(130 * rate))
            rate = rate * 100
            rate_text = f"{int(rate)}%"
        base = QPixmap("assets/images/空白下用.png").scaled(160, 130)
        badge0_full = QPixmap("assets/images/達成度いろ.png").scaled(160, 130)
        badge0 = badge0_full.copy(0, 130 - self.high, 160, self.high)
        badge = QPixmap("assets/images/達成度せん.png").scaled(160, 130)

        p = QPainter(base)
        p.drawPixmap(0, 130 - self.high, badge0)
        p.drawPixmap(0, 0, badge)
        p.setPen(QColor("white"))
        p.setFont(QFont("Mv Boli", 24))
        p.drawText(0, 130, rate_text)
        p.end()
        self.label_completed.setPixmap(base)
        print("self.task", self.task)
        print("achieve_count_now", achieve_count_now)

    def update_mochivation(self,weekly_total):
        self.high2 = 0
        rate2 = weekly_total
        rate2_00 = rate2 // 10
        if rate2_00 > 100:
            rate2_00 = 100
        self.high2 = max(1, int(130 * (rate2_00 / 100)))
        rate_text2 = f"{int(rate2)}"
        base2 = QPixmap("assets/images/空白下用.png").scaled(160, 130)
        badge02_full = QPixmap("assets/images/やる気いろ.png").scaled(160, 130)
        badge02 = badge02_full.copy(0, 130 - self.high2, 160, self.high2)
        badge2 = QPixmap("assets/images/やる気せん.png").scaled(160, 130)

        p2 = QPainter(base2)
        p2.drawPixmap(0, 130 - self.high2, badge02)
        p2.drawPixmap(0, 0, badge2)
        p2.setPen(QColor("white"))
        p2.setFont(QFont("Mv Boli", 24))
        p2.drawText(0, 130, rate_text2)
        p2.end()
        self.label_mochivation.setPixmap(base2)
        print("rate2", rate2)

    def update_user_name(self, new_name):
        self.username_label.setText(new_name)

    def open_change(self):
        self.change_dialog.show()
        self.change_dialog.raise_()  
        self.change_dialog.activateWindow()

    def paintEvent(self, event):
        painter = QPainter(self)
        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

class BackgroundListWidget(QListWidget):
    def __init__(self, bg_path):
        super().__init__()
        self.bg = QPixmap(bg_path)
        spacer = QListWidgetItem()
        spacer.setSizeHint(QSize(0, 340))
        self.addItem(spacer)

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        scroll_offset = self.verticalScrollBar().value()

        scaled_bg = self.bg.scaledToWidth(self.viewport().width(), Qt.SmoothTransformation)
        painter.drawPixmap(0, -scroll_offset, scaled_bg)
        super().paintEvent(event)

class ToDoItemWidget(QWidget):
    def __init__(self, text, glyphs, sheets, max_width, item_id, item_data, main_window):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.main_window = main_window
        self.item_data = item_data
        self.item_id = item_id
        self.temp_completed = False
        self.temp_deleted = False
        self.glyphs = glyphs
        self.sheets = sheets

        #  チェックボタンの元
        self.check_btn = QPushButton()
        self.check_btn = HoverIconSoundButton("assets/images/チェックボタン.png", "assets/images/チェックボタンh.png","assets\sounds\hover.wav")
        self.check_btn.setIconSize(QSize(80, 80))
        self.check_btn.setFlat(True)
        self.check_btn.setStyleSheet("padding: 0px; margin: 0px; border: none;")
        if self.item_data.get("completed", 0) == 1:#おまけにagainは必ず0　　　1,0
            self.check_btn.normal_icon = QIcon("assets/images/達成.png")
            self.check_btn.hover_icon  = QIcon("assets/images/達成.png")
            self.check_btn.setIcon(self.check_btn.normal_icon)
        elif self.item_data.get("again") == 1:#    0,1
            self.update_check_image_count(self.item_data.get("again_count", 0))
            self.check_btn.setIcon(self.check_btn.normal_icon)
        else:#   0,0
            self.check_btn.normal_icon = QIcon("assets/images/チェックボタン.png")
            self.check_btn.hover_icon  = QIcon("assets/images/チェックボタンh.png")
            self.check_btn.setIcon(self.check_btn.normal_icon)
        
        #  スプライト文字
        self.text_renderer = TextRenderer(text, glyphs, sheets, max_width)
        self.text_renderer.setFixedWidth(1200)

        self.sort_info_label = QLabel("")
        self.sort_info_label.setStyleSheet("font-family: Mv Boli; color: black; font-size: 30px; margin: 0px;")

        #  編集ボタン
        self.edit_btn = QPushButton()
        self.edit_btn = HoverIconSoundButton("assets/images/編集.png", "assets/images/編集h.png", "assets\sounds\hover.wav")
        self.edit_btn.setIconSize(QSize(80, 80))
        self.edit_btn.setFlat(True)
        self.edit_btn.setStyleSheet("padding: 0px; margin : 0px; border: none;")

        self.edit_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.edit_btn,lambda: self.main_window.show_data_screen(self.item_data)))
        #self.edit_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.edit_btn,lambda: self.main_window.fade_to(self.main_window.data_screen)))

        #  削除ボタン
        self.delete_btn = QPushButton()
        self.delete_btn = HoverIconSoundButton("assets/images/ゴミ箱.png", "assets/images/ゴミ箱h.png", "assets\sounds\hover.wav")
        self.delete_btn.setIconSize(QSize(80, 80))
        self.delete_btn.setFlat(True)
        self.delete_btn.setStyleSheet("padding: 0px; margin: 0px; border: none;")
        layout.addSpacing(275)
        layout.addWidget(self.check_btn)
        layout.addSpacing(0)
        layout.addWidget(self.text_renderer)
        layout.addStretch()  #空間
        layout.addWidget(self.sort_info_label)
        layout.addWidget(self.edit_btn)
        layout.addWidget(self.delete_btn)
        layout.addSpacing(60)
        self.setLayout(layout)

        self.check_btn.clicked.connect(self.toggle_completed)
        self.delete_btn.clicked.connect(self.toggle_deleted)

    def toggle_completed(self):
        self.temp_completed = not self.temp_completed
        if self.temp_completed:
            self.check_btn.normal_icon = QIcon("assets/images/チェックあり.png")
            self.check_btn.hover_icon  = QIcon("assets/images/チェックありh.png")
            self.check_btn.setIcon(self.check_btn.normal_icon)
        else:
            self.check_btn.normal_icon = QIcon("assets/images/チェックボタン.png")
            self.check_btn.hover_icon  = QIcon("assets/images/チェックボタンh.png")
            self.check_btn.setIcon(self.check_btn.normal_icon)

    def toggle_deleted(self):
        self.temp_deleted = not self.temp_deleted
        self.text_renderer.setStrikeOut(self.temp_deleted)

    def set_sort_info(self, info_text):
        self.sort_info_label.setText(info_text)

    def update_check_image(self):
        if self.temp_completed:
            self.check_btn.normal_icon = QIcon("assets/images/チェックあり.png")
            self.check_btn.hover_icon  = QIcon("assets/images/チェックありh.png")
            self.check_btn.setIcon(self.check_btn.normal_icon)
        else:
            self.check_btn.normal_icon = QIcon("assets/images/チェックボタン.png")
            self.check_btn.hover_icon  = QIcon("assets/images/チェックボタンh.png")
            self.check_btn.setIcon(self.check_btn.normal_icon)

    def update_check_image_count(self, again_c):
        self.again_c = again_c
        if self.again_c > 99:
            self.again_c = 99

        digits = len(str(self.again_c))
        if self.item_data.get("again", 0) == 1:
            base_pixmap = QPixmap("assets/images/チェックボタン.png")

        # 数字用 TextRenderer
            number_renderer = NumberRenderer(str(self.again_c), self.glyphs, self.sheets, 40 * digits)
            number_renderer.setAttribute(Qt.WA_TranslucentBackground)
            number_renderer.setStyleSheet("background: transparent;")
            number_renderer.adjustSize()
        # grab → scale で縮小
            number_pixmap = number_renderer.grab()
            number_pixmap = number_pixmap.scaled(
                20 * digits, 20,  # 桁数に応じて幅を広げる
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation)
        # 合成
            painter = QPainter(base_pixmap)
            pos_x = base_pixmap.width() - number_pixmap.width() - 5
            pos_y = base_pixmap.height() - number_pixmap.height() - 5
            painter.drawPixmap(pos_x, pos_y, number_pixmap)
            painter.end()
        # QIcon に変換
            self.check_btn.normal_icon = QIcon(base_pixmap)
            self.check_btn.hover_icon  = QIcon(base_pixmap)
            self.check_btn.setIcon(self.check_btn.normal_icon)
    
class ToDoApp(QWidget):
    def __init__(self, main_window, user_name, data_list):
        super().__init__()
        self.main_window = main_window
        self.user_name = user_name
        self.setWindowTitle("スプライトToDoリスト")
        self.bg = QPixmap("assets/images/background0.png")
        self.data_file = "data/todo_data.json"
        self.todo_data_store = data_list or []
        self.startup_log_shown = False
        self.start_log = StartupLogDialog(self)

        with open("data/font.json", "r", encoding="utf-8") as f:
            self.glyphs = json.load(f)

        self.sheets = {
            "assets/images/フォント2.png": QPixmap("assets/images/フォント2.png"),
            "assets/images/フォント1.png": QPixmap("assets/images/フォント1.png")
        }
        self.free_list = BackgroundListWidget("assets/images/list_0.png")
        self.study_list = BackgroundListWidget("assets/images/list_mido.png")
        self.unknown_list = BackgroundListWidget("assets/images/list_aka.png")

# スタイル設定（共通）
        for lw in [self.free_list, self.study_list, self.unknown_list]:
            lw.setStyleSheet("""QListWidget {
        background: transparent;
        color: white;
        font-size: 16px;
        margin: 0px;
        padding: 0px;
        border: none;
        outline: none;}
        QListWidget::item:selected {
        background: transparent;
        outline: none;}
        QListWidget::item:hover {
        background: transparent;}""")
            lw.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            lw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.list_container = QWidget()
        self.list_stack = QStackedLayout(self.list_container)
        
        self.list_stack.addWidget(self.free_list)
        self.list_stack.addWidget(self.study_list)
        self.list_stack.addWidget(self.unknown_list)
        self.list_container.setLayout(self.list_stack)
        self.genre2_btn = QPushButton()
        self.genre2_btn.setParent(self.list_container)  #リストと同じ親
        self.genre2_btn.setFixedSize(1630, 3858)
        self.genre2_btn.setIcon(QIcon("assets/images/list_2.png"))
        self.genre2_btn.setIconSize(QSize(1630, 3858))
        #self.genre2_btn.setFlat(True)
        self.genre2_btn.setStyleSheet("border: none; background: transparent;")
        self.genre2_btn.move(30,40)
        self.genre1_btn = QPushButton()
        self.genre1_btn.setParent(self.list_container)  
        self.genre1_btn.setFixedSize(1630, 3858)
        self.genre1_btn.setIcon(QIcon("assets/images/list_1.png"))
        self.genre1_btn.setIconSize(QSize(1630, 3858))
        #self.genre1_btn.setFlat(True)
        self.genre1_btn.setStyleSheet("border: none; background: transparent;")
        self.genre1_btn.move(30,40) 
        self.real1_btn = HoverButton(self.genre1_btn, self.list_container)
        self.real1_btn.move(30, 40)
        self.real1_btn.setStyleSheet("background: transparent; border: none; qproperty-icon: none;")
        pixmap1 = QPixmap("assets/images/list_1B.png")  # 透過部分あり
        self.real1_btn.setIcon(QIcon(pixmap1))
        self.real1_btn.setIconSize(pixmap1.size())
        self.real1_btn.setFixedSize(pixmap1.size())
        self.real1_btn.setMask(pixmap1.mask())
        self.real2_btn = HoverButton(self.genre2_btn, self.list_container)
        self.real2_btn.move(30, 40)
        self.real2_btn.setStyleSheet("background: transparent; border: none; qproperty-icon: none;")
        pixmap2 = QPixmap("assets/images/list_2B.png")  # 透過部分あり
        self.real2_btn.setIcon(QIcon(pixmap2))
        self.real2_btn.setIconSize(pixmap2.size())
        self.real2_btn.setFixedSize(pixmap2.size())
        self.real2_btn.setMask(pixmap2.mask())
        self.genre2_btn.raise_()
        self.genre1_btn.raise_()
        self.free_list.raise_()
        self.real2_btn.raise_()
        self.real1_btn.raise_()
        # スクロール領域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.list_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 全体レイアウト
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        # layout.addWidget(self.input_field)
        self.layout.addWidget(self.scroll_area)
        self.setLayout(self.layout)

        self.header_overlay = HeaderOverlay(parent=self, main_window=self.main_window, user_name=self.user_name)
        self.header_overlay.show()
        self.header_overlay.raise_()

        self.pen_btn = QPushButton()
        self.pen_btn = HoverIconSoundButton("assets/images/鉛筆m.png", "assets/images/鉛筆m.png", "assets\sounds\hover.wav")
        self.pen_btn.setParent(self)
        self.pen_btn.setFixedSize(177,315)
        self.pen_btn.setIconSize(QSize(177,315))
        self.pen_btn.setFlat(True)
        self.pen_btn.move(-20, 1080-315)
        self.pen_btn.setStyleSheet("border: none; background: transparent; padding: 0px; margin: 0px;")
        self.pen_btn.raise_()
        self.pen_btn.installEventFilter(self)
        self.stamp_btn = QPushButton()
        self.stamp_btn = HoverIconSoundButton("assets/images/ハンコ.png", "assets/images/ハンコ.png", "assets\sounds\hover.wav")
        self.stamp_btn.setParent(self)
        self.stamp_btn.setFixedSize(142,174)
        self.stamp_btn.setIconSize(QSize(142,174))
        self.stamp_btn.setFlat(True)
        self.stamp_btn.move(-30, 200)

        self.stamp_btn.setStyleSheet("border: none; background: transparent; padding: 0px; margin: 0px;")
        self.stamp_btn.raise_()
        self.stamp_btn.installEventFilter(self)
        self.current_genre = 0#どのTypeが表示されてるかの基準
        self.real1_btn.clicked.connect(self.toggle_genre1)
        self.real2_btn.clicked.connect(self.toggle_genre2)

        self.pen_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.pen_btn, lambda: self.main_window.fade_to(self.main_window.edit_screen)))
        self.stamp_btn.clicked.connect(lambda checked=False: self.open_confirm())
        self.confirm_dialog = ConfirmDialog(self)
        self.confirm_dialog.hide() 
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(800, 600)

    def open_confirm(self):
        self.confirm_dialog.show()
        self.confirm_dialog.raise_()  
        self.confirm_dialog.activateWindow()

    def confirm_changes(self):
        self.add_achieve = 0
        for lw in [self.free_list, self.study_list, self.unknown_list]:
            for i in range(lw.count()):
                widget = lw.itemWidget(lw.item(i))
                if isinstance(widget, ToDoItemWidget):
                    if widget.temp_deleted:
                    # 削除確定
                        if widget.item_data in self.todo_data_store:
                            self.todo_data_store.remove(widget.item_data)
                            self.main_window.info["delete_count"] =  self.main_window.info.get("delete_count", 0) + 1
                    elif widget.temp_completed: # 達成確定
                        self.add_achieve += 1
                        if widget.item_data["again"] == 0:
                            widget.item_data["completed"] = 1
                            widget.item_data["completed date"] = datetime.now().strftime("%Y/%m/%d %H:%M")
                            widget.update_check_image()
                        elif widget.item_data["again"] == 1:
                            self.again_c = widget.item_data["again_count"] + 1
                            widget.item_data["again_count"] = self.again_c
                            widget.update_check_image_count(self.again_c)
                            again_max = self.main_window.info.get("again_max", 0) 
                            if self.again_c > again_max: 
                                self.main_window.info["again_max"] = self.again_c
    # 表示更新
        self.new_achieve = self.main_window.info.get("achieve_count", 0)
        self.new_achieve = self.add_achieve +  self.new_achieve
        self.main_window.info["achieve_count"] = self.new_achieve
        self.main_window.save_data()
        self.apply_sorting(self.main_window.current_sort_index, self.main_window.current_sort_order)

    def apply_sorting(self, sort_index, sort_order):
        self.data_list = self.todo_data_store
         #indexて呼び出す"Date", "Priority", "Progress", "Duration", "Deadline", "Created"
        incomplete_items = [item for item in self.data_list if item.get("completed", 0) == 0]
        completed_items  = [item for item in self.data_list if item.get("completed", 0) == 1]
        if sort_index == 0:
            sorted_data = self.sort_by_completed_date(completed_items)
        elif sort_index == 1:
            sorted_data = self.sort_by_priority(incomplete_items)
        elif sort_index == 2:
            sorted_data = self.sort_by_progress(incomplete_items)
        elif sort_index == 3:
            sorted_data = self.sort_by_duration(incomplete_items)# 所要時間
        elif sort_index == 4:
            sorted_data = self.sort_by_deadline(incomplete_items)#締切日
        elif sort_index == 5:
            sorted_data = self.sort_by_created(incomplete_items)
        else:
            sorted_data = self.data_list  # fallback予備処理
    # 昇降順切り替え
        if sort_order == 1:
            sorted_data.reverse()
        if sort_index == 0:
            sorted_data = sorted_data + incomplete_items
        self.refresh_display(sorted_data)

    def add_todo_by_genre(self, data):
        genre = data.get("type_index", 0)
        bullet_text = f"・{data['todo']}"
        item = QListWidgetItem()
        item.setData(Qt.UserRole, data)
        item_id = data.get("id", 0)
        item_data = data
        widget = ToDoItemWidget(bullet_text, self.glyphs, self.sheets, max_width=1600, item_id=item_id, item_data=item_data, main_window=self.main_window)
        item.setSizeHint(widget.sizeHint())
        widget.set_sort_info(self.get_sort_info(data))
        if genre == 0:
            self.free_list.addItem(item)
            self.free_list.setItemWidget(item, widget)
            self.update_list_height(self.free_list)
        elif genre == 1:
            self.study_list.addItem(item)
            self.study_list.setItemWidget(item, widget)
            self.update_list_height(self.study_list)
        else:
            self.unknown_list.addItem(item)
            self.unknown_list.setItemWidget(item, widget)
            self.update_list_height(self.unknown_list)

    def get_sort_info(self, data):
        index = self.main_window.current_sort_index
        if index == 0:  # Created → 3行
            completed = data.get("completed date", "")
            if not completed:  # 空文字や None の場合
               return "--"
            try:
               date_part, time_part = completed.split()
               year, month, day = date_part.split("/")
               return f"{year}\n{month}/{day}\n{time_part}"
            except Exception:
                return completed or "--"
        elif index == 1:  # Priority → 1行
            priority = data.get("priority", -1)
            return {0: "L", 1: "M", 2: "H"}.get(priority, "No")
        elif index == 2:  # Progress → 1行
            return f"{data.get('progress', 0)}%"
        elif index == 3:  # Duration → 2行（h / m）
            duration = data.get("duration", "")
            parts = duration.split()
            return "\n".join(parts)  # 2行表示
        elif index == 4:  # Deadline → 3行（年 / 月日 / 時間）
            date = data.get("date", "")
            try:
                date_part, time_part = date.split()
                year, month, day = date_part.split("/")
                return f"{year}\n{month}/{day}\n{time_part}"
            except:
                return date
        elif index == 5:  # Created → 3行
            created = data.get("created", "")
            try:
                date_part, time_part = created.split()
                year, month, day = date_part.split("/")
                return f"{year}\n{month}/{day}\n{time_part}"
            except:
                return created
        else:
            return ""
    
    def sort_by_completed_date(self, data_list):
        def parse_completed(item):
            if item.get("completed", 0) == 1:
                try:
                    return datetime.strptime(item.get("completed date", ""), "%Y/%m/%d %H:%M")
                except ValueError:
                    return datetime.max
            else: # completed=0 は一番=最大値 
                return datetime.max
        return sorted(data_list, key=parse_completed)

    def sort_by_deadline(self, data_list):
        def parse_date(item):
            try:
                return datetime.strptime(item.get("date", ""), "%Y/%m/%d %H:%M")
            except ValueError:
                return datetime.max  # 不正日付は一番遠い扱い
        return sorted(data_list, key=parse_date)
    
    def sort_by_priority(self, data_list):
        return sorted(data_list, key=lambda x: x.get("priority", 0))#reverse=Trueか0
    
    def sort_by_progress(self, data_list):
        return sorted(data_list, key=lambda x: x.get("progress", 0))
    
    def sort_by_duration(self, data_list):
        import re
        def parse_duration(duration_str):
            match = re.match(r"(\d+)h\s*(\d+)m", duration_str)
            if match:
                return int(match.group(1)) * 60 + int(match.group(2))
            return 0
        return sorted(data_list, key=lambda x: parse_duration(x.get("duration", "0h 0m")))
    
    def sort_by_created(self, data_list):
        def extract_id_number(item):
            id_str = item.get("id", "")
            try:
                return int(id_str.replace("data", ""))
            except ValueError:
                return 0  # 不正なIDは一番下に
        return sorted(data_list, key=extract_id_number, reverse=True)  # 新しい順（IDが大きい順）
    
    def refresh_display(self, data_list=None):
        self.free_list.clear()
        self.study_list.clear()
        self.unknown_list.clear()
        # 空白アイテム
        spacer = QListWidgetItem()
        spacer.setSizeHint(QSize(0, 340))
        self.free_list.addItem(spacer)
        self.study_list.addItem(spacer.clone())
        self.unknown_list.addItem(spacer.clone())

        target_list = data_list or self.todo_data_store
        for data in target_list:
            print("追加するToDo:", data.get("todo"), "ジャンル:", data.get("type_index"))
            self.add_todo_by_genre(data)

    def update_list_height(self, list_widget):
        total_height = 340
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            widget = list_widget.itemWidget(item)
            if widget:
                total_height += widget.sizeHint().height()
        list_widget.setMinimumHeight(total_height)

    def toggle_genre1(self):
        if self.current_genre == 1:
            print("ジャンル1からジャンル0に戻す")
            self.switch_genre(0)
        else:
            print("ジャンル1に切り替え")
            self.switch_genre(1)

    def toggle_genre2(self):
        if self.current_genre == 2:
            print("ジャンル2からジャンル0に戻す")
            self.switch_genre(0)
        else:
            print("ジャンル2に切り替え")
            self.switch_genre(2)

    def switch_genre(self, genre_index):
        print("ジャンル切り替え:", genre_index)
        self.current_genre = genre_index
        self.list_stack.setCurrentIndex(genre_index)
        self.real2_btn.raise_()
        self.real1_btn.raise_()
    #切り替え0:1,2  1:0,2  2:0,1
        if genre_index == 0:
            self.genre1_btn.setIcon(QIcon(QPixmap("assets/images/list_1.png")))
            self.genre2_btn.setIcon(QIcon(QPixmap("assets/images/list_2.png")))
        elif genre_index == 1:
            self.genre1_btn.setIcon(QIcon(QPixmap("assets/images/list_01.png")))
            self.genre2_btn.setIcon(QIcon(QPixmap("assets/images/list_2.png")))
        elif genre_index == 2:
            self.genre1_btn.setIcon(QIcon(QPixmap("assets/images/list_1.png")))
            self.genre2_btn.setIcon(QIcon(QPixmap("assets/images/list_02.png")))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            self.animate_button_shift(obj, shift_x=20)
        elif event.type() == QEvent.Leave:
            self.animate_button_shift(obj, shift_x=0)
        return super().eventFilter(obj, event)

    def animate_button_shift(self, button, shift_x):
        if not hasattr(button, "original_pos"):
            button.original_pos = button.pos()

        target_pos = button.original_pos + QPoint(shift_x, 0)
        anim = QPropertyAnimation(button, b"pos")
        anim.setDuration(200)
        anim.setStartValue(button.pos())
        anim.setEndValue(target_pos)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()  
        self._hover_anim = anim 
        
    def focusInEvent(self, event):
        self.free_list.setFocus()
        super().focusInEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.header_overlay.setGeometry(0, 0, self.width(), 180)

    def reset_temp_states(self):
        for lw in [self.free_list, self.study_list, self.unknown_list]:
            for i in range(lw.count()):
                widget = lw.itemWidget(lw.item(i))
                if isinstance(widget, ToDoItemWidget):
                    widget.temp_completed = False
                    widget.temp_deleted = False
                    widget.sort_info_label.setText("")
                    widget.text_renderer.setStrikeOut(False)

    def paintEvent(self, event):
        painter = QPainter(self)
        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.startup_log_shown:
            self.startup_log_shown = True
            self.main_window.calculate_today_info()
            self.show_startup_log()
            
    def show_startup_log(self):
        #self.start_log = StartupLogDialog(self)
        self.start_log.show()
        self.start_log.raise_()
        self.start_log.activateWindow()

class SliderWithBar(QWidget):
    valueChanged = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        # バーの背景（灰色）
        self.bar_bg = QFrame(self)
        self.bar_bg.move(30, 30)
        self.bar_bg.setStyleSheet("background-color: lightgray; padding:0px 0px 0px 0px;")
        self.bar_bg.setContentsMargins(0, 0, 0, 0)
        self.bar_bg.setFixedHeight(20)
        self.bar_bg.setFixedWidth(580)
        # 赤い矩形（進捗部分）
        self.bar_red = QFrame(self)
        self.bar_red.move(30, 30)
        self.bar_red.setStyleSheet("background-color: #2e8b57;")
        self.bar_bg.setContentsMargins(0, 0, 0, 0)
        self.bar_red.setFixedHeight(20)
        self.bar_red.setFixedWidth(0)  # 初期は0
        # バーの背景を画像に置き換え
        self.bar_bg = QLabel(self)
        self.bar_bg.move(30-2, 30-3)
        pixmap_bg = QPixmap("assets/images/枠線.png").scaled(582, 23, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.bar_bg.setPixmap(pixmap_bg)
        self.bar_bg.setFixedSize(582, 23)

        # つまみ画像（QLabel）  
        self.knob = QLabel(self) 
        self.knob.move(30, 0)
        self.knob.setContentsMargins(0, 0, 0, 0)
        pixmap = QPixmap("assets/images/顔アイコン.png").scaled(170, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation) 
        self.knob.setPixmap(pixmap) 
        self.knob.setFixedSize(170, 70)
        # スライダー
        self.slider = QSlider(Qt.Horizontal,self)
        self.slider.move(30, 30)
        self.slider.setRange(0, 100)
        self.slider.setValue(0)
        self.slider.setTickInterval(10)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setFixedWidth(580)
        self.slider.setFixedHeight(50)#
        self.slider.setStyleSheet("QSlider::groove:horizontal {height:50px;background:transparent;}" 
                                  "QSlider::handle:horizontal {width:50px; height:50px;}")
        self.slider.raise_()
        self.slider.valueChanged.connect(self.update_bar)

    def update_bar(self, value):
        # スライダーの値に応じて赤いバーの幅を更新
        total_width = self.bar_bg.width()
        new_width = int(total_width * value / 100)
        self.bar_red.setFixedWidth(new_width)
        # つまみ画像の位置更新 
        knob_x = int((total_width-20) * value / 100) - self.knob.width() // 2 
        #knob_y = self.bar_bg.y() - (self.knob.height() // 2 - self.bar_bg.height() // 2) 
        self.knob.move(knob_x+30, 0)

    def setValue(self, value): 
        self.slider.setValue(value)
        self.update_bar(value) 

    def value(self): 
        return self.slider.value()

class DataScreen(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.item_data = None
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.bg = QPixmap("assets/images/memo_siro.png")  # ← 背景画像を読み込む
        with open("data/font.json", "r", encoding="utf-8") as f:
            self.glyphs = json.load(f)
        self.sheets = {
            "assets/images/フォント2.png": QPixmap("assets/images/フォント2.png"),
            "assets/images/フォント1.png": QPixmap("assets/images/フォント1.png")
        }      
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        
        # 固定のとこ
        self.back_btn = HoverIconSoundButton("assets/images/戻る.png", "assets/images/戻るh.png", "assets\sounds\hover.wav")
        self.back_btn.setFixedWidth(80)
        self.back_btn.setIconSize(QSize(80, 80))
        self.back_btn.setStyleSheet("background: transparent; border: none; margin: 0px;")
        self.back_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.back_btn, lambda: self.main_window.fade_to(self.main_window.todo_screen)))
        
        self.top_layout = QHBoxLayout()
        self.top_layout.setSpacing(0)
        self.top_layout.setAlignment(Qt.AlignCenter)
        # タイトル用のスプライト文字ラベル
        self.title_renderer = TextRenderer("title",self.glyphs,self.sheets,max_width=1600)
        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setWidget(self.title_renderer)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedWidth(1600-308)
        self.scroll.setFixedHeight(220)  # 2行分
        self.lay_444 = QVBoxLayout()
        self.label_pr = QLabel()
        self.label_pr.setPixmap(QPixmap("assets/images/星1.png"))
        self.label_pr.setScaledContents(True)
        self.label_pr.setFixedSize(308, 70)
        # self.label_du = QLabel("duration")
        # self.label_du.setScaledContents(True)  
        # self.label_du.setFixedSize(361, 95)
        self.lay_444.addWidget(self.label_pr)
        # self.lay_444.addWidget(self.label_du)

        self.top_layout.addWidget(self.back_btn, alignment=Qt.AlignLeft)
        self.top_layout.addStretch()
        self.top_layout.addWidget(self.scroll)
        self.top_layout.addStretch()
        self.top_layout.addLayout(self.lay_444)
        self.main_layout.addLayout(self.top_layout)

        self.overlay_img = QLabel(self)
        self.overlay_img.setPixmap(QPixmap("assets/images/datamemo改.png"))  # ←重ねたい画像
        self.overlay_img.setStyleSheet("border: none; background: transparent; padding: 0px; margin: 0px;")

        # 文字ラベルを複数配置
        self.lay11 = QHBoxLayout()
        self.lay22 = QHBoxLayout()
        self.lay33 = QHBoxLayout()
        self.lay44 = QHBoxLayout()
        self.lay55 = QHBoxLayout()
        self.lay66 = QHBoxLayout()
        
        self.font = QFont("Mv Boli", 15)
        self.font1 = QFont("Mv Boli", 25)
        self.label1 = QLabel("  created")
        self.label2 = QLabel("  deadline")
        self.label3 = QLabel("   priority")
        self.label4 = QLabel("  duration")
        self.label5 = QLabel(" again count")
        self.label6 = QLabel("completed date")
        self.label1.setFixedWidth(160)
        self.label2.setFixedWidth(160)
        self.label3.setFixedWidth(160)
        self.label4.setFixedWidth(160)
        self.label5.setFixedWidth(180)
        self.label6.setFixedWidth(230)
        #self.label2.setStyleSheet("background-color:white; margin: 0px;padding: 0px;")
        self.label_created = QLabel("created")
        self.label_deadline = QLabel("date")
        self.label_priority = QLabel("priority")
        self.label_duration = QLabel("duration")
        self.label_duration.setScaledContents(True)
        self.label_again_count = QLabel("again count")
        self.label_completed = QLabel("completed date")
        #self.label_deadline.setStyleSheet("background-color:red; margin: 0px;padding: 0px;")
        self.label1.setFont(self.font)
        self.label2.setFont(self.font)
        self.label3.setFont(self.font)
        self.label4.setFont(self.font)
        self.label5.setFont(self.font)
        self.label6.setFont(self.font)
        self.label_created.setFont(self.font1)
        self.label_deadline.setFont(self.font1)
        self.label_priority.setFont(self.font1)
        self.label_duration.setFont(self.font1)
        self.label_again_count.setFont(self.font1)
        self.label_completed.setFont(self.font1)

        # 画像上文字を載せるレイ
        overlay_layout = QVBoxLayout(self.overlay_img)
        overlay_layout.setContentsMargins(30, 40, 100, 60)
        self.lay11.addWidget(self.label1)
        self.lay11.addStretch()
        self.lay22.addWidget(self.label2)
        self.lay22.addStretch()
        self.lay33.addWidget(self.label3)
        self.lay33.addStretch()
        self.lay44.addWidget(self.label4)
        self.lay44.addStretch()
        self.lay55.addWidget(self.label5)
        self.lay55.addStretch()
        self.lay66.addWidget(self.label6)
        self.lay66.addStretch()
        self.lay11.addWidget(self.label_created)
        self.lay11.addStretch()
        self.lay22.addWidget(self.label_deadline)
        self.lay22.addStretch()
        self.lay33.addWidget(self.label_priority)
        self.lay33.addStretch()
        self.lay44.addWidget(self.label_duration)
        self.lay44.addStretch()
        self.lay55.addWidget(self.label_again_count)
        self.lay55.addStretch()
        self.lay66.addWidget(self.label_completed)
        self.lay66.addStretch()
        
        overlay_layout.addLayout(self.lay11)
        overlay_layout.addLayout(self.lay22)
        overlay_layout.addLayout(self.lay33)
        overlay_layout.addLayout(self.lay44)
        overlay_layout.addLayout(self.lay55)
        overlay_layout.addLayout(self.lay66)
        
        self.lay_right = QVBoxLayout()
        self.lay_right.setSpacing(0)
        self.lay_tttp = QHBoxLayout()
        self.i_label = QLabel("[")
        self.ii_label = QLabel("]")
        self.iii_label = QLabel("[")
        self.iiii_label = QLabel("]")
        self.ring_label = QLabel("notification")
        self.again_label = QLabel("again")
        self.at_label = QLabel("3 days to go!")
        self.ring_label.setFont(self.font1)
        self.again_label.setFont(self.font1)
        self.at_label.setFont(self.font1)
        self.i_label.setFont(self.font1)
        self.ii_label.setFont(self.font1)
        self.iii_label.setFont(self.font1)
        self.iiii_label.setFont(self.font1)
        self.lay_tttp.addStretch()
        self.lay_tttp.addWidget(self.i_label)
        self.lay_tttp.addWidget(self.ring_label)
        self.lay_tttp.addWidget(self.ii_label)
        self.lay_tttp.addStretch()
        self.lay_tttp.addWidget(self.iii_label)
        self.lay_tttp.addWidget(self.again_label)
        self.lay_tttp.addWidget(self.iiii_label)
        self.lay_tttp.addStretch()
        self.lay_tttp.addWidget(self.at_label)

        self.lay_progress = QHBoxLayout()
        self.progress_label = QLabel("0%")
        self.progress_label.setFont(self.font1)
        self.progress_label.setFixedWidth(150)
        self.progress_label.setFixedHeight(60)
        #self.progress_label.setStyleSheet("background-color: red;")
        self.progress_slider = SliderWithBar()
        #self.progress_slider.setStyleSheet("background-color: black;")
        self.progress_slider.setContentsMargins(0, 40, 0, 40)
        self.progress_slider.setFixedWidth(650)
        self.progress_slider.setFixedHeight(100)
        # スライダー値変更イベント
        self.progress_slider.slider.valueChanged.connect(self.update_progress)

        self.memo_edit = QTextEdit()
        self.memo_edit.setFixedSize(880, 480)
        self.memo_edit.setPlaceholderText("memo")# background-color: red;
        self.memo_edit.setStyleSheet("margin-top:5px; margin-left:40px; border: none; padding: 0px;line-height: 200%;")
        self.memo_edit.setContentsMargins(0, 0, 0, 0)
        self.memo_edit.setFont(QFont("Mv Boli", 25))

        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(20)
        self.button_layout.setAlignment(Qt.AlignCenter)
        self.copy_btn = HoverSoundButton("Copy", "assets\sounds\hover.wav")
        self.save_btn = HoverSoundButton("Save", "assets\sounds\hover.wav")
        self.copy_btn.setFont(QFont("Mv Boli", 20))
        self.save_btn.setFont(QFont("Mv Boli", 20))
        self.copy_btn.setStyleSheet("margin: 0px;")
        self.save_btn.setStyleSheet("margin: 0px;")
        self.copy_btn.setFixedSize(120, 80)
        self.save_btn.setFixedSize(120, 80)
        self.button_layout.addWidget(self.save_btn)
        self.button_layout.addWidget(self.copy_btn)
        self.copy_btn.clicked.connect(self.copy_item)
        self.save_btn.clicked.connect(self.save_all)
        
        #self.lay_progress.addStretch()
        self.lay_progress.addWidget(self.progress_slider)
        self.lay_progress.addWidget(self.progress_label)
        #self.lay_progress.addStretch()
        self.lay_right.addLayout(self.lay_tttp)
        self.lay_right.addLayout(self.lay_progress)
        self.lay_right.addWidget(self.memo_edit)
        self.lay_right.addLayout(self.button_layout)
        self.content_layout = QHBoxLayout()
        self.content_layout.addWidget(self.overlay_img)   # 左に画像
        self.content_layout.addLayout(self.lay_right)     # 右にバー
        # メインレイアウトに追加
        self.main_layout.addLayout(self.content_layout)

    def update_progress(self, value):
        self.progress_label.setText(f"{value}%")

    def copy_item(self):
        if self.item_data is None:
            return
        self.main_window.copied_item_id = self.item_data.get("id")

    def save_progress(self):
        if self.item_data is None:
           return
        progress_new = self.progress_slider.value()
        progress_old = self.item_data.get("progress", 0)
        progress_delta = progress_new - progress_old
        duration_str = self.item_data.get("duration", "")
        import re
        match = re.match(r"(\d+)h\s*(\d+)m", duration_str)
        if match:
            total_hours = int(match.group(1))
            total_minutes = int(match.group(2))
            total_h =  total_hours + (total_minutes / 60)
        else: 
            total_h = 1
        mochi = progress_delta * total_h
        today = datetime.now().date()
        today_str = today.strftime("%Y/%m/%d")
        today_entry = next((e for e in self.main_window.mochivation_data if e["date"] == today_str), None)
        if today_entry:
            mochivation_today = today_entry.get("mochivation", 0)
            daily_mochivation = mochivation_today + mochi
            today_entry["mochivation"] = daily_mochivation
        else:
            new_id = f"data{len(self.main_window.mochivation_data) + 1}"
            daily_mochivation = mochi
            self.main_window.mochivation_data.append({
            "id": new_id,
            "date": today_str,
            "mochivation": daily_mochivation
        })
        day_mochivation_max = self.main_window.info.get("day_mochivation_max", 0)
        if daily_mochivation > day_mochivation_max:
            self.main_window.info["day_mochivation_max"] = daily_mochivation

        self.item_data["progress"] = progress_new
        if progress_new == 100:
            again = self.item_data.get("again", 0)
            if again == 1:
                count_new = self.item_data.get("again_count", 0) + 1
                self.item_data["again_count"] = count_new
                self.item_data["progress"] = 0
                self.item_data["complete"] = 0
                count_max = self.main_window.info.get("again_max", 0)
                if count_new > count_max:
                    self.main_window.info["again_max"] = count_new
            elif again == 0:
                self.item_data["completed"] = 1
                now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
                self.item_data["completed date"] = now_str
        self.main_window.update_mochivation_summary()
        self.main_window.save_data()
        self.main_window.todo_screen.apply_sorting(
        self.main_window.current_sort_index,
        self.main_window.current_sort_order)

    def set_item(self, item_data):
        self.item_data = item_data# データを保持
        print("DataScreen に渡された item_data:", item_data) #デバッグ用
        # 各UI部品に値を反映
        self.title_renderer.set_text(item_data.get("todo", ""))
        self.label_created.setText(item_data.get("created", ""))
        self.label_deadline.setText(item_data.get("date", ""))
        self.label_duration.setText(item_data.get("duration", ""))
        #あと何日
        date_value = item_data.get("date", "")  # "2025/12/15 21:34"
        self.deadline = datetime.strptime(date_value, "%Y/%m/%d %H:%M")
        self.now = datetime.now()
        self.delta = self.deadline - self.now
        sec = self.delta.total_seconds()
        if sec > 0:
            if self.delta.days >= 1:
                self.at_label.setText(f"{self.delta.days} days to go")
            else:
                hours = int(sec // 3600)
                self.at_label.setText(f"{hours} hours to go")
        else:
            sec = abs(sec)
            if abs(self.delta.days) >= 1:
                self.at_label.setText(f"{abs(self.delta.days)} days passed")
            else:
                hours = int(sec // 3600)
                self.at_label.setText(f"{hours} hours passed")
        #onoff
        ring_value = item_data.get("ring", 0)
        if ring_value == 0:
            self.ring_label.setStyleSheet("color: rgba(0, 0, 0, 80);")
        else:
           self.ring_label.setStyleSheet("color: rgba(0, 0, 0, 255);")
        again_value = item_data.get("again", 0)
        if again_value == 0:
            self.again_label.setStyleSheet("color: rgba(0, 0, 0, 80);")
        else:
            self.again_label.setStyleSheet("color: rgba(0, 0, 0, 255);")
        #completed表示
        completed_value = item_data.get("completed", 0)
        if completed_value == 0:
            self.label_completed.setText("--")
        elif completed_value == 1:
            completed_data_value = item_data.get("completed date", "")
            self.label_completed.setText(completed_data_value)
        # duration表示
        duration_str = item_data.get("duration", "")
        import re
        match = re.match(r"(\d+)h\s*(\d+)m", duration_str)
        if match:
            total_hours = int(match.group(1))
            total_minutes = int(match.group(2))
            if total_minutes > 59:
                total_hours = total_hours + total_minutes // 60
                total_minutes = total_minutes - 60
        else:
            total_hours, total_minutes = 0, 0
        #12は基本1このみ
        self.days1 = total_hours // 24
        self.days12 = (total_hours % 24) // 12
        self.hours1 = ((total_hours % 24) % 12 ) // 2 #2時間一個  最大11/2こ
        self.hours12 = (((total_hours % 24) % 12 ) % 2 ) #1時間半個     最大１こ
        self.minutes1 = total_minutes // 10    #最大５こ
        self.minutes12 = (total_minutes % 10) // 5   #最大9/5
        for i in reversed(range(self.lay_444.count())):
            widget = self.lay_444.itemAt(i).widget()
            if widget and widget is not self.label_pr:  # label4は残す
                widget.deleteLater()
        #ラベル再追加
        #self.lay44.addWidget(self.label4, alignment=Qt.AlignLeft)
        self.container = QWidget()
        self.container.setFixedWidth(308)  # 幅を固定
        self.h_layout = QHBoxLayout(self.container)
        self.h_layout.setAlignment(Qt.AlignCenter)
        self.h_layout.setSpacing(0)
        #画像追加
        for _ in range(self.days1):
            lbl = QLabel()
            lbl.setPixmap(QPixmap("assets/images/時計d1.png"))
            lbl.setScaledContents(True)
            lbl.setFixedSize(80, 80)
            self.h_layout.addWidget(lbl)
        for _ in range(self.days12):
            lbl = QLabel()
            lbl.setPixmap(QPixmap("assets/images/時計d12.png"))
            lbl.setScaledContents(True)
            lbl.setFixedSize(80, 80)
            self.h_layout.addWidget(lbl)
        for _ in range(self.hours1):
            lbl = QLabel()
            lbl.setPixmap(QPixmap("assets/images/時計h1.png"))
            lbl.setScaledContents(True)
            lbl.setFixedSize(66, 80)
            self.h_layout.addWidget(lbl)
        for _ in range(self.hours12):
            lbl = QLabel()
            lbl.setPixmap(QPixmap("assets/images/時計h12.png"))
            lbl.setScaledContents(True)
            lbl.setFixedSize(66, 80)
            self.h_layout.addWidget(lbl)
        for _ in range(self.minutes1):
            lbl = QLabel()
            lbl.setPixmap(QPixmap("assets/images/時計m1.png"))
            lbl.setScaledContents(True)
            lbl.setFixedSize(46, 80)
            self.h_layout.addWidget(lbl)
        for _ in range(self.minutes12):
            lbl = QLabel()
            lbl.setPixmap(QPixmap("assets/images/時計m12.png"))
            lbl.setScaledContents(True)
            lbl.setFixedSize(46, 80)
            self.h_layout.addWidget(lbl)
        self.lay_444.addWidget(self.container)
        #again表示
        again_value = item_data.get("again", 0)
        if again_value == 0:
            self.label_again_count.setText(" --")
        elif again_value == 1:
            count_value = item_data.get("again_count", 0)
            self.label_again_count.setText(str(count_value))
        #重要度表示
        prio = item_data.get("priority", -1)  # デフォルトは -1
        if prio == 0:
            self.label_pr.setPixmap(QPixmap("assets/images/星1.png"))
            self.label_priority.setText("Low priority")
        elif prio == 1:
            self.label_pr.setPixmap(QPixmap("assets/images/星2.png"))
            self.label_priority.setText("Medium priority")
        elif prio == 2:
            self.label_pr.setPixmap(QPixmap("assets/images/星3.png"))
            self.label_priority.setText("High priority")
        else:
            self.label_pr.setPixmap(QPixmap("assets/images/星1.png"))
            self.label_priority.setText("Low priority")
        #Type表示
        genre = item_data.get("type_index", -1)  # デフォルトは -1
        if genre == 0:
            self.bg = QPixmap("assets/images/memo_siro.png") #free
        elif genre == 1:
            self.bg = QPixmap("assets/images/memo_ao.png")   #study
        elif genre == 2:
            self.bg = QPixmap("assets/images/memo_aka.png")  #???
        else:
            self.bg = QPixmap("assets/images/memo_siro.png") #デフォ
        self.update()#再描画要求
        self.load_memo()

    def save_memo(self):
        memo_text = self.memo_edit.toPlainText()
        item_id = self.item_data.get("id")
        try:
            with open("data/memo_data.json", "r", encoding="utf-8") as f:
                content = f.read().strip()
                memo_list = json.loads(content) if content else []
        except:
            memo_list = []
        existing = next((m for m in memo_list if m["id"] == item_id), None)
        if existing:
            existing["memo"] = memo_text
        else:
            memo_list.append({
                "id": item_id,
                "memo": memo_text
            })
        with open("data/memo_data.json", "w", encoding="utf-8") as f:
            json.dump(memo_list, f, ensure_ascii=False, indent=2)

    def load_memo(self):
        item_id = self.item_data.get("id")
        try:
            with open("data/memo_data.json", "r", encoding="utf-8") as f:
                content = f.read().strip()
                memo_list = json.loads(content) if content else []
        except:
             memo_list = []
        entry = next((m for m in memo_list if m["id"] == item_id), None)
        self.memo_edit.setText(entry["memo"] if entry else "")

    def showEvent(self, event):
        super().showEvent(event)
        self.reset_data_screen()
        self.setFocus()

    def reset_data_screen(self):
        progress_value = self.item_data.get("progress", 0)  # データから進捗を取得、なければ0
        self.progress_slider.setValue(progress_value)
        self.progress_label.setText(f"{progress_value}%")

    def save_all(self):
        self.save_progress()
        self.save_memo()

    def paintEvent(self, event):
        painter = QPainter(self)
        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

class GenreInputDialog(QWidget):
    def __init__(self, parent=None, main_window=None, switcher=None, index_to_update=0):
        super().__init__(parent)
        self.main_window = main_window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.setFixedSize(1920, 1080)
        self.bg = QPixmap("assets/images/usukuro.png")
        self.switcher = switcher
        self.index = index_to_update
        self.save_count = 0

        self.layout = QVBoxLayout()
        self.label = QLabel("You can freely choose one 'type';"
        "<br> If a type has already been set, it will be overwritten;"
        "<br> When you press 'Add', the entered type will be added"
        "<br>   and you'll return to the previous screen;")
        self.input = QLineEdit()
        self.ok_btn = QPushButton("Add")
        font = QFont("Mv Boli", 25)
        font1 = QFont("Mv Boli", 15)
        self.input.setFont(font)
        self.label.setFont(font1)
        self.ok_btn.setFont(font)
        self.input.setFixedWidth(600)  # ← 幅600pxに固定
        self.input.setFixedHeight(60)  # ← 高さ60pxに固定
        self.input.setPlaceholderText("Add a new type name")
        self.input.setStyleSheet("border: none; color: white;")
        self.ok_btn.setStyleSheet("color: white; margin:100px; ")
        self.label.setStyleSheet("color: white; margin:100px;")
        self.ok_btn.clicked.connect(self.apply_genre)

        self.layout.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.input)
        self.layout.addWidget(self.ok_btn)
        self.setLayout(self.layout)

        if parent:
            self.setGeometry(parent.geometry())

    def apply_genre(self):
        new_genre = self.input.text().strip()
        if new_genre:
            self.switcher.update_item_at(self.index, new_genre)
            self.main_window.update_custom_type_name(new_genre)
            self.hide()  # ← 入力後に非表示にする

    def paintEvent(self, event):    
        painter = QPainter(self)
        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

class ArrowSwitcher(QWidget):
    def __init__(self, items):
        super().__init__()
        #self.setFixedSize(90, 150)
        # 表示する内容リスト
        self.items = items
        self.index = 0

        # 中央ラベル
        self.label = QLabel(self.items[self.index])
        self.label.setFixedWidth(310)  # ← 幅を300pxに固定
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont("Mv Boli", 20))

        # 左右ボタン（画像付き）
        self.left_btn = QPushButton()
        self.left_btn = HoverIconSoundButton("assets/images/左B.png", "assets/images/左Bh.png", "assets\sounds\hover.wav")
        self.left_btn.setIconSize(QPixmap("assets/images/左B.png").size())
        self.left_btn.setFlat(True)

        self.right_btn = QPushButton()
        self.right_btn = HoverIconSoundButton("assets/images/右B.png", "assets/images/右Bh.png", "assets\sounds\hover.wav")
        self.right_btn.setIconSize(QPixmap("assets/images/右B.png").size())
        self.right_btn.setFlat(True)

        # レイアウト
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignLeft)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.left_btn)
        layout.addWidget(self.label)
        layout.addWidget(self.right_btn)
        self.setLayout(layout)

        # ボタンの動作（ラベル切り替え）
        self.left_btn.clicked.connect(self.show_prev)
        self.right_btn.clicked.connect(self.show_next)

    def show_prev(self):
        self.index = (self.index - 1) % len(self.items)
        self.label.setText(self.items[self.index])

    def show_next(self):
        self.index = (self.index + 1) % len(self.items)
        self.label.setText(self.items[self.index])

    def update_items(self, new_items):
        self.items = new_items
        self.index = 0
        self.label.setText(self.items[self.index])

    def update_item_at(self, index, new_text):
        if 0 <= index < len(self.items):
            self.items[index] = new_text
            self.label.setText(self.items[self.index])  # 表示中のインデックスなら更新

    def set_index(self, index):# 範囲チェック
        if 0 <= index < len(self.items):
            self.index = index
            self.label.setText(self.items[self.index])

class WarningDialog(QWidget):
    def __init__(self, main_window=None, error=None):
        super().__init__(main_window)
        self.main_window = main_window
        self.error = error
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.setFixedSize(1920, 1080)
        self.bg = QPixmap("assets/images/usukuro.png")
        self.step = 0

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignCenter)
        self.font = QFont("Mv Boli", 25)
        self.font1 = QFont("Mv Boli", 15)
        self.talk = TalkAnimation("log1.xml", "assets/images/log1.png", "error", parent=self)
        self.talk.setGeometry(0, -100, 1920, 1080)
        self.talk.show()
        
        self.setLayout(self.layout)
        if main_window:
            self.setGeometry(main_window.geometry())

    def next_step(self):
        print(self.error)
        self.step += 1
        if self.step == 1: 
            error = self.error 
            if error == "empty_field":
                msg = "Some fields are still empty!" 
            elif error == "deadline_past": 
                msg = "The deadline is before today!" 
            elif error == "invalid_date": 
                msg = "That date doesn't exist!" 
            else: 
                msg = "これだと保存できないよ！" 

            self.show_talk("data/log1.xml", "assets/images/log1.png", msg, loops=5)
            return
        self.close()# エラー無い
       
    def show_talk(self, xml, png, text, loops):
        if hasattr(self, "talk"): # 既存talk消す
            self.talk.hide()

        self.talk = TalkAnimation(xml, png, text, parent=self)
        self.talk.setGeometry(0, -100, 1920, 380)
        self.talk.show()
        self.talk.play(loops, 40, 30)

    def reset_dialog(self):
        self.step = 0
        self.talk.full_text = "error"
        self.talk.current_index = 0 
        self.talk.text_label.setText("") 
        self.talk.is_text_animating = False
        self.talk.show() 
        self.talk.play(3, 40, 30)
    
    def showEvent(self, event):
        super().showEvent(event)# ウィンドウが表示された後にアニメ開始
        self.reset_dialog()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()
        
    def paintEvent(self, event):    
        painter = QPainter(self)
        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            if not hasattr(self, "talk"):
                return

            if self.talk.is_text_animating:
                self.talk.text_timer.stop()
                self.talk.text_label.setText(self.talk.full_text)
                self.talk.is_text_animating = False
                return
            self.next_step()

class EditScreen(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.main_window = main_window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.bg = QPixmap("assets/images/background0-1.png")  # ← 背景画像を読み込む
        self.toggle_states = {}  # ボタンごとの状態を記録
        self.now = QDateTime.currentDateTime()
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(40, 20, 40, 20)
        self.main_layout.setSpacing(30)
        self.todo_data_store = {}  # ← すべてのToDoをここに保存
        #上
        self.top_layout = QHBoxLayout()
        self.top_layout.setSpacing(0)
        self.top_layout.setAlignment(Qt.AlignCenter)

        self.label1 = QLabel("ToDo")
        self.label1.setStyleSheet("""
        QLabel {background-image: url(assets/images/kamim.png);
        background-repeat: no-repeat;
        background-position: center;
        color: black;
        font-size: 80px;
        margin: 0px;
        padding: 10px;
        padding-left: 60px;
        font-family: "Mv Boli";
        }""")
        self.label1.setFixedSize(347, 184)
        self.input1 = QLineEdit()
        self.input1.setStyleSheet("""QLineEdit {
        border: none;
        background-repeat: no-repeat;
        background-position: center;
        background-color: transparent;}""")
        font = QFont("Mv Boli", 25)
        self.input1.setFont(font)
        self.input1.setPlaceholderText("Click here!")
        self.input1.setFixedWidth(700)
        self.input1.setFixedHeight(60)
        self.top_layout.addWidget(self.label1)
        self.top_layout.addWidget(self.input1)
        self.main_layout.addLayout(self.top_layout)

        # ②以下6項目（2列×3行）
        self.row1_layout = QHBoxLayout()
        self.row1_layout.setAlignment(Qt.AlignLeft)
        self.label2 = QLabel("value")
        self.input2 = QLineEdit()
        self.label3 = QLabel("ETA")#所要時間
        self.input3 = QLineEdit()
        self.switcher1 = ArrowSwitcher(["Low priority", "Medium priority", "High priority"])
        # self.btn_add_genre = HoverIconButton("assets/images/プラス.png", "assets/images/プラスh.png")
        # self.btn_add_genre.setIconSize(QSize(80, 80))
        # self.btn_add_genre.setStyleSheet("background: transparent; border: none; margin: 0px;")
        # self.btn_add_genre = QPushButton("ジャンル追加")
        self.label2.setStyleSheet("""
        QLabel {background-image: url(assets/images/kamim.png);background-repeat: no-repeat;
        background-position: center;color: black;font-family: "Mv Boli";
        font-size: 80px;margin: 0px;
        padding: 10px;padding-left: 60px;}""")
        self.label3.setStyleSheet("""
        QLabel {background-image: url(assets/images/kamim.png);background-repeat: no-repeat;
        background-position: center;color: black;font-family: "Mv Boli";
        font-size: 80px;margin: 0px;
        padding: 10px;padding-left: 60px;}""")
        self.label2.setFixedSize(347, 184) 
        self.label3.setFixedSize(347, 184)
        self.switcher1.setStyleSheet("margin: 0px;")#padding: 0px;書いたら消えたしね
        # 時間・分入力欄のレイアウト
        self.time_layout = QHBoxLayout()
        self.hour_input11 = QLineEdit()
        self.hour_input11.setFixedWidth(100)
        self.hour_input11.setPlaceholderText("hour")
        self.hour_input11.setFont(QFont("Mv Boli", 20))
        self.hour_input11.setStyleSheet("border: none; margin: 0px;")
        self.hour_label = QLabel("h")
        self.hour_label.setStyleSheet("margin: 0px;")
        self.hour_label.setFont(QFont("Mv Boli", 30))
        self.minute_input11 = QLineEdit()
        self.minute_input11.setFixedWidth(100)
        self.minute_input11.setPlaceholderText("min.")
        self.minute_input11.setFont(QFont("Mv Boli", 20))
        self.minute_input11.setStyleSheet("border: none; margin: 0px;")
        self.hour_input11.setMaxLength(2)
        self.minute_input11.setMaxLength(2)
        self.minute_label = QLabel("m")
        self.minute_label.setStyleSheet("margin: 0px;")
        self.minute_label.setFont(QFont("Mv Boli", 30))
        self.hour_input11.setValidator(QIntValidator(0, 999))
        self.minute_input11.setValidator(QIntValidator(0, 999))
        self.time_layout.addWidget(self.hour_input11)
        self.time_layout.addWidget(self.hour_label)
        self.time_layout.addSpacing(20)
        self.time_layout.addWidget(self.minute_input11)
        self.time_layout.addWidget(self.minute_label)

        self.row1_layout.addWidget(self.label2, alignment=Qt.AlignLeft)
        # self.row1_layout.addWidget(self.btn_add_genre, alignment=Qt.AlignLeft)
        self.row1_layout.addWidget(self.switcher1, alignment=Qt.AlignLeft)
        self.row1_layout.addSpacing(40)
        self.row1_layout.addWidget(self.label3)
        #self.row1_layout.addWidget(self.input3)
        self.row1_layout.addLayout(self.time_layout)
        self.main_layout.addLayout(self.row1_layout)

        self.row2_layout = QHBoxLayout()
        self.row2_layout.setAlignment(Qt.AlignLeft)
        self.label4 = QLabel("Done")
        self.input4 = QLineEdit()
        self.label5 = QLabel("Due")#締切日
        self.input5 = QLineEdit()
        self.switcher3 = ArrowSwitcher(["0%", "10%", "20%","30%","40%","50%","60%","70%","80%","90%"])
        self.label4.setStyleSheet("""
        QLabel {background-image: url(assets/images/kamim.png);background-repeat: no-repeat;
        background-position: center;color: black;font-family: "Mv Boli";
        font-size: 80px;margin: 0px;
        padding: 10px;padding-left: 60px;}""")
        self.label5.setStyleSheet("""
        QLabel {background-image: url(assets/images/kamim.png);background-repeat: no-repeat;
        background-position: center;color: black;font-family: "Mv Boli";
        font-size: 80px;margin: 0px;
        padding: 10px;padding-left: 60px;}""")
        self.label4.setFixedSize(347, 184) 
        self.label5.setFixedSize(347, 184)
        self.switcher3.setStyleSheet("margin: 0px;")#padding: 0px;書いたら消えたしね
        # 日付入力欄のレイアウト
        self.date_layout = QHBoxLayout()
        self.year_input = QLineEdit()
        self.year_input.setFixedWidth(140)
        self.year_input.setPlaceholderText("yyyy")
        self.year_input.setStyleSheet("border: none; margin: 0px; padding: 0px;")
        self.year_input.setFont(QFont("Mv Boli", 25))
        self.year_input.setValidator(QIntValidator(1, 9999))
        self.year_label = QLabel("/")
        self.year_label.setStyleSheet("border: none; margin: 0px; padding: 0px;")
        self.year_label.setFont(QFont("Mv Boli", 25))
        # 月入力欄
        self.month_input = QLineEdit()
        self.month_input.setFixedWidth(70)
        self.month_input.setPlaceholderText("mm")
        self.month_input.setStyleSheet("border: none; margin: 0px;padding: 0px;")
        self.month_input.setFont(QFont("Mv Boli", 25))
        self.month_input.setValidator(QIntValidator(1, 12))
        self.month_label = QLabel("/")
        self.month_label.setStyleSheet("border: none; margin: 0px;padding: 0px;")
        self.month_label.setFont(QFont("Mv Boli", 25))
        # 日入力欄
        self.day_input = QLineEdit()
        self.day_input.setFixedWidth(153)
        self.day_input.setPlaceholderText("dd")
        self.day_input.setStyleSheet("border: none; margin: 0px;padding: 0px;")
        self.day_input.setFont(QFont("Mv Boli", 25))
        self.day_input.setValidator(QIntValidator(1, 31))
        # self.day_label = QLabel("()")
        # self.day_label.setFont(QFont("Mv Boli", 20))
        # 時間入力欄
        self.hour_input = QLineEdit()
        self.hour_input.setFixedWidth(173)
        self.hour_input.setPlaceholderText("hh")
        self.hour_input.setStyleSheet("border: none; margin: 0px; padding: 0px 60px 0px 0px;")
       
        self.hour_input.setFont(QFont("Mv Boli", 25))
        self.hour_input.setValidator(QIntValidator(0, 23))
        self.hour_label = QLabel(":")
        self.hour_label.setStyleSheet("border: none; margin: 0px;padding: 0px;")
        self.hour_label.setFont(QFont("Mv Boli", 25))
        self.hour_input.setAlignment(Qt.AlignRight)
        # 分入力欄
        self.minute_input = QLineEdit()
        self.minute_input.setContentsMargins(0, 0, 0, 0)
        self.minute_input.setFixedWidth(213)
        self.minute_input.setPlaceholderText("mm")
        self.minute_input.setStyleSheet("border: none; padding: 0px;")
        self.minute_input.setContentsMargins(0, 0, 60, 0)
        self.minute_input.setFont(QFont("Mv Boli", 25))
        self.minute_input.setValidator(QIntValidator(0, 59))

        self.year_input.setText(str(self.now.date().year()))
        self.month_input.setText(str(self.now.date().month()))
        self.day_input.setText(str(self.now.date().day()))
        self.hour_input.setText(str(self.now.time().hour()))
        self.minute_input.setText(str(self.now.time().minute()))
        # レイアウトに追加
        # 日付行
        self.date_row = QHBoxLayout()
        self.date_row.setAlignment(Qt.AlignLeft)
        self.date_row.setSpacing(0)
        self.date_row.addWidget(self.year_input)
        self.date_row.addWidget(self.year_label)
        self.date_row.addWidget(self.month_input)
        self.date_row.addWidget(self.month_label)
        self.date_row.addWidget(self.day_input)
        # 時間行
        self.time_row = QHBoxLayout()
        self.time_row.setAlignment(Qt.AlignCenter)
        self.time_row.setSpacing(0)
        self.time_row.addWidget(self.hour_input)
        self.time_row.addWidget(self.hour_label)
        self.time_row.addWidget(self.minute_input)

        self.date_time_layout = QVBoxLayout()
        self.date_time_layout.setSpacing(0)
        self.date_time_layout.setContentsMargins(0, 0, 50, 0)  # 左に50pxの余白
        self.date_time_layout.setAlignment(Qt.AlignCenter)
        self.date_time_layout.addLayout(self.date_row)
        self.date_time_layout.addLayout(self.time_row)

        self.due_block_layout = QHBoxLayout()
        self.due_block_layout.setAlignment(Qt.AlignLeft)
        self.due_block_layout.addWidget(self.label5)
        self.due_block_layout.addLayout(self.date_time_layout)

        self.row2_layout.addWidget(self.label4, alignment=Qt.AlignLeft)
        self.row2_layout.addWidget(self.switcher3, alignment=Qt.AlignLeft)
        #self.row2_layout.addWidget(self.input4)
        self.row2_layout.addSpacing(40)
        #self.row2_layout.addWidget(self.label5)
        #self.row2_layout.addWidget(self.input5)
        self.row2_layout.addLayout(self.due_block_layout)
        self.main_layout.addLayout(self.row2_layout)

        self.row3_layout = QHBoxLayout()
        self.row3_layout.setAlignment(Qt.AlignLeft)
        self.label6 = QLabel("Type")
        #self.input6 = QLineEdit()
        self.label7 = QLabel("Again")
        #self.input7 = QLineEdit()
        #self.switcher2 = ArrowSwitcher(["Low priority", "Medium priority", "High priority"])
        self.switcher2 = ArrowSwitcher(["pastime(free)", "study", "???"])
        self.btn_add_genre = HoverIconSoundButton("assets/images/プラス.png", "assets/images/プラスh.png", "assets\sounds\hover.wav")
        self.btn_add_genre.setIconSize(QSize(80, 80))
        self.btn_add_genre.setStyleSheet("background: transparent; border: none; margin: 0px;")
        self.label6.setStyleSheet("""
        QLabel {background-image: url(assets/images/kamim.png);background-repeat: no-repeat;
        background-position: center;color: black;font-family: "Mv Boli";
        font-size: 80px;margin: 0px;
        padding: 10px;padding-left: 60px;}""")
        self.label7.setStyleSheet("""
        QLabel {background-image: url(assets/images/kamim.png);background-repeat: no-repeat;
        background-position: center;color: black;font-family: "Mv Boli";
        font-size: 80px;margin: 0px;
        padding: 10px;padding-left: 60px;}""")
        self.again_btn = QPushButton()
        self.toggle_states[self.again_btn] = False
        self.again_btn.setFixedSize(80, 80)
        self.again_btn.setIcon(QIcon("assets/images/しかくB.png"))
        self.again_btn.setIconSize(QSize(80, 80))
        self.ring_btn = QPushButton()
        self.toggle_states[self.ring_btn] = False
        self.ring_btn.setFixedSize(80, 80)
        self.ring_btn.setIcon(QIcon("assets/images/通知c.png"))
        self.ring_btn.setIconSize(QSize(80, 80))
        self.label6.setFixedSize(347, 184) 
        self.label7.setFixedSize(347, 184)
        self.switcher1.setStyleSheet("margin: 0px;")#padding: 0px;書いたら消えたしね
        self.row3_layout.addWidget(self.label6, alignment=Qt.AlignLeft)
        self.row3_layout.addWidget(self.switcher2, alignment=Qt.AlignLeft)
        self.row3_layout.addWidget(self.btn_add_genre, alignment=Qt.AlignLeft)
        #self.row1_layout.addWidget(self.input6)
        self.row3_layout.addSpacing(40)
        self.row3_layout.addWidget(self.label7)
        self.row3_layout.addWidget(self.again_btn)
        self.row3_layout.addWidget(self.ring_btn)
        self.main_layout.addLayout(self.row3_layout)

        self.again_btn.clicked.connect(lambda: self.toggle_icon(self.again_btn, "assets/images/しかくBc.png", "assets/images/しかくB.png"))
        self.ring_btn.clicked.connect(lambda: self.toggle_icon(self.ring_btn, "assets/images/通知.png", "assets/images/通知c.png"))
        self.btn_add_genre.clicked.connect(lambda checked=False: self.open_genre_input())
        self.genre_dialog = GenreInputDialog(parent=self, main_window=self.main_window, switcher=self.switcher2, index_to_update=2)
        self.genre_dialog.hide()

        # ④ 最下部のボタン行
        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(20)
        self.button_layout.setAlignment(Qt.AlignCenter)

        self.back_btn = HoverSoundButton("Back", "assets\sounds\hover.wav")
        self.save_btn = HoverSoundButton("Save", "assets\sounds\hover.wav")
        self.paste_btn = HoverSoundButton("Paste", "assets\sounds\hover.wav")
        self.saved_btn = HoverSoundButton("Saved", "assets\sounds\hover.wav")
        self.saved_btn.hide()
        self.back_btn.setFont(QFont("Mv Boli", 20))
        self.save_btn.setFont(QFont("Mv Boli", 20))
        self.paste_btn.setFont(QFont("Mv Boli", 20))
        self.saved_btn.setFont(QFont("Mv Boli", 20))
        self.back_btn.setStyleSheet("margin: 0px;")
        self.save_btn.setStyleSheet("margin: 0px;")
        self.paste_btn.setStyleSheet("margin: 0px;")
        self.saved_btn.setStyleSheet("color: #333333; margin: 0px;")
        self.back_btn.setFixedSize(120, 80)
        self.save_btn.setFixedSize(120, 80)
        self.paste_btn.setFixedSize(120, 80)
        self.saved_btn.setFixedSize(120, 80)
        self.button_layout.addWidget(self.save_btn)
        self.button_layout.addWidget(self.saved_btn)
        self.button_layout.addWidget(self.paste_btn)
        self.button_layout.addWidget(self.back_btn)
        self.main_layout.addLayout(self.button_layout)
        self.back_btn.clicked.connect(lambda: self.main_window.flash_widget_color(self.back_btn, lambda: self.main_window.fade_to(self.main_window.todo_screen)))
        #self.save_btn.clicked.connect(self.save_data)
        self.paste_btn.clicked.connect(self.paste_from_copy)
        self.saved_btn.clicked.connect(lambda: self.play_sound("assets\sounds\bb.wav"))
        self.save_btn.setEnabled(True)
        self.save_btn.clicked.connect(lambda checked=False: self.open_warning_edit())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(800, 600)

        self.frames = load_frames_from_xml("data/try.xml")
        self.animator = SpriteAnimator("assets/images/try.png", self.frames, parent=self)
        self.animator.setGeometry(1920-880+150, 1080-880+200, 880, 880)
        self.save_sound = QSoundEffect()
        self.save_sound.setSource(QUrl.fromLocalFile("assets\sounds\chara.wav"))#いいのがない
        self.save_sound.setVolume(0.8)

        self.setLayout(self.main_layout)
        self.resize(600, 400)

    def save_data(self):
        if self.save_count >= 1:
            print("すでに保存されています")
            return
    # 入力内容を取得
        self.main_window.save_count = self.main_window.save_count + 1
        self.todo_text = self.input1.text().strip()
        self.year = int(self.year_input.text().strip())
        self.month = int(self.month_input.text().strip())
        self.day = int(self.day_input.text().strip())
        self.hour = int(self.hour_input.text().strip())
        self.minute = int(self.minute_input.text().strip())

        self.hour11 = self.hour_input11.text().strip()
        self.minute11 = self.minute_input11.text().strip()
        self.priority_index = self.switcher1.index
        self.type_index = self.switcher2.index
        self.progress = int(self.switcher3.label.text().strip().replace("%", ""))
        self.checked = self.toggle_states.get(self.again_btn, False)
        self.ringchecked = self.toggle_states.get(self.ring_btn, False)
        data_id = f"data{self.main_window.save_count}"
        self.now = datetime.now()
        self.again_count = 0
    # 保存データまとめ
        self.data = {
            "id": data_id,
            "todo": self.todo_text,
            "date": f"{self.year}/{self.month:02d}/{self.day:02d} {self.hour:02d}:{self.minute:02d}",
            "duration": f"{self.hour11}h {self.minute11}m",
            "priority": self.priority_index,
            "type_index": self.type_index,
            "progress": self.progress,
            "again": 1 if self.checked else 0,
            "created": self.now.strftime("%Y/%m/%d %H:%M"),  # ← 日付＋時間
            "completed": 0, #未達成:0、達成:1
            "completed date": "",
            "again_count": self.again_count,
            "ring": 1 if self.ringchecked else 0,
            "google_saved": False, #未送信フラグ
            "deleted": False
            }
        
        print(f"{data_id} に保存されました:", self.data)
        self.save_btn.hide()
        self.saved_btn.show()
        # TODO: ファイル保存やデータベース登録などに応用
        self.main_window.info["save_count"] = self.main_window.save_count
        self.main_window.todo_data_store.append(self.data)#todo_data_store全ToDoの一覧
        self.main_window.todo_screen.todo_data_store = self.main_window.todo_data_store
        self.main_window.todo_screen.apply_sorting(
        self.main_window.current_sort_index,
        self.main_window.current_sort_order)
        send_push_notification(FCM_TOKEN, "新しいToDoリスト", self.todo_text)
        
        #self.save_sound.play()
        self.animator.frame_index = 0
        self.animator.show()
        self.animator.raise_()
        self.animator.start_animation(40, 1)#interval, loops
        #Google Tasks APIに保存
        try:
            if self.ringchecked:  # ← 通知ONのとき保存
                #deadline_iso = f"{self.year}-{self.month.zfill(2)}-{self.day.zfill(2)}T{self.hour.zfill(2)}:{self.minute.zfill(2)}:00.000Z"
                deadline_iso = (
            f"{self.year:04d}-"
            f"{self.month:02d}-"
            f"{self.day:02d}T"
            f"{self.hour:02d}:{self.minute:02d}:00.000Z"
        )
                self.save_todo_to_google(
                title=self.todo_text,
                deadline=deadline_iso,
                creds=self.main_window.login_window.creds,
                completed=False)
            else:
                print("通知OFFなのでGoogle保存はスキップしました")
        except Exception as e:
           print("Google保存失敗:", e)

        self.main_window.save_data()
    
    def open_warning_edit(self):
        self.error = None
        self.required_fields = [
        self.input1.text().strip(),
        self.year_input.text().strip(),
        self.month_input.text().strip(),
        self.day_input.text().strip(),
        self.hour_input.text().strip(),
        self.minute_input.text().strip(),
        self.hour_input11.text().strip(),
        self.minute_input11.text().strip(),
        ]
        if not all(self.required_fields): # どれか1つでも空ならエラー
            self.show_warning("empty_field")
            return#ないのにこのまま続くとまずい
    
        year = int(self.year_input.text()) 
        month = int(self.month_input.text()) 
        day = int(self.day_input.text()) # 月の範囲チェック 
        invalid = False
        if not (1 <= month <= 12):
            invalid = True
        if not (1 <= day <= 31):
            invalid = True
        try:
            datetime(year, month, day)
        except ValueError:
            invalid = True
        try:# 過去日チェック
            entered = datetime(
                int(self.year_input.text()), int(self.month_input.text()), int(self.day_input.text()), 
                int(self.hour_input.text()), int(self.minute_input.text())
            )
            if entered < datetime.now():
                self.show_warning("deadline_past")
                return
        except:
            invalid = True

        if invalid:
            self.show_warning("invalid_date")
            return
        self.save_data() # 問題なし → 保存

    def show_warning(self, error):
        dialog = WarningDialog(self, error)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def paste_from_copy(self):
        copy_id = self.main_window.copied_item_id
        if not copy_id:
            print("コピーされたデータがありません")
            return
        try:
            with open("data/todo_data.json", "r", encoding="utf-8") as f:
                data_list = json.load(f)
        except Exception as e:
            print("JSON 読み込み失敗:", e)
            return
        base = next((item for item in data_list if item.get("id") == copy_id), None)

        if base is None:
            print("コピー元データが見つかりません")
            return
    # ToDo 名
        self.input1.setText(base.get("todo", ""))
    # 優先度
        self.switcher1.set_index(base.get("priority", 0))
    # ETA（duration）
        duration = base.get("duration", "0h 0m")
        import re
        m = re.match(r"(\d+)h\s*(\d+)m", duration)
        if m:
            self.hour_input11.setText(m.group(1))
            self.minute_input11.setText(m.group(2))
    # 期限（date）
        date_str = base.get("date", "")
        m = re.match(r"(\d+)/(\d+)/(\d+)\s+(\d+):(\d+)", date_str)
        if m:
            self.year_input.setText(m.group(1))
            self.month_input.setText(m.group(2))
            self.day_input.setText(m.group(3))
            self.hour_input.setText(m.group(4))
            self.minute_input.setText(m.group(5))
    # Type
        self.switcher2.set_index(base.get("type_index", 0))
    # Again
        again_flag = base.get("again", 0)
        self.toggle_states[self.again_btn] = bool(again_flag)
        self.again_btn.setIcon(QIcon("assets/images/しかくBc.png" if again_flag else "assets/images/しかくB.png"))
    # Ring
        ring_flag = base.get("ring", 0)
        self.toggle_states[self.ring_btn] = bool(ring_flag)
        self.ring_btn.setIcon(QIcon("assets/images/通知.png" if ring_flag else "assets/images/通知c.png"))
    # Progress（0〜90%）
        progress = base.get("progress", 0)
        self.switcher3.set_index(progress // 10)

    def save_todo_to_google(self,title, deadline, creds, completed=False):
        if creds.expired and creds.refresh_token: 
            creds.refresh(Request())
        service = build("tasks", "v1", credentials=creds)
        task = {
            "title": title,
            "due": deadline,
            "status": "completed" if completed else "needsAction"
        }
        result = service.tasks().insert(tasklist="@default", body=task).execute()
        print("Googleに保存:", result)

    # def save_local_data(self):
    #     try:
    #         with open("data/todo_data.json", "w", encoding="utf-8") as f:
    #             json.dump(self.main_window.todo_data_store, f, ensure_ascii=False, indent=2)
    #         print("ローカル保存成功: data/todo_data.json")
    #     except Exception as e:
    #         print("ローカル保存失敗:", e)

    def open_genre_input(self):
        self.genre_dialog.show()
        self.genre_dialog.raise_()
        self.genre_dialog.activateWindow()

    def toggle_icon(self, button, on_icon, off_icon):
        self.toggle_states[button] = not self.toggle_states[button]
        if self.toggle_states[button]:
            button.setIcon(QIcon(on_icon))
        else:
            button.setIcon(QIcon(off_icon))

    def play_sound(self, sound_file):
        self.sound = QSound(sound_file)
        self.sound.play()

    def showEvent(self, event):
        super().showEvent(event)
        self.reset_edit_screen()
        self.setFocus()

    def reset_edit_screen(self):
        self.now = QDateTime.currentDateTime()
        self.save_btn.show()
        self.saved_btn.hide()
        self.input1.clear()
        self.hour_input.clear()
        self.minute_input.clear()
        self.year_input.setText(str(self.now.date().year()))
        self.month_input.setText(str(self.now.date().month()))
        self.day_input.setText(str(self.now.date().day()))
        self.hour_input.setText(str(self.now.time().hour()))
        self.minute_input.setText(str(self.now.time().minute()))
    # ArrowSwitcher を初期化（index 0 に戻す）
        self.switcher1.index = 0
        self.switcher1.label.setText(self.switcher1.items[0])
        self.switcher3.index = 0
        self.switcher3.label.setText(self.switcher3.items[0])
    # switcher2（Type）そのまま
    # チェックマークを外す
        self.toggle_states[self.again_btn] = False
        self.again_btn.setIcon(QIcon("assets/images/しかくB.png"))
        self.save_count = 0

        self.animator.timer.stop()
        self.animator.hide()
        self.animator.frame_index = 0

    def paintEvent(self, event):
        painter = QPainter(self)
        scaled = self.bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        super().paintEvent(event)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("スプライトToDoリスト")
        self.resize(800, 600)
        self.transition_sound = QSoundEffect()
        self.transition_sound.setSource(QUrl.fromLocalFile("assets\sounds\enter.wav"))
        self.transition_sound.setVolume(0.8)
        self.login_window = LoginWindow(self)
        self.user_name = ""
        self.username = ""
        self.save_count = 0
        self.achieve_count = 0
        self.todo_data_store = []
        self.current_sort_index = 5
        self.current_sort_order = 0
        self.copied_item_id = None
        self.due_today_count = 0
        self.due_today_titles = []
        self.overdue_count = 0
        self.earliest_overdue_time = None
        self.earliest_not_overdue_time = None
        self.remaining_hours = None
        self.remaining_minutes = None

        self.stack = QStackedWidget(self)
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.stack)
        self.setLayout(layout)

        self.start_screen = StartScreen(self)
        self.menu_screen = MenuScreen(self)
        self.option_screen = OptionScreen(main_window=self)
        self.todo_screen = ToDoApp(main_window=self, user_name=self.user_name, data_list=self.todo_data_store)
        self.award_screen = AwardScreen(self)
        self.edit_screen = EditScreen(main_window=self)
        self.data_screen = DataScreen(main_window=self)

        self.stack.addWidget(self.start_screen)
        self.stack.addWidget(self.menu_screen)
        self.stack.addWidget(self.option_screen)
        self.stack.addWidget(self.todo_screen)
        self.stack.addWidget(self.award_screen)
        self.stack.addWidget(self.edit_screen)
        self.stack.addWidget(self.data_screen)
       
        self.type_names = ["pastime(free)", "study", "???"]
        self.load_local_data()

    def save_data(self):
        try:
            with open("data/todo_data.json", "w", encoding="utf-8") as f:
                json.dump(self.todo_data_store, f, ensure_ascii=False, indent=2)
            print("保存しました:","data/todo_data.json")
        except Exception as e:
            print("保存エラー(todo):", e)
    # アプリ保存
        try:
            with open("data/option.json", "w", encoding="utf-8") as f:
                json.dump(self.info, f, ensure_ascii=False, indent=4)
            print("保存しました: data/option.json")
        except Exception as e:
            print("保存エラー(info):", e)

        try:
            with open("data/mochivation.json", "w", encoding="utf-8") as f:
                json.dump(self.mochivation_data, f, ensure_ascii=False, indent=4)
            print("保存しました: data/mochivation.json")
        except Exception as e:
            print("保存エラー(mochivation):", e)
    # 達成度更新
        self.todo_screen.header_overlay.update_achievement()
        self.award_screen.update_display()

    def update_custom_type_name(self, new_name):
        self.type_names[2] = new_name
        self.edit_screen.switcher2.update_item_at(2, new_name)
        
    def show_menu(self):
        self.start_screen.movie.stop()
        self.stack.setCurrentWidget(self.menu_screen)

    def show_option(self):
        self.stack.setCurrentWidget(self.option_screen)

    def show_todo(self):
        self.stack.setCurrentWidget(self.todo_screen)

    def show_award(self):
        self.stack.setCurrentWidget(self.award_screen)

    def show_edit(self):
        self.stack.setCurrentWidget(self.edit_screen)

    def show_data_screen(self, item_data):
       # DataScreen にデータを渡して更新
        self.data_screen.set_item(item_data)
        self.fade_to(self.data_screen)#fade_to スタイル

    def show_data(self,item_data):
        self.data_screen.set_item(item_data)
        self.stack.setCurrentWidget(self.data_screen)

    def load_local_data(self):
        if os.path.exists("data/todo_data.json"):
            try:
                with open("data/todo_data.json", "r", encoding="utf-8") as f:
                    self.todo_data_store = json.load(f)
                print("ローカルデータ読み込み成功")
            except Exception as e:
                print("ローカルデータ読み込み失敗:", e)
                self.todo_data_store = []
        else:
            self.todo_data_store = []

        if os.path.exists("data/option.json"):
            with open("data/option.json", "r", encoding="utf-8") as f:
                self.info = json.load(f)
        else:
            self.info = { "username": "", "save_count": 0, "achieve_count": 0 ,"weekly_mochivation_max": 0}
        
        self.username = self.info.get("username", "")
        self.save_count = self.info.get("save_count", 0)
        self.achieve_count = self.info.get("achieve_count", 0)
        self.weekly_mochivation_max = self.info.get("weekly_mochivation_max", 0)
        self.login_count = self.info.get("login_count", 0)
        self.login_count_new = self.login_count + 1
        self.info["login_count"] = self.login_count_new

        if os.path.exists("data/mochivation.json"):
            try:
                with open("data/mochivation.json", "r", encoding="utf-8") as f:
                    self.mochivation_data = json.load(f)
                print("やる気データ読み込み成功")
            except Exception as e:
                print("やる気データ読み込み失敗:", e)
                self.mochivation_data = []
        else:
        # 初期値（空のリスト）
            self.mochivation_data = []

        self.todo_screen.todo_data_store = self.todo_data_store
        self.todo_screen.apply_sorting(
        self.current_sort_index,
        self.current_sort_order)
        self.todo_screen.header_overlay.update_achievement()
        self.todo_screen.header_overlay.update_user_name(self.username)
        self.todo_screen.start_log.update_user_name(self.username)
        self.award_screen.update_display()
        self.update_mochivation_summary()

    def calculate_today_info(self):#todoのshowにある
        today = datetime.now()
        today_str = today.strftime("%Y/%m/%d")
        due_today = []
        overdue = []
        not_overdue = []
        for item in self.todo_data_store:
            if item.get("deleted", False):
                continue
            try:
                deadline = datetime.strptime(item["date"], "%Y/%m/%d %H:%M")
            except:
                continue

            if item["date"].startswith(today_str):
                due_today.append(item)
                if deadline < today:
                    overdue.append((item, deadline))
                else:
                    not_overdue.append((item, deadline))

        self.due_today_count = len(due_today)#代入
        self.due_today_titles = [item["todo"] for item in due_today]
        self.overdue_count = len(overdue)
        self.earliest_overdue_time = (
            min(overdue, key=lambda x: x[1])[1] if overdue else None
        )
        if not_overdue:
            earliest = min(not_overdue, key=lambda x: x[1])[1]
            delta = earliest - today
            self.earliest_not_overdue_time = earliest
            self.remaining_hours = delta.seconds // 3600
            self.remaining_minutes = (delta.seconds % 3600) // 60
        else:
            self.earliest_not_overdue_time = None
            self.remaining_hours = None
            self.remaining_minutes = None

        #self.todo_screen.start_log.generate_choices(self.due_today_count)
        self.todo_screen.start_log.update_count(self.due_today_count, self.due_today_titles, self.overdue_count, self.earliest_overdue_time, self.earliest_not_overdue_time, self.remaining_hours, self.remaining_minutes)
        print(self.due_today_count)

    def update_mochivation_summary(self):
        if len(self.mochivation_data) > 7:#データ数7件以下
            self.mochivation_data.sort(
                key=lambda x: datetime.strptime(x["date"], "%Y/%m/%d")
            )
        # 最新7件だけ
            self.mochivation_data = self.mochivation_data[-7:]
        today = datetime.now().date()#やる気合計
        seven_days_ago = today - timedelta(days=7)
        weekly_total = 0
        for entry in self.mochivation_data:
            entry_date = datetime.strptime(entry["date"], "%Y/%m/%d").date()
            if seven_days_ago <= entry_date <= today:
                weekly_total += entry.get("mochivation", 0)

        if weekly_total > self.info.get("weekly_mochivation_max", 0):
            self.info["weekly_mochivation_max"] = weekly_total

        self.save_data()
        self.todo_screen.header_overlay.update_mochivation(weekly_total)
        return weekly_total

    def flash_widget_color(self, widget, callback):
        original_style = widget.styleSheet()

        flash_style = original_style.replace("color: black;", "color: #696969;")

        widget.setStyleSheet(flash_style)

        QTimer.singleShot(70, lambda: (
            widget.setStyleSheet(original_style),
            callback()
        )) 
    def fade_to(self, target_widget):
        if hasattr(self, "todo_app"):
            self.todo_app.reset_temp_states()
            self.todo_app.update()
        self.transition_sound.play()
        current_widget = self.stack.currentWidget()
        target_widget.setFocus()
    # フェードアウト設定
        fade_out = QGraphicsOpacityEffect()
        current_widget.setGraphicsEffect(fade_out)
        self.anim_out = QPropertyAnimation(fade_out, b"opacity")
        self.anim_out.setDuration(500)
        self.anim_out.setStartValue(1)
        self.anim_out.setEndValue(0)
        self.anim_out.setEasingCurve(QEasingCurve.InOutQuad)

        def switch_and_fade_in():
            self.stack.setCurrentWidget(target_widget)
            fade_in = QGraphicsOpacityEffect()
            target_widget.setGraphicsEffect(fade_in)
            self.anim_in = QPropertyAnimation(fade_in, b"opacity")
            self.anim_in.setDuration(500)
            self.anim_in.setStartValue(0)
            self.anim_in.setEndValue(1)
            self.anim_in.setEasingCurve(QEasingCurve.InOutQuad)
            self.anim_in.start()

        self.anim_out.finished.connect(switch_and_fade_in)
        self.anim_out.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showFullScreen()
    window.show()
    sys.exit(app.exec_())