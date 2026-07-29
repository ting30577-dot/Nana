"""Full deterministic Relation Registry invariant tests."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from nana_sidecar.contracts.domain import RelationType
from nana_sidecar.contracts.relations import (
    RELATION_REGISTRY,
    RelationContractError,
    RelationEndpoint,
    RelationValidationContext,
    validate_minimum_cardinality,
    validate_relation,
)


NOW = datetime(2026, 7, 29, tzinfo=timezone.utc)


def endpoint(
    object_type: str,
    *,
    project_id=None,
    inquiry_id=None,
    **kwargs,
) -> RelationEndpoint:
    return RelationEndpoint(
        object_type=object_type,
        object_id=kwargs.pop("object_id", uuid4()),
        project_id=project_id or uuid4(),
        inquiry_id=inquiry_id,
        **kwargs,
    )


class RelationRegistryTests(unittest.TestCase):
    def test_registry_matches_relation_enum_and_has_deletion_contracts(self) -> None:
        self.assertEqual(
            set(RELATION_REGISTRY),
            {item.value for item in RelationType},
        )
        self.assertTrue(
            all(rule.deletion_behavior for rule in RELATION_REGISTRY.values())
        )

    def test_evidence_relation_requires_direction_and_inquiry(self) -> None:
        inquiry_id = uuid4()
        project_id = uuid4()
        evidence = endpoint(
            "evidence",
            project_id=project_id,
            inquiry_id=inquiry_id,
            direction="opposes",
        )
        claim = endpoint(
            "claim",
            project_id=project_id,
            inquiry_id=inquiry_id,
        )
        with self.assertRaises(RelationContractError) as captured:
            validate_relation(
                RelationType.EVIDENCE_SUPPORTS_CLAIM.value,
                evidence,
                claim,
            )
        self.assertEqual(captured.exception.code, "E_REL_EVIDENCE_DIRECTION")

        other_claim = endpoint(
            "claim",
            project_id=project_id,
            inquiry_id=uuid4(),
        )
        with self.assertRaisesRegex(RelationContractError, "Inquiry"):
            validate_relation(
                RelationType.EVIDENCE_OPPOSES_CLAIM.value,
                evidence,
                other_claim,
            )

    def test_resource_relation_checks_locator_resource_and_cardinality(self) -> None:
        resource = endpoint("resource")
        evidence = endpoint("evidence", resource_id=uuid4())
        with self.assertRaises(RelationContractError) as captured:
            validate_relation(
                RelationType.RESOURCE_CONTAINS_EVIDENCE.value,
                resource,
                evidence,
            )
        self.assertEqual(captured.exception.code, "E_REL_RESOURCE_MISMATCH")

        matching = replace(evidence, resource_id=resource.object_id)
        with self.assertRaisesRegex(RelationContractError, "cardinality"):
            validate_relation(
                RelationType.RESOURCE_CONTAINS_EVIDENCE.value,
                resource,
                matching,
                RelationValidationContext(incoming_count=1),
            )

    def test_artifact_lineage_allows_cross_project_but_rejects_cycle(self) -> None:
        source = endpoint("artifact", project_id=uuid4())
        target = endpoint("artifact", project_id=uuid4())
        validate_relation(
            RelationType.ARTIFACT_DERIVED_FROM_ARTIFACT.value,
            source,
            target,
        )
        with self.assertRaisesRegex(RelationContractError, "cycle"):
            validate_relation(
                RelationType.ARTIFACT_DERIVED_FROM_ARTIFACT.value,
                source,
                target,
                RelationValidationContext(
                    existing_edges=frozenset(
                        {(target.object_id, source.object_id)}
                    )
                ),
            )

    def test_retry_requires_newer_same_project_run(self) -> None:
        project_id = uuid4()
        old = endpoint("run", project_id=project_id, created_at=NOW)
        new = endpoint(
            "run",
            project_id=project_id,
            created_at=NOW + timedelta(seconds=1),
        )
        validate_relation(RelationType.RUN_RETRY_OF_RUN.value, new, old)

        with self.assertRaisesRegex(RelationContractError, "newer"):
            validate_relation(RelationType.RUN_RETRY_OF_RUN.value, old, new)
        with self.assertRaisesRegex(RelationContractError, "cross-project"):
            validate_relation(
                RelationType.RUN_RETRY_OF_RUN.value,
                endpoint("run", created_at=NOW + timedelta(seconds=2)),
                old,
            )

    def test_supersede_requires_same_type_newer_revision_and_time(self) -> None:
        project_id = uuid4()
        old = endpoint(
            "finding",
            project_id=project_id,
            revision=1,
            created_at=NOW,
        )
        new = endpoint(
            "finding",
            project_id=project_id,
            revision=2,
            created_at=NOW + timedelta(seconds=1),
        )
        validate_relation(
            RelationType.OBJECT_SUPERSEDES_OBJECT.value,
            new,
            old,
        )
        wrong_revision = endpoint(
            "finding",
            project_id=project_id,
            revision=1,
            created_at=NOW + timedelta(seconds=2),
        )
        with self.assertRaisesRegex(RelationContractError, "revision"):
            validate_relation(
                RelationType.OBJECT_SUPERSEDES_OBJECT.value,
                wrong_revision,
                old,
            )

    def test_producer_is_immutable(self) -> None:
        run = endpoint("run")
        artifact = endpoint("artifact", producer_run_id=uuid4())
        with self.assertRaises(RelationContractError) as captured:
            validate_relation(
                RelationType.RUN_PRODUCES_ARTIFACT.value,
                run,
                artifact,
            )
        self.assertEqual(captured.exception.code, "E_REL_PRODUCER_EXISTS")

    def test_finding_producer_must_be_a_terminal_run(self) -> None:
        inquiry_id = uuid4()
        project_id = uuid4()
        running = endpoint(
            "run",
            project_id=project_id,
            inquiry_id=inquiry_id,
            state="running",
        )
        finding = endpoint(
            "finding",
            project_id=project_id,
            inquiry_id=inquiry_id,
        )
        with self.assertRaisesRegex(RelationContractError, "terminal Run"):
            validate_relation(
                RelationType.RUN_PRODUCES_FINDING.value,
                running,
                finding,
            )

        terminal = replace(running, state="succeeded")
        validate_relation(
            RelationType.RUN_PRODUCES_FINDING.value,
            terminal,
            finding,
        )

    def test_object_minimum_cardinalities_are_explicit(self) -> None:
        with self.assertRaises(RelationContractError) as finding_error:
            validate_minimum_cardinality("finding", state="draft")
        self.assertEqual(finding_error.exception.code, "E_REL_FINDING_EMPTY")
        validate_minimum_cardinality(
            "finding",
            state="draft",
            evidence_count=1,
        )

        with self.assertRaises(RelationContractError) as decision_error:
            validate_minimum_cardinality("decision", state="confirmed")
        self.assertEqual(decision_error.exception.code, "E_REL_DECISION_EMPTY")
        validate_minimum_cardinality(
            "decision",
            state="confirmed",
            finding_count=1,
        )

    def test_unknown_relation_is_rejected(self) -> None:
        with self.assertRaises(RelationContractError) as captured:
            validate_relation("related_to", endpoint("resource"), endpoint("claim"))
        self.assertEqual(captured.exception.code, "E_REL_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
