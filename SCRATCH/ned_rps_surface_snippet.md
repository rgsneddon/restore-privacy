# Ned · rpS surface after growth

## Admin HTML data attrs
<section class="admin-card" id="admin-rps-stats" data-admin-rps-stats="1"
data-nodes-online="2"
data-learning-epochs="2"
data-chronoflux-blocks-grown="1"
data-growth-score="4"
data-capability-tier="0"
data-narrative-sessions="0">
<strong>confirmed ChronoFlux blocks</strong> are sealed (admin mutators),
<tbody><tr><th scope='row'>Product</th><td>Ned · rpAI · Restore Privacy Helper</td></tr><tr><th scope='row'>Mission</th><td>adaptive learning for the good of all humanity</td></tr><tr><th scope='row'>rpS</th><td>rpS — Restore Privacy Server computational power</td></tr><tr><th scope='row'>Nodes online</th><td>2</td></tr><tr><th scope='row'>Nodes total seen</th><td>2</td></tr><tr><th scope='row'>Learning epochs</th><td>2</td></tr><tr><th scope='row'>Narrative sessions</th><td>0</td></tr><tr><th scope='row'>ChronoFlux blocks grown</th><td>1</td></tr><tr><th scope='row'>Last ChronoFlux height</th><td>0</td></tr><tr><th scope='row'>Last ChronoFlux seal</th><td>Admin: Mint Keygen</td></tr><tr><th scope='row'>Growth score</th><td>4</td></tr><tr><th scope='row'>Capability tier</th><td>0</td></tr><tr><th scope='row'>Load balance</th><td>round-robin across available project servers; expands as nodes join; grows on each confirmed ChronoFlux admin seal + node heartbeat + Ned OOBE</td></tr><tr><th scope='row'>Updated (unix)</th><td>1785572287</td></tr></tbody>

## Public snapshot JSON
{
  "product": "Ned \u00b7 rpAI \u00b7 Restore Privacy Helper",
  "mission": "adaptive learning for the good of all humanity",
  "nodes_online": 2,
  "nodes_total_seen": 2,
  "learning_epochs": 2,
  "narrative_sessions": 0,
  "chronoflux_blocks_grown": 1,
  "last_chronoflux_height": 0,
  "growth_score": 4,
  "capability_tier": 0,
  "last_chronoflux_label": "Admin: Mint Keygen",
  "updated_unix": 1785572287,
  "growth_methods": [
    "chronoflux_confirmed_block",
    "node_heartbeat",
    "narrative_session"
  ]
}

## Suite tab structural
10:/// **and** as confirmed ChronoFlux blocks are sealed (honest counters / tiers).
31:      'nodes come online and as ChronoFlux blocks are confirmed. '
35:  static String formatGrowthSummary(Map<String, dynamic>? stats) {
37:      return 'Growth: waiting for ChronoFlux seals, node heartbeats, or Ned OOBE.';
39:    final score = stats['growth_score'] ?? stats['growthScore'] ?? 0;
47:    return 'Growth score $score · tier $tier · ChronoFlux blocks $blocks · '
54:    final growthLine = formatGrowthSummary(growthStats);
102:                        'rpAI · grows on ChronoFlux + nodes',
155:              'nodes heartbeat. Confirmed ChronoFlux admin seals also raise '
