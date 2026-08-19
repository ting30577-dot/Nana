import type { components } from "./generated/api";

export type Handshake = components["schemas"]["RuntimeHandshakeResponse"];
export type Project = components["schemas"]["Project"];
export type Inquiry = components["schemas"]["Inquiry"];
export type Plan = components["schemas"]["Plan"];
export type Run = components["schemas"]["Run"];
export type Action = components["schemas"]["Action"];
export type Event = components["schemas"]["Event"];
export type Artifact = components["schemas"]["Artifact"];
export type ArtifactStagedEvent =
  components["schemas"]["ArtifactStagedEvent"];
export type ArtifactCommittedEvent =
  components["schemas"]["ArtifactCommittedEvent"];
export type ArtifactReconciledEvent =
  components["schemas"]["ArtifactReconciledEvent"];
export type ArtifactLifecycleEvent =
  | ArtifactStagedEvent
  | ArtifactCommittedEvent
  | ArtifactReconciledEvent;
export type Resource = components["schemas"]["Resource"];
export type Locator = components["schemas"]["Locator"];
export type Evidence = components["schemas"]["Evidence"];
export type Finding = components["schemas"]["Finding"];
