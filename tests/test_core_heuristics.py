#!/usr/bin/env python3
"""
Unit tests for Entropy Framework core heuristics.

Tests classify_authority(), compute_swr() dedup, self_created logic,
and archetype classification thresholds. Pure-logic tests — no API
calls, no filesystem dependency.

Run:
    python -m pytest tests/test_core_heuristics.py -v
    # or without pytest:
    python tests/test_core_heuristics.py
"""

import sys
import unittest
from pathlib import Path
from collections import defaultdict

# Add tools/ to path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from analyze_archetypes import classify_archetype
from extract_jira_swr import classify_authority, compute_swr


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_ticket(key, reporter_name="PM Alice", assignee_name="Dev Bob",
                reporter_id="alice123", assignee_id="bob456",
                issue_type="Story", parent_key=None, epic_link=None):
    """Build a minimal ticket dict for testing."""
    if assignee_id is None:
        # Unassigned ticket
        self_created = None
    elif reporter_id == assignee_id and reporter_id != "":
        self_created = True
    else:
        self_created = False

    return {
        "key": key,
        "summary": f"Test ticket {key}",
        "issue_type": issue_type,
        "reporter_name": reporter_name,
        "reporter_id": reporter_id,
        "assignee_name": assignee_name,
        "assignee_id": assignee_id or "",
        "parent_key": parent_key,
        "epic_link": epic_link,
        "self_created": self_created,
    }


# ── classify_authority tests ─────────────────────────────────────────────────

