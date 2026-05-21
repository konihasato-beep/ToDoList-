import json
import requests
from google.oauth2 import service_account
import google.auth.transport.requests

# サービスアカウント鍵のパス
SERVICE_ACCOUNT_FILE = "data/todoapp-50f7b-firebase-adminsdk-fbsvc-1abdc1df90.json"

# Firebase プロジェクトID
PROJECT_ID = "todoapp-50f7b"

FCM_TOKEN = "eiAR5Oa7TbSnBqEtzrn_5d:APA91bFOIevik8uMQlHeAl5IYItNklGLOjoLA4jtwmdtmBy5OpaWY33GrxNVqMCMSnkaGW-dhnDEtQs3GCrIjJ49d7klQThvYCFaFUSgnHK8z_9j0LfThNM"

def get_access_token():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/firebase.messaging"]
    )
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token

def send_push_notification(token, title, body):
    url = f"https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send"

    access_token = get_access_token()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; UTF-8",
    }

    payload = {
        "message": {
            "token": token,
            "notification": {
                "title": title,
                "body": body
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    print("FCM response:", response.text)
    
