import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg.set_content("Test email")
msg['Subject'] = 'Test'
msg['From'] = 'team.sourcegraph@gmail.com'
msg['To'] = 'team.sourcegraph@gmail.com'

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('team.sourcegraph@gmail.com', 'xozf qdlc kyav tdpg')
    server.send_message(msg)
    server.quit()
    print("Email sent successfully")
except Exception as e:
    print(f"Failed: {e}")
