#!/usr/bin/env bash
# setup-ado-boards.sh — Create ADO teams + area paths from roadmap-sync-config.json
#
# Each boardMapping becomes:
#   - An ADO team  (gets its own board automatically)
#   - An area path: <PROJECT>\Area\Roadmap\<board name>
#   - The team is configured to own that area path
#
# roadmap-sync-config.json is updated in-place with the resolved
# project, organization, and areaPath values for every mapping.
#
# Usage (run from repo root):
#   chmod +x setup-ado-boards.sh && ./setup-ado-boards.sh
#
# Prerequisites:
#   - Azure CLI with azure-devops extension  (az extension add --name azure-devops)
#   - jq  (brew install jq)

set -euo pipefail

# ============================================================
# CONFIGURATION
# ============================================================

ADO_ORG="https://dev.azure.com/hobbitfeetado"
ADO_PROJECT="Hobbit-Dev"
AREA_ROOT="Roadmap"        # Node to create under the project's default Area
CONFIG_FILE="roadmap-sync-config.json"

# ============================================================
# Helpers
# ============================================================

BLUE='\033[1;34m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'; NC='\033[0m'
log()  { echo -e "\n${BLUE}==> $1${NC}"; }
ok()   { echo -e "${GREEN}    ✓ $1${NC}"; }
warn() { echo -e "${YELLOW}    ⚠ $1${NC}"; }
fail() { echo -e "${RED}    ✗ $1${NC}"; exit 1; }

# ============================================================
# Preflight
# ============================================================

log "Preflight checks"

[[ -f "$CONFIG_FILE" ]] || fail "$CONFIG_FILE not found. Run from repo root."
command -v az  &>/dev/null || fail "Azure CLI not found."
command -v jq  &>/dev/null || fail "jq not found. Install with: brew install jq"

if ! az extension show --name azure-devops &>/dev/null; then
  warn "Installing azure-devops CLI extension..."
  az extension add --name azure-devops --only-show-errors
fi
ok "azure-devops extension ready"

if ! az account show &>/dev/null; then
  warn "Not logged in — launching device code login"
  az login --use-device-code
fi
ok "Logged in as: $(az account show --query 'user.name' -o tsv)"

az devops configure --defaults organization="$ADO_ORG" project="$ADO_PROJECT"
ok "Defaults set: org=$ADO_ORG  project=$ADO_PROJECT"

az devops project show --project "$ADO_PROJECT" --output none 2>/dev/null || \
  fail "Project '$ADO_PROJECT' not found in $ADO_ORG."
ok "Project '$ADO_PROJECT' found"

# ============================================================
# Step 1: Discover the real root area path
# ADO wraps areas under a hidden root node (e.g. \Hobbit-Dev\Area).
# We discover it dynamically so this script works on any project.
# ============================================================

log "Discovering project area root"

AREA_TREE=$(az boards area project list --depth 4 --output json)

# The root node's .path is the base for all area operations
ROOT_AREA_PATH=$(echo "$AREA_TREE" | jq -r '.path')
ok "Area root: $ROOT_AREA_PATH"

# ============================================================
# Step 2: Create parent Roadmap node  (e.g. \Hobbit-Dev\Area\Roadmap)
# ============================================================

log "Creating '$AREA_ROOT' area node"

ROADMAP_PATH="${ROOT_AREA_PATH}\\${AREA_ROOT}"

EXISTING_TOP=$(echo "$AREA_TREE" | jq -r '.children[]?.name // empty')

if echo "$EXISTING_TOP" | grep -qx "$AREA_ROOT"; then
  ok "'$AREA_ROOT' already exists — skipping"
else
  az boards area project create \
    --name "$AREA_ROOT" \
    --output none
  # Refresh tree after creation
  AREA_TREE=$(az boards area project list --depth 4 --output json)
  ok "Created: $ROADMAP_PATH"
fi

# ============================================================
# Step 3: Process each boardMapping
# ============================================================

BOARD_COUNT=$(jq '.boardMappings | length' "$CONFIG_FILE")
log "Processing $BOARD_COUNT board mappings from $CONFIG_FILE"

