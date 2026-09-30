"""Runtime identity for Grok Bot ticks. Import after common; do not commit into published records as Claude."""
import common
common.CONFIG['contributor_name'] = 'Grok AI'
common.CONFIG['created_by'] = 'grok-job-search'
# Prefer env TRACKER_CODE; keep code_file fallback on this box
common.CONFIG['code_file'] = '/workspace/repos/.secrets/job-tracker-code'
