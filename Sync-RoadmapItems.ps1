<#
.SYNOPSIS
    Fetches Microsoft Azure and M365 roadmap RSS feeds, filters by product/status,
    and creates Azure DevOps work items for matching items.

.DESCRIPTION
    Reads roadmap-filter.json for filter configuration, fetches the RSS feeds,
    filters items by product, status, and excluded types, checks for duplicates
    in Azure DevOps, and creates new work items for items not already tracked.

.PARAMETER ConfigPath
    Path to the roadmap-filter.json config file. Defaults to ./roadmap-filter.json.

.PARAMETER DaysBack
    Only process items published within this many days. Defaults to 7.

.PARAMETER DryRun
    If set, shows what would be created without actually creating work items.

.PARAMETER Organization
    Azure DevOps organization URL (e.g., https://dev.azure.com/myorg).
    Can also be set via ADO_ORGANIZATION environment variable or pipeline variable.

.PARAMETER Pat
    Azure DevOps Personal Access Token. Can also be set via AZURE_DEVOPS_PAT
    environment variable. In ADO pipelines, use System.AccessToken instead.
#>
[CmdletBinding()]
param(
    [string]$ConfigPath = "./roadmap-filter.json",
    [int]$DaysBack = 7,
    [switch]$DryRun,
    [string]$Organization = $env:ADO_ORGANIZATION,
    [string]$Pat = $env:AZURE_DEVOPS_PAT
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

#region --- Configuration ---

if (-not (Test-Path $ConfigPath)) {
    Write-Error "Config file not found: $ConfigPath"
    exit 1
}

$config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
Write-Host "Loaded config from $ConfigPath" -ForegroundColor Cyan

# Validate required ADO settings
$adoProject = $config.ado.project
$adoWorkItemType = if ($config.ado.workItemType) { $config.ado.workItemType } else { "Feature" }

if (-not $DryRun -and (-not $Organization -or -not $adoProject)) {
    Write-Error "ADO organization and project must be configured. Set ADO_ORGANIZATION env var and ado.project in config."
    exit 1
}

if (-not $DryRun -and -not $Pat) {
    # Fall back to System.AccessToken in ADO pipelines
    if ($env:SYSTEM_ACCESSTOKEN) {
        $Pat = $env:SYSTEM_ACCESSTOKEN
    } else {
        Write-Error "No PAT provided. Set AZURE_DEVOPS_PAT env var or use System.AccessToken in pipeline."
        exit 1
    }
}

$feedUrls = @{
    azure = "https://www.microsoft.com/releasecommunications/api/v2/azure/rss"
    m365  = "https://www.microsoft.com/releasecommunications/api/v2/m365/rss"
}

#endregion

#region --- RSS Fetch & Parse ---

function Get-RoadmapItems {
    param([string]$FeedUrl, [string]$FeedName)

    Write-Host "  Fetching $FeedName feed..." -ForegroundColor Gray
    try {
        [xml]$rss = (Invoke-WebRequest -Uri $FeedUrl -UseBasicParsing -TimeoutSec 30).Content
    } catch {
        Write-Warning "Failed to fetch $FeedName feed: $_"
        return @()
    }

    $items = @()
    foreach ($item in $rss.rss.channel.item) {
        $categories = @($item.category)

        $parsed = [PSCustomObject]@{
            Feed        = $FeedName
            Guid        = $item.guid.'#text'
            Title       = $item.title -replace '^\[.*?\]\s*', ''
            RawTitle    = $item.title
            Link        = $item.link
            Description = $item.description
            PubDate     = [datetime]::Parse($item.pubDate)
            Categories  = $categories
            Status      = ($categories | Where-Object {
                $_ -in @('Launched', 'In preview', 'In development', 'In review', 'Rolling out')
            } | Select-Object -First 1)
            Products    = @($categories | Where-Object {
                $_ -notin @('Launched', 'In preview', 'In development', 'In review', 'Rolling out',
                    'General Availability', 'Public Preview', 'Private Preview', 'Preview',
                    'Current Channel', 'Targeted Release', 'Targeted Release (Entire Organization)',
                    'Worldwide (Standard Multi-Tenant)', 'GCC', 'GCC High', 'DoD',
                    'Android', 'iOS', 'Desktop', 'Mac', 'Web', 'Windows',
                    'Developer', 'Teams and Surface Devices',
                    'Features', 'Retirements', 'Compliance', 'Regions & Datacenters',
                    'Operating System', 'SDK and Tools', 'Pricing & Offerings', 'Services', 'Open Source')
            })
            UpdateTypes = @($categories | Where-Object {
                $_ -in @('Features', 'Retirements', 'Compliance', 'Regions & Datacenters',
                    'Operating System', 'SDK and Tools', 'Pricing & Offerings', 'Services', 'Open Source')
            })
        }
        $items += $parsed
    }

    Write-Host "  Parsed $($items.Count) items from $FeedName" -ForegroundColor Gray
    return $items
}

#endregion

#region --- Filtering ---

function Test-ItemMatchesFilter {
    param(
        [PSCustomObject]$Item,
        [PSCustomObject]$Config,
        [int]$DaysBack
    )

    # Date filter
    $cutoff = (Get-Date).AddDays(-$DaysBack)
    if ($Item.PubDate -lt $cutoff) { return $false }

    # Status filter
    if ($Config.statuses -and $Config.statuses.Count -gt 0) {
        if ($Item.Status -notin $Config.statuses) { return $false }
    }

    # Product filter (if products specified, item must match at least one)
    if ($Config.products -and $Config.products.Count -gt 0) {
        $match = $false
        foreach ($prod in $Item.Products) {
            if ($prod -in $Config.products) { $match = $true; break }
        }
        # Also check categories directly for broader matching
        if (-not $match) {
            foreach ($cat in $Item.Categories) {
                if ($cat -in $Config.products) { $match = $true; break }
            }
        }
        if (-not $match) { return $false }
    }

    # Exclude types
    if ($Config.excludeTypes -and $Config.excludeTypes.Count -gt 0) {
        foreach ($ut in $Item.UpdateTypes) {
            if ($ut -in $Config.excludeTypes) { return $false }
        }
    }

    return $true
}

#endregion

#region --- Azure DevOps Integration ---

function Get-AdoHeaders {
    $base64Auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$Pat"))
    return @{
        Authorization  = "Basic $base64Auth"
        "Content-Type" = "application/json-patch+json"
    }
}

function Find-ExistingWorkItem {
    param([string]$RoadmapGuid, [string]$Title)

    $headers = @{
        Authorization  = "Basic $([Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$Pat")))"
        "Content-Type" = "application/json"
    }

    # Search by roadmap GUID in tags
    $wiql = @{
        query = "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '$adoProject' AND [System.Tags] CONTAINS 'RoadmapId:$RoadmapGuid'"
    } | ConvertTo-Json

    $searchUrl = "$Organization/$adoProject/_apis/wit/wiql?api-version=7.1"
    try {
        $result = Invoke-RestMethod -Uri $searchUrl -Method Post -Headers $headers -Body $wiql
        if ($result.workItems.Count -gt 0) {
            return $result.workItems[0].id
        }
    } catch {
        Write-Warning "WIQL search failed: $_"
    }

    return $null
}