for i in $(seq 0 $(( BOARD_COUNT - 1 ))); do
  BOARD_NAME=$(jq -r ".boardMappings[$i].name" "$CONFIG_FILE")
  # ADO does not allow & in area path or team names — replace with "and"
  ADO_NAME="${BOARD_NAME//&/and}"
  BOARD_AREA_PATH="${ROADMAP_PATH}\\${ADO_NAME}"

  echo ""
  echo "  [$((i+1))/$BOARD_COUNT] $BOARD_NAME  (ADO name: '$ADO_NAME')"

  # --- Create area path ---
  EXISTING_UNDER_ROADMAP=$(echo "$AREA_TREE" | \
    jq -r --arg root "$AREA_ROOT" \
    '.children[]? | select(.name == $root) | .children[]?.name // empty')

  if echo "$EXISTING_UNDER_ROADMAP" | grep -qx "$ADO_NAME"; then
    ok "    Area path already exists"
  else
    az boards area project create \
      --name "$ADO_NAME" \
      --path "$ROADMAP_PATH" \
      --output none
    # Refresh tree so next iteration has current state
    AREA_TREE=$(az boards area project list --depth 4 --output json)
    ok "    Created area: $BOARD_AREA_PATH"
  fi

  # --- Create team ---
  EXISTING_TEAMS=$(az devops team list --output json | jq -r '.[].name')

  if echo "$EXISTING_TEAMS" | grep -qx "$ADO_NAME"; then
    ok "    Team already exists"
  else
    az devops team create \
      --name "$ADO_NAME" \
      --output none
    ok "    Created team: $ADO_NAME"
  fi

  # --- Assign area path to team ---
  az boards area team add \
    --team "$ADO_NAME" \
    --path "$BOARD_AREA_PATH" \
    --output none 2>/dev/null || warn "    Area may already be assigned to team"

  az boards area team update \
    --team "$ADO_NAME" \
    --path "$BOARD_AREA_PATH" \
    --set-as-default \
    --output none 2>/dev/null || warn "    Could not set default area (check in portal)"

  ok "    Team area configured: $BOARD_AREA_PATH"

  # --- Update roadmap-sync-config.json in-place ---
  UPDATED=$(jq \
    --arg i "$i" \
    --arg org "${ADO_ORG}/" \
    --arg project "$ADO_PROJECT" \
    --arg area "$BOARD_AREA_PATH" \
    '.boardMappings[($i|tonumber)].ado.organization = $org |
     .boardMappings[($i|tonumber)].ado.project = $project |
     .boardMappings[($i|tonumber)].ado.areaPath = $area' \
    "$CONFIG_FILE")
  echo "$UPDATED" > "$CONFIG_FILE"
  ok "    Config updated"
done

# ============================================================
# Step 4: defaultBoard — Roadmap\General
# ============================================================

log "Configuring defaultBoard (Roadmap\\General)"

DEFAULT_BOARD_NAME="General"
DEFAULT_AREA_PATH="${ROADMAP_PATH}\\${DEFAULT_BOARD_NAME}"

EXISTING_UNDER_ROADMAP=$(echo "$AREA_TREE" | \
  jq -r --arg root "$AREA_ROOT" \
  '.children[]? | select(.name == $root) | .children[]?.name // empty')

if echo "$EXISTING_UNDER_ROADMAP" | grep -qx "$DEFAULT_BOARD_NAME"; then
  ok "'$DEFAULT_BOARD_NAME' area already exists"
else
  az boards area project create \
    --name "$DEFAULT_BOARD_NAME" \
    --path "$ROADMAP_PATH" \
    --output none
  ok "Created area: $DEFAULT_AREA_PATH"
fi

UPDATED=$(jq \
  --arg org "${ADO_ORG}/" \
  --arg project "$ADO_PROJECT" \
  --arg area "$DEFAULT_AREA_PATH" \
  '.defaultBoard.ado.organization = $org |
   .defaultBoard.ado.project = $project |
   .defaultBoard.ado.areaPath = $area' \
  "$CONFIG_FILE")
echo "$UPDATED" > "$CONFIG_FILE"
ok "defaultBoard config updated"

# ============================================================
# Summary
# ============================================================

BOARD_COUNT=$(jq '.boardMappings | length' "$CONFIG_FILE")

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║              SETUP COMPLETE                               ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "  Project:  $ADO_ORG / $ADO_PROJECT"
echo "  Areas created under: $ROADMAP_PATH"
echo ""

for i in $(seq 0 $(( BOARD_COUNT - 1 ))); do
  BOARD_NAME=$(jq -r ".boardMappings[$i].name" "$CONFIG_FILE")
  echo "    ├── $BOARD_NAME"
done
echo "    └── General  (default)"

echo ""
echo "  $CONFIG_FILE updated with resolved org, project, and area paths."
echo ""
echo "  Boards: ${ADO_ORG}/${ADO_PROJECT}/_boards"
echo ""
echo "  ┌─ Next steps ────────────────────────────────────────────"
echo "  │  1. Verify boards appear at the URL above"
echo "  │  2. Commit the updated $CONFIG_FILE"
echo "  │  3. Continue with SETUP.md §5 (Foundry Agent creation)"
echo "  └─────────────────────────────────────────────────────────"
echo ""