class TestClassifyAuthority(unittest.TestCase):
    """Tests for the SWR authority classification heuristic."""

    def test_empty_lineage_returns_unknown(self):
        level, source, depth, details = classify_authority([])
        self.assertEqual(level, "UNKNOWN")
        self.assertIsNone(source)

    def test_sanctioned_leaf(self):
        """Reporter != Assignee on leaf → SANCTIONED."""
        ticket = make_ticket("SBT-1", reporter_id="pm1", assignee_id="dev1")
        level, source, depth, details = classify_authority([ticket])
        self.assertEqual(level, "SANCTIONED")
        self.assertEqual(source, "SBT-1")
        self.assertEqual(depth, 0)

    def test_self_created_single_ticket(self):
        """Reporter == Assignee, no parents → UNSANCTIONED."""
        ticket = make_ticket("SBT-2", reporter_id="dev1", assignee_id="dev1")
        level, source, depth, details = classify_authority([ticket])
        self.assertEqual(level, "UNSANCTIONED")
        self.assertIsNone(source)

    def test_inherited_from_parent(self):
        """Self-created leaf, but parent has external authority → INHERITED."""
        leaf = make_ticket("SBT-10", reporter_id="dev1", assignee_id="dev1",
                           parent_key="SBT-5")
        parent = make_ticket("SBT-5", reporter_id="pm1", assignee_id="dev1",
                             issue_type="Epic")
        level, source, depth, details = classify_authority([leaf, parent])
        self.assertEqual(level, "INHERITED")
        self.assertEqual(source, "SBT-5")
        self.assertEqual(depth, 1)

    def test_inherited_from_grandparent(self):
        """Authority found 2 levels up → INHERITED with depth=2."""
        leaf = make_ticket("SBT-20", reporter_id="dev1", assignee_id="dev1")
        parent = make_ticket("SBT-15", reporter_id="dev1", assignee_id="dev1")
        grandparent = make_ticket("SBT-10", reporter_id="pm1", assignee_id="dev1")
        level, source, depth, details = classify_authority([leaf, parent, grandparent])
        self.assertEqual(level, "INHERITED")
        self.assertEqual(source, "SBT-10")
        self.assertEqual(depth, 2)

    def test_full_self_created_chain(self):
        """Entire chain is self-created → UNSANCTIONED."""
        leaf = make_ticket("SBT-30", reporter_id="dev1", assignee_id="dev1")
        parent = make_ticket("SBT-25", reporter_id="dev1", assignee_id="dev1")
        level, source, depth, details = classify_authority([leaf, parent])
        self.assertEqual(level, "UNSANCTIONED")
        self.assertIsNone(source)

    def test_unassigned_leaf_falls_through_to_parent(self):
        """Unassigned leaf (self_created=None) → skip, check parent."""
        leaf = make_ticket("SBT-40", reporter_id="pm1", assignee_id=None,
                           assignee_name="unassigned")
        parent = make_ticket("SBT-35", reporter_id="pm1", assignee_id="dev1")
        level, source, depth, details = classify_authority([leaf, parent])
        self.assertEqual(level, "INHERITED")
        self.assertEqual(source, "SBT-35")

    def test_unassigned_leaf_no_parent_is_unsanctioned(self):
        """Unassigned leaf with no parents, no PR author → UNSANCTIONED."""
        leaf = make_ticket("SBT-50", reporter_id="pm1", assignee_id=None,
                           assignee_name="unassigned")
        level, source, depth, details = classify_authority([leaf])
        self.assertEqual(level, "UNSANCTIONED")

    def test_unassigned_leaf_with_sanctioned_grandparent(self):
        """Unassigned leaf → self-created parent → sanctioned grandparent → INHERITED."""
        leaf = make_ticket("SBT-60", reporter_id="dev1", assignee_id=None)
        parent = make_ticket("SBT-55", reporter_id="dev1", assignee_id="dev1")
        grandparent = make_ticket("SBT-50", reporter_id="pm1", assignee_id="dev1")
        level, source, depth, details = classify_authority([leaf, parent, grandparent])
        self.assertEqual(level, "INHERITED")
        self.assertEqual(source, "SBT-50")
        self.assertEqual(depth, 2)

    # ── PR-author-as-effective-assignee fallback ──

    def test_unassigned_story_with_pr_author_different_from_reporter(self):
        """Unassigned Story + PR author != reporter → SANCTIONED (PM created, dev worked)."""
        leaf = make_ticket("SBT-70", reporter_name="PM Alice", reporter_id="pm1",
                           assignee_id=None, assignee_name="unassigned",
                           issue_type="Story")
        level, source, depth, details = classify_authority([leaf], pr_author_name="Dev Bob")
        self.assertEqual(level, "SANCTIONED")
        self.assertEqual(source, "SBT-70")
        self.assertIn("effective assignee", details)

    def test_unassigned_story_with_pr_author_same_as_reporter(self):
        """Unassigned Story + PR author == reporter → self-created → UNSANCTIONED."""
        leaf = make_ticket("SBT-71", reporter_name="Dev Bob", reporter_id="dev1",
                           assignee_id=None, assignee_name="unassigned",
                           issue_type="Story")
        level, source, depth, details = classify_authority([leaf], pr_author_name="Dev Bob")
        self.assertEqual(level, "UNSANCTIONED")

    def test_unassigned_epic_ignores_pr_author(self):
        """Unassigned Epic + PR author → epic escapes the heuristic, falls through."""
        leaf = make_ticket("SBT-72", reporter_name="PM Alice", reporter_id="pm1",
                           assignee_id=None, assignee_name="unassigned",
                           issue_type="Epic")
        level, source, depth, details = classify_authority([leaf], pr_author_name="Dev Bob")
        # Epic is indeterminate, no parents → UNSANCTIONED (not SANCTIONED)
        self.assertEqual(level, "UNSANCTIONED")

    def test_unassigned_epic_ancestor_still_provides_authority(self):
        """Unassigned Epic in lineage with assignee-bearing ancestor still inherits."""
        leaf = make_ticket("SBT-73", reporter_id="dev1", assignee_id="dev1",
                           issue_type="Task")
        epic = make_ticket("SBT-74", reporter_id="pm1", assignee_id="dev1",
                           issue_type="Epic")
        level, source, depth, details = classify_authority([leaf, epic])
        self.assertEqual(level, "INHERITED")
        self.assertEqual(source, "SBT-74")

    def test_unassigned_story_no_pr_author_mapping_falls_through(self):
        """Unassigned Story but no pr_author_name provided → falls through to parents."""
        leaf = make_ticket("SBT-75", reporter_name="PM Alice", reporter_id="pm1",
                           assignee_id=None, issue_type="Story")
        parent = make_ticket("SBT-76", reporter_id="pm1", assignee_id="dev1",
                             issue_type="Epic")
        # No pr_author_name → can't resolve leaf, check parent
        level, source, depth, details = classify_authority([leaf, parent])
        self.assertEqual(level, "INHERITED")
        self.assertEqual(source, "SBT-76")

    def test_pr_author_comparison_is_case_insensitive(self):
        """Name comparison should be case-insensitive."""
        leaf = make_ticket("SBT-80", reporter_name="PM Alice", reporter_id="pm1",
                           assignee_id=None, issue_type="Task")
        level, _, _, _ = classify_authority([leaf], pr_author_name="pm alice")
        # Same person (case-insensitive) → self-created → UNSANCTIONED
        self.assertEqual(level, "UNSANCTIONED")


