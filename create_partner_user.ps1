<#
.SYNOPSIS

.NOTES
    Called once per user row extracted from the SDP description HTML table.
#>

param(
    [Parameter(Mandatory=$true)]  [string]$FirstName,
    [Parameter(Mandatory=$true)]  [string]$LastName,
    [Parameter(Mandatory=$true)]  [string]$Email,
    [Parameter(Mandatory=$true)]  [string]$UserLogonName,        # sAMAccountName  e.g. abdulmenan.tenker
    [Parameter(Mandatory=$true)]  [string]$Password,             # per-user generated password
    [Parameter(Mandatory=$true)]  [string]$OU,                   # full DN
    [Parameter(Mandatory=$false)] [string]$Groups       = "",    # semicolon-separated
    [Parameter(Mandatory=$false)] [string]$Phone        = "",
    [Parameter(Mandatory=$false)] [string]$Description  = "",    # Reason for Access
    [Parameter(Mandatory=$false)] [string]$DisplayName  = "",    # e.g. "FirstName LastName - Partner|Project"
    [Parameter(Mandatory=$false)] [string]$Manager      = "",    # sAMAccountName of manager
    [Parameter(Mandatory=$false)] [string]$Company      = "",    # extracted from DisplayName pattern
    [Parameter(Mandatory=$false)] [string]$ChangePasswordAtLogon = "true"
)

# ── Derive UPN from email domain ───────────────────────────────────────────────
$Domain = ($Email -split "@" | Select-Object -Last 1)
$UPN    = "$UserLogonName@$Domain"

if (-not $DisplayName) {
    $DisplayName = "$FirstName $LastName"
}

# ── Helper: output JSON and exit ───────────────────────────────────────────────
function Exit-Result {
    param([bool]$Success, [string]$Message, [string]$User, [hashtable]$Details = @{})
    $obj = [ordered]@{
        success   = $Success
        message   = $Message
        username  = $User
        timestamp = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        details   = $Details
    }
    Write-Output ($obj | ConvertTo-Json -Compress -Depth 5)
    exit $(if ($Success) { 0 } else { 1 })
}

# ── Validate OU (must be full DN for partner accounts) ────────────────────────
if ($OU -notmatch "^(OU|DC)=") {
    try {
        $ouObj = Get-ADOrganizationalUnit -Filter "Name -eq '$OU'" -ErrorAction Stop | Select-Object -First 1
        if (-not $ouObj) { Exit-Result $false "OU '$OU' not found in Active Directory." $UserLogonName }
        $OU = $ouObj.DistinguishedName
    } catch {
        Exit-Result $false "Error resolving OU '$OU': $_" $UserLogonName
    }
}

# ── Check for duplicate sAMAccountName ────────────────────────────────────────
$existing = Get-ADUser -Filter "SamAccountName -eq '$UserLogonName'" -ErrorAction SilentlyContinue
if ($existing) {
    Exit-Result $false "User '$UserLogonName' already exists in Active Directory." $UserLogonName
}

# ── Resolve Manager (sAMAccountName → DN) ─────────────────────────────────────
$managerDN = $null
if ($Manager) {
    try {
        $mgr = Get-ADUser -Filter "SamAccountName -eq '$Manager'" -ErrorAction Stop | Select-Object -First 1
        if ($mgr) { $managerDN = $mgr.DistinguishedName }
        else { Write-Warning "Manager '$Manager' not found in AD — skipping manager field." }
    } catch {
        Write-Warning "Could not resolve manager '$Manager': $_ — skipping manager field."
    }
}

# ── Convert ChangePasswordAtLogon string → bool ────────────────────────────────
$ChangeAtLogon = $ChangePasswordAtLogon.ToLower() -notin @("false", "0", "no")


$SecurePass = ConvertTo-SecureString $Password -AsPlainText -Force

# ── Account expiry: 1 year from today ─────────────────────────────────────────
$ExpiryDate = (Get-Date).AddYears(1)

# ── Build New-ADUser params ────────────────────────────────────────────────────
$userParams = @{
    GivenName             = $FirstName
    Surname               = $LastName
    Name                  = "$FirstName $LastName"
    DisplayName           = $DisplayName
    SamAccountName        = $UserLogonName
    UserPrincipalName     = $UPN
    EmailAddress          = $Email
    AccountPassword       = $SecurePass
    Enabled               = $true
    ChangePasswordAtLogon = $ChangeAtLogon
    PasswordNeverExpires  = $false
    AccountExpirationDate = $ExpiryDate
    Path                  = $OU
}

if ($Phone)       { $userParams["OfficePhone"] = $Phone }
if ($Description) { $userParams["Description"] = $Description }
if ($Company)     { $userParams["Company"]      = $Company }
if ($managerDN)   { $userParams["Manager"]      = $managerDN }

# ── Create the user ────────────────────────────────────────────────────────────
try {
    New-ADUser @userParams -ErrorAction Stop
} catch {
    Exit-Result $false "Failed to create user '$UserLogonName': $_" $UserLogonName
}

# ── Add to groups (semicolon-separated) ───────────────────────────────────────
$groupResults = @()
if ($Groups) {
    $groupList = $Groups -split ";" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
    foreach ($grp in $groupList) {
        if ($grp -ieq "Domain Users") {
            $groupResults += "OK: Domain Users (automatic)"
            continue
        }
        try {
            Add-ADGroupMember -Identity $grp -Members $UserLogonName -ErrorAction Stop
            $groupResults += "OK: $grp"
        } catch {
            $groupResults += "FAILED: $grp ($_)"
        }
    }
}

$groupSummary = if ($groupResults.Count -gt 0) { $groupResults -join " | " } else { "none assigned" }

$details = @{
    full_name        = "$FirstName $LastName"
    display_name     = $DisplayName
    sam_account_name = $UserLogonName
    upn              = $UPN
    email            = $Email
    phone            = $Phone
    description      = $Description
    company          = $Company
    manager          = $Manager
    ou               = $OU
    groups_result    = $groupResults
    expiry_date      = $ExpiryDate.ToString("yyyy-MM-dd")
    account_enabled  = $true
}

$msg = "User '$UserLogonName' ($FirstName $LastName) created. Expires: $($ExpiryDate.ToString('yyyy-MM-dd')). Groups: $groupSummary."
Exit-Result $true $msg $UserLogonName $details