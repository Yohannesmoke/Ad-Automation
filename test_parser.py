from bulk_parser import parse_html_table
import json

html_content = r'''<div class="sdp-ze-default-wrapper" style="font-family: Roboto, Arial; font-size: 10pt"><div><br/></div><table style="font-size: 13px; border-collapse: collapse; border-spacing: 2px; background-color: rgb(255, 255, 255); outline: 0px; color: rgb(17, 17, 17); font-family: Roboto, Arial; font-style: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-transform: none; widows: 2; word-spacing: 0px; white-space: normal; border: 1px solid rgb(171, 171, 171); table-layout: auto !important" class="ze_tableView" cellpadding="2" cellspacing="2" border="1"><tbody style="outline: 0px"><tr style="outline: 0px"><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px"><div style="outline: 0px; text-align: center" class="align-center"><b>FirstName</b><br/></div></td><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 147.41px"><div style="outline: 0px; text-align: center" class="align-center"><b>LastName</b><br/></div></td><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 230.102px"><div style="outline: 0px; text-align: center" class="align-center"><b>TelephoneNumber</b><br/></div></td><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 172.789px"><div style="outline: 0px; text-align: center" class="align-center"><b>Email</b><br/></div></td></tr><tr style="outline: 0px"><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px">Yohannes<br/></td><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px"><div>Mekonen<br/></div></td><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px"><div>+27190000000<br/></div></td><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px"><div>Yohannesmekonen@gmail.com<br/></div></td></tr><tr style="outline: 0px"><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px">Ruhama<br/></td><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px"><div>Mekonen<br/></div></td><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px"><div>+2517010203<br/></div></td><td style="padding: 2px; color: rgb(51, 51, 51); outline: 0px; border: 1px solid rgb(171, 171, 171); vertical-align: top; width: 154.289px"><div>ruhamamekonen@gmail.com<br/></div></td></tr></tbody></table><div><br/></div></div>'''

def test_parser():
    try:
        users, skipped = parse_html_table(html_content)
        print(f"Successfully parsed {len(users)} users.")
        print(json.dumps(users, indent=2))
        if skipped:
            print(f"Skipped {len(skipped)} rows:")
            print(json.dumps(skipped, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_parser()