function New-AdoWorkItem {
    param([PSCustomObject]$Item)

    $headers = Get-AdoHeaders

    $descriptionHtml = @"
<div>
<p><strong>Source:</strong> Microsoft $($Item.Feed) Roadmap</p>
<p><strong>Status:</strong> $($Item.Status)</p>
<p><strong>Published:</strong> $($Item.PubDate.ToString('yyyy-MM-dd'))</p>
<p><strong>Products:</strong> $($Item.Products -join ', ')</p>
<p><strong>Roadmap Link:</strong> <a href="$($Item.Link)">$($Item.Link)</a></p>
<hr/>
<p>$($Item.Description)</p>
</div>
"@

    $tags = @(
        "Roadmap"
        "RoadmapId:$($Item.Guid)"
        $Item.Feed.ToUpper()
        $Item.Status
    )
    $tags += $Item.Products
    $tagString = $tags -join "; "

    $body = @(
        @{ op = "add"; path = "/fields/System.Title"; value = $Item.Title }
        @{ op = "add"; path = "/fields/System.Description"; value = $descriptionHtml }
        @{ op = "add"; path = "/fields/System.Tags"; value = $tagString }
    ) | ConvertTo-Json -Depth 5

    $url = "$Organization/$adoProject/_apis/wit/workitems/`$$($adoWorkItemType)?api-version=7.1"

    try {
        $result = Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $body
        return $result
    } catch {
        Write-Warning "Failed to create work item for '$($Item.Title)': $_"
        return $null
    }
}

