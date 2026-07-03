/**
 * Feature flags for IVS v1.0 scope control.
 *
 * Backend logic for these features remains intact — only the UI surface
 * is hidden in v1.0. Flip a flag to true to re-expose the corresponding
 * navigation entry / settings tab in a later minor release.
 *
 * Roadmap reference:
 *   v1.0 — current set (false)
 *   v1.1 — diagnostics: dns, network
 *   v1.2 — ecosystem: api_catalog, gitea
 *   v2.0 — enterprise: multi-machine fleet management
 */
export const features = {
  // Sidebar entries
  api_catalog: true,   // v1.0.1 — managed catalog of deployed-app APIs

  // Settings tabs
  dns_tab: false,
  network_tab: false,
  gitea_tab: false,
  enterprise_tab: false,  // v2.0: fleet management (MachineRegistry)
} as const;

export type FeatureKey = keyof typeof features;

export function isEnabled(key: FeatureKey): boolean {
  return features[key];
}
