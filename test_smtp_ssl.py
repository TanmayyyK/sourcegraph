import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg.set_content("Test email SSL")
msg['Subject'] = 'Test SSL'
msg['From'] = 'team.sourcegraph@gmail.com'
msg['To'] = 'team.sourcegraph@gmail.com'

try:
    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.login('team.sourcegraph@gmail.com', 'xozf qdlc kyav tdpg')
    server.send_message(msg)
    server.quit()
    print("Email sent successfully via SSL")
except Exception as e:
    print(f"Failed: {e}")