#endregion

#region --- Main Execution ---

Write-Host ""
Write-Host "=== Microsoft Roadmap Sync ===" -ForegroundColor Cyan
Write-Host "Date range: last $DaysBack days (since $((Get-Date).AddDays(-$DaysBack).ToString('yyyy-MM-dd')))"
Write-Host "Feeds: $($config.feeds -join ', ')"
Write-Host "Products filter: $(if ($config.products.Count -eq 0) { 'All' } else { $config.products.Count.ToString() + ' products' })"
Write-Host "Status filter: $($config.statuses -join ', ')"
Write-Host "Exclude types: $($config.excludeTypes -join ', ')"
if ($DryRun) { Write-Host "MODE: DRY RUN (no work items will be created)" -ForegroundColor Yellow }
Write-Host ""

# Fetch items from configured feeds
$allItems = @()
foreach ($feed in $config.feeds) {
    if ($feedUrls.ContainsKey($feed)) {
        $items = Get-RoadmapItems -FeedUrl $feedUrls[$feed] -FeedName $feed
        $allItems += $items
    } else {
        Write-Warning "Unknown feed: $feed"
    }
}

Write-Host "Total items fetched: $($allItems.Count)" -ForegroundColor Cyan

# Filter
$filtered = @($allItems | Where-Object { Test-ItemMatchesFilter -Item $_ -Config $config -DaysBack $DaysBack })
Write-Host "Items after filtering: $($filtered.Count)" -ForegroundColor Cyan
Write-Host ""

if ($filtered.Count -eq 0) {
    Write-Host "No new roadmap items match your filters." -ForegroundColor Yellow
    exit 0
}

# Group and display
$grouped = $filtered | Group-Object -Property Status
foreach ($group in $grouped) {
    Write-Host "--- $($group.Name) ($($group.Count) items) ---" -ForegroundColor Green
    foreach ($item in ($group.Group | Sort-Object PubDate -Descending)) {
        $products = $item.Products -join ", "
        Write-Host "  [$($item.Feed.ToUpper())] $($item.Title)" -ForegroundColor White
        Write-Host "    Products: $products | Published: $($item.PubDate.ToString('yyyy-MM-dd')) | ID: $($item.Guid)"
    }
    Write-Host ""
}

# Create work items (unless dry run)
if ($DryRun) {
    Write-Host "DRY RUN complete. $($filtered.Count) items would be synced to ADO." -ForegroundColor Yellow
    exit 0
}

Write-Host "Syncing $($filtered.Count) items to Azure DevOps ($adoProject)..." -ForegroundColor Cyan
$created = 0
$skipped = 0
$failed = 0

foreach ($item in $filtered) {
    $existingId = Find-ExistingWorkItem -RoadmapGuid $item.Guid -Title $item.Title
    if ($existingId) {
        Write-Host "  SKIP: '$($item.Title)' (exists as #$existingId)" -ForegroundColor DarkGray
        $skipped++
        continue
    }

    $result = New-AdoWorkItem -Item $item
    if ($result) {
        Write-Host "  CREATED: #$($result.id) - $($item.Title)" -ForegroundColor Green
        $created++
    } else {
        $failed++
    }
}

Write-Host ""
Write-Host "=== Sync Complete ===" -ForegroundColor Cyan
Write-Host "Created: $created | Skipped (duplicates): $skipped | Failed: $failed"

#endregion
