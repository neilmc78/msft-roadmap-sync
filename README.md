# Microsoft Roadmap Sync

Automatically fetches Microsoft Azure and M365 roadmap updates from official RSS feeds, filters them by product and status, and creates Azure DevOps work items for new items.

## How It Works

1. **Scheduled pipeline** runs daily (Mon–Fri at 07:00 UTC)
2. **PowerShell script** fetches the RSS feeds
3. **Filters** items by products, statuses, and excluded types defined in `roadmap-filter.json`
4. **Checks for duplicates** in Azure DevOps using a `RoadmapId:<guid>` tag
5. **Creates work items** for new items that pass the filters

## Setup

### 1. Configure your filters

Edit [`roadmap-filter.json`](roadmap-filter.json):

```json
{
  "feeds": ["azure", "m365"],
  "products": [
    "Microsoft Teams",
    "Outlook",
    "Microsoft Purview"
  ],
  "statuses": ["In preview", "In development"],
  "excludeTypes": ["Retirements"],
  "ado": {
    "project": "YourProjectName",
    "workItemType": "Feature"
  }
}
```

| Field | Description |
|---|---|
| `feeds` | Which feeds to check: `azure`, `m365`, or both |
| `products` | Only include items matching these products. Empty array = all products |
| `statuses` | Only include items with these statuses: `Launched`, `In preview`, `In development`, `In review`, `Rolling out` |
| `excludeTypes` | Exclude items of these types: `Features`, `Retirements`, `Compliance`, `Regions & Datacenters`, `SDK and Tools`, etc. |
| `ado.project` | Your Azure DevOps project name |
| `ado.workItemType` | Work item type to create (e.g. `Feature`, `User Story`, `Product Backlog Item`) |

### 2. Import the pipeline in Azure DevOps

1. Go to **Pipelines > New Pipeline**
2. Select your repo (Azure Repos Git or GitHub)
3. Choose **Existing Azure Pipelines YAML file**
4. Select `/azure-pipelines.yml`
5. Save and run

### 3. Grant pipeline permissions

The pipeline uses `System.AccessToken` to create work items. Ensure:

- **Project Settings > Pipelines > Settings** — the build service account has permission to create work items
- Navigate to **Project Settings > Permissions** and grant the **Project Collection Build Service** account the **Edit work items in this node** permission on the relevant area path

### 4. Set your ADO project name

Update `ado.project` in `roadmap-filter.json` to your target project name before the first run.

## Running Manually

### From the pipeline

Run the pipeline manually from Azure DevOps. Use the **Dry run** checkbox to preview what would be created without actually creating work items.

### Locally

```powershell
# Dry run — see what matches without creating work items
./Sync-RoadmapItems.ps1 -DryRun -DaysBack 7

# Full run with explicit org and PAT
./Sync-RoadmapItems.ps1 `
  -Organization "https://dev.azure.com/myorg" `
  -Pat "your-pat-here" `
  -DaysBack 7
```

## Work Item Format

Each created work item includes:

- **Title**: Cleaned roadmap item title (without status prefix)
- **Description**: Source feed, status, published date, products, link to roadmap page, and full description
- **Tags**: `Roadmap`, `RoadmapId:<guid>`, feed name, status, and product names

The `RoadmapId:<guid>` tag is used for duplicate detection on subsequent runs.

## Available Products

### Azure Feed
`Azure Kubernetes Service (AKS)`, `Azure SQL Database`, `Azure Cosmos DB`, `Azure Monitor`, `Azure Functions`, `Azure Databricks`, `Azure Storage`, `Azure Networking`, and many more.

### M365 Feed
`Microsoft Teams`, `Outlook`, `SharePoint`, `OneDrive`, `Excel`, `Word`, `PowerPoint`, `Microsoft Purview`, `Microsoft Intune`, `Microsoft Viva`, `Microsoft Copilot (Microsoft 365)`, `Microsoft Entra`, `Microsoft Edge`, `Planner`, `Exchange`, and more.
