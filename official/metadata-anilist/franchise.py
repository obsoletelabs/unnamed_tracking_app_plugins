"""Bounded franchise graph traversal owned by the AniList provider."""
from __future__ import annotations

from itertools import pairwise
from typing import Any

from sdk.metadata_provider import ProviderFailure, ProviderHttp
from relations import RELATION_LABELS, collect_branches, node_to_dict, topological_order

AniListError = ProviderFailure

_RELATIONS_QUERY = """
query ($search: String) {
  Media(search: $search, type: ANIME) {
    id
    title {
      romaji
      english
    }
    format
    episodes
    startDate {
      year
    }
    coverImage {
      extraLarge
      large
    }
    relations {
      edges {
        relationType(version: 2)
        node {
          id
          title {
            romaji
            english
          }
          format
          episodes
          startDate {
            year
          }
          coverImage {
            extraLarge
            large
          }
        }
      }
    }
    recommendations(sort: RATING_DESC, perPage: 10) {
      nodes {
        mediaRecommendation {
          id
          title {
            romaji
            english
          }
          format
          episodes
          startDate {
            year
          }
          coverImage {
            extraLarge
            large
          }
        }
      }
    }
  }
}
"""
# Same shape as _RELATIONS_QUERY but looked up by AniList's own id rather
# than a text search — used while walking the prequel/sequel chain, where
# every step after the first already has a real id to follow instead of
# a title to (re-)search for.
_RELATIONS_BY_ID_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title {
      romaji
      english
    }
    format
    episodes
    startDate {
      year
    }
    coverImage {
      extraLarge
      large
    }
    relations {
      edges {
        relationType(version: 2)
        node {
          id
          title {
            romaji
            english
          }
          format
          episodes
          startDate {
            year
          }
          coverImage {
            extraLarge
            large
          }
        }
      }
    }
    recommendations(sort: RATING_DESC, perPage: 10) {
      nodes {
        mediaRecommendation {
          id
          title {
            romaji
            english
          }
          format
          episodes
          startDate {
            year
          }
          coverImage {
            extraLarge
            large
          }
        }
      }
    }
  }
}
"""

# How far the chain walk follows PREQUEL/SEQUEL edges in each direction,
# and how many off-chain relations (adaptation, side story, source
# manga/novel, etc.) get surfaced as branches — generous enough for a
# real franchise's full run without risking a runaway request chain.
_MAX_CHAIN_HOPS = 8
_CHAIN_RELATION_TYPES = {"PREQUEL", "SEQUEL"}

# _expand_branch_chains checks at most this many top-level branches for a
# hidden prequel/sequel of their own — each check is a real extra AniList
# request, so this bounds an uncached relations fetch to a handful of
# extra round trips instead of one per branch on a franchise with a lot
# of them.
_MAX_BRANCH_CHAIN_EXPANSIONS = 4

# A movie/OVA/special is reached from the franchise root, not the other
# way round: opening the page of "Gurren Lagann The Movie" used to build
# the graph around that one movie, so it only ever showed its own parent
# and sequel instead of the whole franchise. Entries of these formats
# hop up to their parent TV series first, and the graph is built from
# there with the entry you opened marked as current.
_SHORT_FORMATS = {"MOVIE", "OVA", "ONA", "SPECIAL", "MUSIC"}
_ROOT_FORMATS = {"TV", "TV_SHORT"}
_ROOT_RELATION_TYPES = ("PARENT", "ALTERNATIVE", "SIDE_STORY", "SPIN_OFF")

# Bumped whenever the shape/coverage of the cached payload changes, so
# results cached by an older layout are refetched instead of served stale.
RELATIONS_CACHE_VERSION = 2


class FranchiseGraph:
    def __init__(self, work):
        self.http = ProviderHttp(work, "anilist", min_gap=0.7)

    def _post_graphql(self, query, variables):
        result = self.http("https://graphql.anilist.co", method="POST",
                           body={"query": query, "variables": variables})
        if result.get("errors"):
            raise ProviderFailure("unavailable")
        return result

    def _fetch_relations_node(
        self, *, media_id: int | None = None, search: str | None = None
    ) -> dict[str, Any] | None:
        """One request's worth of a single Media node: its own id/title
        plus its direct relations edges and recommendations — the unit
        the chain walk in `relations_chain_and_branches` is built from."""
        variables: dict[str, Any]
        if media_id is not None:
            query, variables = _RELATIONS_BY_ID_QUERY, {"id": media_id}
        else:
            query, variables = _RELATIONS_QUERY, {"search": search}
        payload = self._post_graphql(query, variables)
        return (payload.get("data") or {}).get("Media")

    def _walk_chain(
        self, nodes: dict[int, dict[str, Any]], chain_ids: list[int], anchor_id: int
    ) -> None:
        """Extends `chain_ids`/`nodes` in place, following PREQUEL edges
        backward and SEQUEL edges forward from the anchor, up to
        `_MAX_CHAIN_HOPS` each way, guarded against cycles."""

        def _walk_one_direction(relation_type: str, prepend: bool) -> None:
            current_id = anchor_id
            for _ in range(_MAX_CHAIN_HOPS):
                edges = (nodes[current_id].get("relations") or {}).get("edges") or []
                edge = next((e for e in edges if e.get("relationType") == relation_type), None)
                if not edge or not edge.get("node"):
                    break
                next_id = edge["node"]["id"]
                if next_id in nodes:
                    break  # cycle guard — a franchise's edges can loop back
                try:
                    next_node = self._fetch_relations_node(media_id=next_id)
                except AniListError:
                    break  # a flaky/missing hop ends the walk, not the whole tab
                if not next_node:
                    break
                nodes[next_id] = next_node
                if prepend:
                    chain_ids.insert(0, next_id)
                else:
                    chain_ids.append(next_id)
                current_id = next_id

        _walk_one_direction("PREQUEL", prepend=True)
        _walk_one_direction("SEQUEL", prepend=False)

    def relations_chain_and_branches(
        self, title: str, anilist_id: str | None = None
    ) -> dict[str, Any]:
        """The full prequel/sequel chain this entry belongs to — walked
        via PREQUEL/SEQUEL edges in both directions, not just the anchor's
        own direct relations — plus every other relation type (adaptation,
        side story, source manga/novel, etc.)
        attached to whichever chain entry it's actually connected to.
        A season otherwise only ever lists its immediate neighbor, which
        reads as missing entries for any franchise 3+ seasons deep."""
        opened = self._fetch_relations_node(
            media_id=int(anilist_id) if anilist_id else None,
            search=None if anilist_id else title,
        )
        if not opened:
            return {
                "chain": [],
                "branches": [],
                "recommendations": [],
                "version": RELATIONS_CACHE_VERSION,
            }
        current_id = opened["id"]
        anchor = self._find_franchise_root(opened) or opened

        nodes: dict[int, dict[str, Any]] = {anchor["id"]: anchor}
        chain_ids: list[int] = [anchor["id"]]
        self._walk_chain(nodes, chain_ids, anchor["id"])

        chain = [
            {**node_to_dict(nodes[node_id]), "is_current": node_id == current_id}
            for node_id in chain_ids
        ]
        recommendations = [
            node_to_dict(rec["mediaRecommendation"])
            for rec in (anchor.get("recommendations") or {}).get("nodes") or []
            if rec.get("mediaRecommendation")
        ]

        branches = self._order_related_branches(collect_branches(nodes, anchor["id"], chain_ids))
        seen_ids = set(chain_ids) | {b["id"] for b in branches}
        branches.extend(self._expand_branch_chains(branches, seen_ids))
        for b in branches:
            b["is_current"] = b["id"] == current_id
        if current_id not in seen_ids and opened["id"] != anchor["id"]:
            # reached the root but the entry itself sits deeper than the
            # graph looks (a sequel of a sequel of a movie): still show it
            branches.append(
                {
                    "anchor_id": anchor["id"],
                    "anchor_kind": "show",
                    "relation_label": "Related",
                    "is_current": True,
                    **node_to_dict(opened),
                }
            )

        return {
            "chain": chain,
            "branches": branches,
            "recommendations": recommendations,
            "version": RELATIONS_CACHE_VERSION,
        }

    def _find_franchise_root(self, opened: dict[str, Any]) -> dict[str, Any] | None:
        """For a movie/OVA/special, the parent TV series it hangs off (one
        hop, which is all AniList's PARENT/ALTERNATIVE links need), fetched
        with its own relations. None when the entry is already a series,
        has no such link, or the parent can't be fetched."""
        if (opened.get("format") or "").upper() not in _SHORT_FORMATS:
            return None
        edges = (opened.get("relations") or {}).get("edges") or []
        for wanted in _ROOT_RELATION_TYPES:
            for edge in edges:
                node = edge.get("node")
                if edge.get("relationType") != wanted or not node:
                    continue
                if (node.get("format") or "").upper() not in _ROOT_FORMATS:
                    continue
                try:
                    return self._fetch_relations_node(media_id=node["id"])
                except AniListError:
                    return None
        return None

    def _expand_branch_chains(
        self, branches: list[dict[str, Any]], seen_ids: set[int]
    ) -> list[dict[str, Any]]:
        """A top-level branch can have its own prequel/sequel that's invisible from the anchor's
        own relations — e.g. Bleach's "BURN THE WITCH" ONA has its own prequel special ("BURN
        THE WITCH #0.8") that's only a relation of the ONA itself, one hop past what
        `collect_branches` ever looks at (the anchor's direct relations only). One extra fetch
        per still-top-level branch, pulling in any PREQUEL/SEQUEL neighbor not already known and
        nesting it under that branch (`anchor_kind: "branch"`) — the same nested-branch shape
        `_order_related_branches` already produces for a duology it detects. Single hop only
        (not a full walk), restricted to short-form formats that actually tend to have their own
        mini-chain (OVA/ONA/Special/One Shot — a movie or source manga essentially never does),
        and capped to a handful of extra fetches total — this is a real AniList request per
        branch checked, and a franchise with a dozen+ branches would otherwise turn one
        relations fetch into a dozen+ more, which is a bad trade for a detail few branches
        actually have."""
        candidates = [
            b
            for b in branches
            if b["anchor_kind"] == "show"
            and (b.get("format") or "").lower() in {"ova", "ona", "special", "one shot"}
        ]
        extra: list[dict[str, Any]] = []
        checked = 0
        for branch in candidates:
            if checked >= _MAX_BRANCH_CHAIN_EXPANSIONS:
                break
            checked += 1
            try:
                node = self._fetch_relations_node(media_id=branch["id"])
            except AniListError:
                continue
            if not node:
                continue
            for edge in (node.get("relations") or {}).get("edges") or []:
                rtype = edge.get("relationType")
                target = edge.get("node")
                if rtype not in _CHAIN_RELATION_TYPES or not target:
                    continue
                target_id = target["id"]
                if target_id in seen_ids:
                    continue
                seen_ids.add(target_id)
                extra.append(
                    {
                        "anchor_id": branch["id"],
                        "anchor_kind": "branch",
                        "relation_label": RELATION_LABELS.get(rtype, "Related"),
                        **node_to_dict(target),
                    }
                )
        return extra

    def _fetch_group_prequel_pointers(
        self, group: list[dict[str, Any]], ids: set[int]
    ) -> dict[int, int]:
        """Fetches each group member's own relations and returns
        {member_id: its_prequel_id} restricted to prequels that are
        themselves in the group (an outside prequel isn't useful for
        ordering the group)."""
        prequel_of: dict[int, int] = {}
        for b in group:
            try:
                node = self._fetch_relations_node(media_id=b["id"])
            except AniListError:
                continue  # one flaky/missing member shouldn't sink the whole tab
            if not node:
                continue
            for edge in (node.get("relations") or {}).get("edges") or []:
                if edge.get("relationType") != "PREQUEL":
                    continue
                target = (edge.get("node") or {}).get("id")
                if isinstance(target, int) and target in ids:
                    prequel_of[b["id"]] = target
        return prequel_of

    def _order_related_branches(self, branches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """A branch group sharing the same anchor and relation label —
        e.g. a two-part movie duology, both tagged ALTERNATIVE to the
        parent show rather than SEQUEL/PREQUEL to it — can still be
        chronologically ordered via their own mutual PREQUEL edges.
        Fetches each 2+-member group once to find that order; every
        member after the first is then reparented onto its immediate
        predecessor (anchor_kind "branch") instead of the show, and
        labeled "Sequel" — a real edge between the siblings themselves,
        matching how the source actually relates them, rather than two
        independent spokes off the show that just happen to sit in the
        right order."""
        groups: dict[tuple[int, str], list[int]] = {}
        for i, b in enumerate(branches):
            groups.setdefault((b["anchor_id"], b["relation_label"]), []).append(i)

        for positions in groups.values():
            # A real duology/trilogy is 2-4 members; a large group sharing
            # a label (e.g. two dozen movies/specials all loosely tagged
            # "Sequel" to the main show, which AniList uses as a catch-all
            # far more often than a genuine narrative chain) is a shared
            # bucket, not a chain — reparenting all of them nose-to-tail
            # would turn 24 independent branches into one 24-deep nested
            # chain the graph has no legible way to draw, and the ids
            # inside it were never meant to represent "watch this right
            # after that" the way a real duology's mutual PREQUEL edges do.
            if not 2 <= len(positions) <= 4:
                continue
            group = [branches[i] for i in positions]
            ids = {b["id"] for b in group}
            prequel_of = self._fetch_group_prequel_pointers(group, ids)
            order = topological_order(ids, prequel_of)
            if order is None:
                continue  # couldn't fully resolve — leave original order
            by_id = {b["id"]: b for b in group}
            for slot, branch_id in zip(sorted(positions), order, strict=True):
                branches[slot] = by_id[branch_id]
            for prev_id, branch_id in pairwise(order):
                child = by_id[branch_id]
                child["anchor_id"] = prev_id
                child["anchor_kind"] = "branch"
                child["relation_label"] = "Sequel"
        return branches
