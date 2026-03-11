param(
    [Parameter(Mandatory=$true)][string]$FirstName,
    [Parameter(Mandatory=$true)][string]$LastName,
    [Parameter(Mandatory=$false)][string]$DisplayName,
    [Parameter(Mandatory=$false)][string]$Description,
    [Parameter(Mandatory=$false)][string]$TelephoneNumber,
    [Parameter(Mandatory=$true)][string]$Email,
    [Parameter(Mandatory=$true)][string]$UserLogonName,
    [Parameter(Mandatory=$true)][string]$Password,
    [Parameter(Mandatory=$false)][bool]$ChangePassword = $true,
    [Parameter(Mandatory=$false)][string]$Manager,
    [Parameter(Mandatory=$false)][string]$Groups,
    [Parameter(Mandatory=$true)][string]$OU,
    [Parameter(Mandatory=$false)][string]$AccountExpirationDate
)

# Debug Log - Append to a local file to see what was received
$DebugLog = Join-Path $PSScriptRoot "ad_script_debug.log"
"--- New Execution (User: $UserLogonName) ---" | Out-File -FilePath $DebugLog -Append
"Params: FN=$FirstName, LN=$LastName, DN=$DisplayName, Desc=$Description, Phone=$TelephoneNumber, Email=$Email, UN=$UserLogonName, PW=(hidden), Manager=$Manager, Groups=$Groups, OU=$OU, Expiry=$AccountExpirationDate" | Out-File -FilePath $DebugLog -Append

# Result scaffold
$result = [ordered]@{
    success   = $false
    message   = ""
    username  = $UserLogonName
    timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    details   = [ordered]@{
        FirstName = $FirstName
        LastName  = $LastName
        Email     = $Email
        OU        = $OU
        AccountExpires = $AccountExpirationDate
    }
}

try {
    if (-not (Get-Module -Name ActiveDirectory)) {
        Import-Module ActiveDirectory -ErrorAction Stop
    }

    # Check existence
    $existing = Get-ADUser -Filter "SamAccountName -eq '$UserLogonName'" -ErrorAction SilentlyContinue
    if ($existing) {
        $result.message = "User already exists in AD"
        Write-Output ($result | ConvertTo-Json -Compress)
        exit 0
    }

    # Resolve Manager
    $managerDN = $null
    if (-not [string]::IsNullOrWhiteSpace($Manager)) {
        $mgrObj = Get-ADUser -Filter "SamAccountName -eq '$Manager'" -ErrorAction SilentlyContinue
        if (-not $mgrObj) {
            $mgrObj = Get-ADUser -Filter "Name -eq '$Manager'" -ErrorAction SilentlyContinue
        }
        if (-not $mgrObj) {
            $mgrObj = Get-ADUser -Filter "DisplayName -eq '$Manager'" -ErrorAction SilentlyContinue
        }
        
        if ($mgrObj) { 
            $managerDN = $mgrObj.DistinguishedName 
            $result.details.ManagerFound = "Yes ($($mgrObj.SamAccountName))"
        } else {
            $result.details.ManagerFound = "No (Could not find user '$Manager')"
            "WARNING: Manager '$Manager' not found. Creating user without manager." | Out-File -FilePath $DebugLog -Append
        }
    }

    $finalDisplayName = if ([string]::IsNullOrWhiteSpace($DisplayName)) { "$FirstName $LastName" } else { $DisplayName }

    $adParams = @{
        Name                  = $finalDisplayName
        GivenName             = $FirstName
        Surname               = $LastName
        DisplayName           = $finalDisplayName
        Description           = $Description
        SamAccountName        = $UserLogonName
        UserPrincipalName     = "$UserLogonName@$((Get-ADDomain).DNSRoot)"
        EmailAddress          = $Email
        AccountPassword       = (ConvertTo-SecureString $Password -AsPlainText -Force)
        Enabled               = $true
        ChangePasswordAtLogon = $ChangePassword
        Path                  = $OU
    }

    if ($TelephoneNumber) {
        $adParams["OtherAttributes"] = @{ telephoneNumber = $TelephoneNumber }
    }

    if ($managerDN) {
        $adParams["Manager"] = $managerDN
    }

    # Handle Account Expiration
    if ($AccountExpirationDate -and $AccountExpirationDate -ne "never") {
        try {
            $expiryDate = [DateTime]::ParseExact($AccountExpirationDate, "yyyy-MM-dd", $null)
            $adParams["AccountExpirationDate"] = $expiryDate
        } catch {
            "WARNING: Could not parse AccountExpirationDate '$AccountExpirationDate'. Skipping expiry." | Out-File -FilePath $DebugLog -Append
        }
    }

    # Execute
    try {
        "DEBUG: Creating user with parameters:" | Out-File -FilePath $DebugLog -Append
        $adParams.Keys | ForEach-Object { "$_ = $($adParams[$_])" } | Out-File -FilePath $DebugLog -Append
        New-ADUser @adParams -ErrorAction Stop
    } catch {
        "ERROR creating user: $($_.Exception.Message)" | Out-File -FilePath $DebugLog -Append
        throw $_
    }

    # Groups
    $groupsResult = @()
    if (-not [string]::IsNullOrWhiteSpace($Groups)) {
        $groupList = $Groups -split ","
        foreach ($gn in $groupList) {
            $gn = $gn.Trim()
            if ($gn -eq "Domain Users" -or [string]::IsNullOrWhiteSpace($gn)) { continue }
            
            $grpObj = Get-ADGroup -Filter "Name -eq '$gn'" -ErrorAction SilentlyContinue
            if ($grpObj) {
                Add-ADGroupMember -Identity $grpObj -Members $UserLogonName -ErrorAction SilentlyContinue
                $groupsResult += @{ name = $gn; status = "Added" }
            } else {
                $groupsResult += @{ name = $gn; status = "Warning: Group not found" }
            }
        }
    }

    $result.success = $true
    $result.message = "User created successfully"
    $result.details.groups_result = $groupsResult
    
    Write-Output ($result | ConvertTo-Json -Compress)
    exit 0

} catch {
    $errorMsg = $_.Exception.Message
    if ($_.Exception.InnerException) {
        $errorMsg = $_.Exception.InnerException.Message
    }
    $result.message = $errorMsg
    "EXCEPTION: $errorMsg" | Out-File -FilePath $DebugLog -Append
    Write-Output ($result | ConvertTo-Json -Compress)
    exit 1
}