# ── compute_swr dedup tests ─────────────────────────────────────────────────

class TestComputeSwrDedup(unittest.TestCase):
    """Tests for multi-ticket PR deduplication in compute_swr."""

    def _mock_compute_swr(self, ticket_to_prs, all_prs_per_author, ticket_data):
        """
        Run compute_swr with mocked ticket loading.
        ticket_data: dict of key → ticket dict for build_lineage/load_ticket.
        """
        import extract_jira_swr as mod

        # Monkey-patch load_ticket to use our in-memory data
        original_load = mod.load_ticket
        mod.load_ticket = lambda key: ticket_data.get(key)
        try:
            per_author, classifications = compute_swr(ticket_to_prs, all_prs_per_author)
        finally:
            mod.load_ticket = original_load
        return per_author, classifications

    def test_single_pr_two_tickets_counted_once(self):
        """A PR referencing two tickets should only be counted once."""
        # Same PR appears under two different tickets
        pr_info = {"repo": "myrepo", "pr_number": 42, "author": "dev1"}
        ticket_to_prs = {
            "SBT-1": [pr_info],
            "SBT-2": [pr_info],
        }
        all_prs_per_author = {"dev1": 1}

        ticket_data = {
            "SBT-1": make_ticket("SBT-1", reporter_id="pm1", assignee_id="dev1"),
            "SBT-2": make_ticket("SBT-2", reporter_id="dev1", assignee_id="dev1"),
        }

        per_author, _ = self._mock_compute_swr(ticket_to_prs, all_prs_per_author, ticket_data)

        self.assertEqual(per_author["dev1"]["classified_prs"], 1)
        self.assertEqual(per_author["dev1"]["total_prs"], 1)
        self.assertEqual(per_author["dev1"]["no_ticket_prs"], 0)

    def test_multi_ticket_pr_takes_strongest_authority(self):
        """PR with both SANCTIONED and UNSANCTIONED tickets → counts as SANCTIONED."""
        pr_info = {"repo": "myrepo", "pr_number": 42, "author": "dev1"}
        ticket_to_prs = {
            "SBT-1": [pr_info],  # SANCTIONED (pm created)
            "SBT-2": [pr_info],  # UNSANCTIONED (self-created)
        }
        all_prs_per_author = {"dev1": 1}

        ticket_data = {
            "SBT-1": make_ticket("SBT-1", reporter_id="pm1", assignee_id="dev1"),
            "SBT-2": make_ticket("SBT-2", reporter_id="dev1", assignee_id="dev1"),
        }

        per_author, _ = self._mock_compute_swr(ticket_to_prs, all_prs_per_author, ticket_data)

        self.assertEqual(per_author["dev1"]["sanctioned_prs"], 1)
        self.assertEqual(per_author["dev1"]["unsanctioned_prs"], 0)

    def test_no_ticket_prs_gap(self):
        """PRs with no ticket reference show up in no_ticket_prs."""
        pr_info = {"repo": "myrepo", "pr_number": 42, "author": "dev1"}
        ticket_to_prs = {"SBT-1": [pr_info]}
        all_prs_per_author = {"dev1": 5}  # 5 total, only 1 has a ticket

        ticket_data = {
            "SBT-1": make_ticket("SBT-1", reporter_id="pm1", assignee_id="dev1"),
        }

        per_author, _ = self._mock_compute_swr(ticket_to_prs, all_prs_per_author, ticket_data)

        self.assertEqual(per_author["dev1"]["total_prs"], 5)
        self.assertEqual(per_author["dev1"]["classified_prs"], 1)
        self.assertEqual(per_author["dev1"]["no_ticket_prs"], 4)

    def test_swr_cannot_exceed_100_percent(self):
        """Even with multi-ticket PRs, classified_prs <= total_prs."""
        pr_info_a = {"repo": "myrepo", "pr_number": 1, "author": "dev1"}
        pr_info_b = {"repo": "myrepo", "pr_number": 2, "author": "dev1"}
        ticket_to_prs = {
            "SBT-1": [pr_info_a, pr_info_b],
            "SBT-2": [pr_info_a],  # PR 1 also references SBT-2
            "SBT-3": [pr_info_b],  # PR 2 also references SBT-3
        }
        all_prs_per_author = {"dev1": 2}

        ticket_data = {
            "SBT-1": make_ticket("SBT-1", reporter_id="pm1", assignee_id="dev1"),
            "SBT-2": make_ticket("SBT-2", reporter_id="pm1", assignee_id="dev1"),
            "SBT-3": make_ticket("SBT-3", reporter_id="pm1", assignee_id="dev1"),
        }

        per_author, _ = self._mock_compute_swr(ticket_to_prs, all_prs_per_author, ticket_data)

        self.assertEqual(per_author["dev1"]["classified_prs"], 2)
        self.assertLessEqual(per_author["dev1"]["classified_prs"],
                             per_author["dev1"]["total_prs"])


