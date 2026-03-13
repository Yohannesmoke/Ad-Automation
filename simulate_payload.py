import requests
import json

# Configuration
URL = "http://127.0.0.1:5000/webhook/create-user"
TOKEN = "TemporaryToken123"

# The payload provided by the user
payload = {
  "vendor name": "Besys technologies",
  "AD Account Duration": "",
  "Groups": "ET-RDS-Users; vpn_vendor; OTP by Email; Vendor Account - All; Vendors-HAYIK-SSID",
  "ou": "OU=User,OU=EBU-Distributors,DC=server,DC=local",
  "description": "<div class=\"sdp-ze-default-wrapper\" style=\"font-family: Roboto, Arial; font-size: 10pt\"><div><br/></div><table style=\"font-size: 13px; border-collapse: collapse; border-spacing: 2px; background-color: rgb(255, 255, 255); outline: 0px; color: rgb(17, 17, 17); font-family: Roboto, Arial; font-style: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-transform: none; widows: 2; word-spacing: 0px; white-space: normal; border: 1px solid rgb(171, 171, 171); table-layout: auto !important\" class=\"ze_tableView\" cellpadding=\"2\" cellspacing=\"2\" border=\"1\"><tbody style=\"outline: 0px\"><tr style=\"outline: 0px\"><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px\"><div style=\"outline: 0px; text-align: center\" class=\"align-center\"><b>FirstName</b><br/></div></td><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 147.41px\"><div style=\"outline: 0px; text-align: center\" class=\"align-center\"><b>LastName</b><br/></div></td><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 230.102px\"><div style=\"outline: 0px; text-align: center\" class=\"align-center\"><b>TelephoneNumber</b><br/></div></td><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 172.789px\"><div style=\"outline: 0px; text-align: center\" class=\"align-center\"><b>Email</b><br/></div></td></tr><tr style=\"outline: 0px\"><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px\">Yohannes<br/></td><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px\"><div>Mekonen<br/></div></td><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px\"><div>+27190000000<br/></div></td><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px\"><div>Yohannesmekonen@gmail.com<br/></div></td></tr><tr style=\"outline: 0px\"><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px\">Ruhama<br/></td><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px\"><div>Mekonen<br/></div></td><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px\"><div>+2517010203<br/></div></td><td style=\"padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px\"><div>ruhamamekonen@gmail.com<br/></div></td></tr></tbody></table><div><br/></div></div>",
  "Reason for Access": "for my project with safaricom",
  "Outlook Email required ": "YES",
  "Manager": "Heather Graham",
  "ticket id": "41"
}

def simulate():
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Token": TOKEN
    }
    try:
        print(f"Sending request to {URL}...")
        response = requests.post(URL, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        print("Response Body:")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    simulate()
