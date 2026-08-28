/* Deliberate breakage for a CI proof -- this branch is never merged.
 *
 * A web-only module reached through require(). tsc does not check require()
 * paths, and the web bundle resolves this file, so both of those gates stay
 * green. Android and iOS have no such file and cannot resolve it.
 */
export const proofPlatform = "web-only module";
