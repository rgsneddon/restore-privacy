/**
 * Perccent PERC mine pool entry (BeamHash III).
 * Listens on 1466 only. Ports 1690/1974 stay on Beam.
 * Shares are method=solution with output; accepted work credits PERC.
 */
import { startPercMinePool } from './mineperc_server.js';

export { startPercMinePool };

if (import.meta.url === `file://${process.argv[1]}`) {
  startPercMinePool();
}