# ── classify_archetype tests ─────────────────────────────────────────────────

class TestClassifyArchetype(unittest.TestCase):
    """Tests for developer archetype classification thresholds."""

    def test_absent(self):
        self.assertEqual(classify_archetype(0, 0, 0, 0, 0, 0), "Absent")

    def test_rubber_stamp(self):
        """Reviews exist but CD=0 → Rubber Stamp."""
        self.assertEqual(classify_archetype(0, 10, 0, 0, 0, 5), "Rubber Stamp")

    def test_production_engine_high_ps_low_cs(self):
        # CD > 0 avoids the Rubber Stamp check (reviews > 0 and cd == 0)
        self.assertEqual(classify_archetype(500, 50, 0.3, 0, 100, 10),
                         "Production Engine")

    def test_system_governor(self):
        """High PS, high CS, high CD, CS > PS."""
        self.assertEqual(classify_archetype(600, 800, 0.9, 0.1, 100, 50),
                         "System Governor")

    def test_hybrid_producer_catalyst(self):
        """High PS, high CS, high CD, PS > CS."""
        result = classify_archetype(800, 600, 0.9, 0.1, 100, 50)
        self.assertIn("Hybrid", result)

    def test_high_entropy_agent(self):
        """High PS, high CS, low CD."""
        self.assertEqual(classify_archetype(600, 600, 0.2, 0.0, 100, 50),
                         "High-Entropy Agent")

    def test_selective_catalyst(self):
        """Low PS, high CS, moderate CD."""
        self.assertEqual(classify_archetype(50, 300, 0.5, 0.1, 10, 30),
                         "Selective Catalyst")

    def test_depleting_catalyst(self):
        """Very low commits, high CS, high CD."""
        self.assertEqual(classify_archetype(5, 300, 0.9, 0.1, 5, 30),
                         "Depleting Catalyst")

    def test_fresh_eyes_catalyst(self):
        """Low everything but has reviews with moderate CD."""
        self.assertEqual(classify_archetype(10, 10, 0.5, 0.0, 2, 5),
                         "Fresh-Eyes Catalyst")


# ── self_created logic tests ─────────────────────────────────────────────────

class TestSelfCreatedLogic(unittest.TestCase):
    """Tests for the self_created three-way logic in fetch_ticket output."""

    def _compute_self_created(self, reporter_id, assignee_id):
        """Replicate the self_created logic from fetch_ticket."""
        if not assignee_id:
            return None
        return reporter_id == assignee_id and reporter_id != ""

    def test_different_users(self):
        self.assertFalse(self._compute_self_created("alice", "bob"))

    def test_same_user(self):
        self.assertTrue(self._compute_self_created("alice", "alice"))

    def test_both_empty(self):
        """Both empty → assignee empty → None (indeterminate)."""
        self.assertIsNone(self._compute_self_created("", ""))

    def test_reporter_present_assignee_empty(self):
        """PM created, not yet assigned → None (indeterminate)."""
        self.assertIsNone(self._compute_self_created("pm_alice", ""))

    def test_reporter_empty_assignee_present(self):
        """Edge case: no reporter but has assignee → False (not equal)."""
        self.assertFalse(self._compute_self_created("", "bob"))


if __name__ == "__main__":
    unittest.main()
