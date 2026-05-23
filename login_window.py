from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout, QLabel
import sys
import json
from PyQt5.QtGui import QPixmap, QPainter, QIcon, QColor, QMovie, QFont, QIntValidator, QBitmap
from PyQt5.QtCore import QRect, Qt, QObject, QEvent, QSize, QTimer, QUrl,QPropertyAnimation, QEasingCurve ,QPoint, QDate, QDateTime
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QStackedWidget, QLabel, QGraphicsOpacityEffect, QSlider, QStackedLayout
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QSizePolicy, QScrollArea, QButtonGroup, QFrame
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QSoundEffect, QSound
from PyQt5.QtMultimediaWidgets import QVideoWidget
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle, os
from google.auth.transport.requests import Request
import requests

class LoginWindow(QWidget):
    def __init__(self,main_window):
        super().__init__()
        self.main_window = main_window
        self.creds = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Google login")
        font = QFont("Mv Boli", 25)
        font1 = QFont("Mv Boli", 15)
        self.login_button = QPushButton("Google login")
        self.status_label = QLabel("Guest mode")
        self.logout_button = QPushButton("Logout")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.label = QLabel("Please log in with your Google account to link"
        "<br> with this app;"
        "<br>This will allow notifications to be sent"
        "<br> to your smartphone;"
        "<br>To log in, tap Google Login;"
        "<br>At first, you'll see Guest mode, but if it changes"
        "<br> to Login successful!, you're all set;"
        "<br>To log out, tap Logout;")
        self.label.setFixedSize(757, 500)
        self.status_label.setFixedSize(757, 200)
        self.logout_button.setFixedSize(757, 100)
        self.login_button.setFixedSize(757, 100)
        self.label.setStyleSheet("color: black; margin-top:0px;")
        self.status_label.setStyleSheet("color: black; margin:0px;")
        self.logout_button.setStyleSheet("color: black; margin:0px;margin-bottom:0px; padding:0px;")
        self.login_button.setStyleSheet("color: black; margin:0px;margin-bottom:0px; padding:0px;")

        self.status_label.setFont(font)
        self.login_button.setFont(font)
        self.logout_button.setFont(font)
        self.label.setFont(font1)

        self.login_button.clicked.connect(self.authenticate_user)
        self.logout_button.clicked.connect(self.logout_user)
        
        self.logout_button.hide()

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.login_button)
        layout.addWidget(self.logout_button)
        self.setLayout(layout)
        self.check_login_state()

    def authenticate_user(self):
        if os.path.exists("token.pickle"): #シークレット
            with open("token.pickle", "rb") as token:
                self.creds = pickle.load(token)
            self.status_label.setText("Logged in")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "data/ファイルのパス.json",
                scopes = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/tasks"]
            )
            self.creds = flow.run_local_server(port=0)
            if self.creds.expired and self.creds.refresh_token: 
                self.creds.refresh(Request())
            with open("token.pickle", "wb") as token:
                pickle.dump(self.creds, token)
                
            self.status_label.setText("Login successful!")
            email = self.get_user_email()
            self.status_label.setText(f"Logged in: <br>{email}")
            self.login_button.hide()
            self.logout_button.show()

    def logout_user(self):
        if os.path.exists("token.pickle"):#シークレット
            os.remove("token.pickle")
        self.creds = None
        self.status_label.setText("Guest mode")
        self.logout_button.hide()
        self.login_button.show()
    
    def check_login_state(self):
        if os.path.exists("token.pickle"):
            try:
                with open("token.pickle", "rb") as token:
                    self.creds = pickle.load(token)
                self.status_label.setText("Logged in")

                email = self.get_user_email()
                self.status_label.setText(f"Logged in:<br> {email}")

                self.login_button.hide()
                self.logout_button.show()
            except Exception:
                self.status_label.setText("Guest mode")
                self.creds = None

    def get_user_email(self):
        try:
            self.creds.refresh(Request())
            response = requests.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {self.creds.token}"}
            )
            if response.status_code == 200:
                return response.json().get("email", "Unknown user")
            else:
                return "Email fetch failed"
        except Exception as e:
            return f"Error: {e}"
