# AD Provisioning Automation

This project provides an automated solution for provisioning Active Directory (AD) users based on webhooks received from ManageEngine Service Desk Plus (SDP).

## Features

- **Automated User Creation**: Parses HTML tables from SDP ticket descriptions to extract user details.
- **Credential Generation**: Auto-generates secure passwords and standard usernames (firstname.lastname).
- **Active Directory Integration**: Uses a PowerShell script to create users, set attributes, manage groups, and handle account expiration.
- **SDP Feedback**: Automatically updates the source SDP ticket with the results of the provisioning process, including generated credentials or error logs.
- **Security**: Validates incoming webhooks using a secret token.

## Tech Stack

- **Backend**: Flask (Python)
- **Scripting**: PowerShell (Active Directory module)
- **Parsing**: BeautifulSoup4
- **Integration**: SDP API v3

## Directory Structure

- `app.py`: Main Flask application and webhook handler.
- `create_ad_user.ps1`: PowerShell script for interacting with AD.
- `create_user.py`: Python wrapper for the PowerShell script.
- `bulk_parser.py`: Logic for parsing SDP HTML descriptions.
- `logs/`: Directory for application and script logs.

## Setup & Configuration

1. **Environment Variables**: Create a `.env` file with the following:
   ```env
   # Flask Config
   FLASK_HOST=0.0.0.0
   FLASK_PORT=5000
   WEBHOOK_SECRET_TOKEN=your_secret_here
   PARTNER_EMAIL_DOMAIN=partnersafaricom.et

   # SDP Config
   SDP_API_KEY=your_sdp_api_key
   SDP_BASE_URL=https://your-sdp-instance/api/v3/requests
   SDP_LOG_FIELD=udf_mline_908
   ```

2. **Dependencies**: Install Python requirements:
   ```bash
   pip install -r requirements.txt
   ```

3. **AD Permissions**: Ensure the service account running the app has permissions to create users in the target OU.

## Usage

Start the application:
```bash
python app.py
```

The application listens for `POST` requests at `/webhook/create-user`.

## Production Deployment

For production usage, it is recommended to:
- Use a production WSGI server like `Waitress`.
- Run as a Windows Service using `NSSM`.
- Configure a reverse proxy (IIS/Nginx) for HTTPS.
