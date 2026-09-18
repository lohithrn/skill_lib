#!/usr/bin/env python3
"""Role assignment and edge legality — the doctrine, expressed as predicates over paths.

`references/doctrine.md` §9 states the layer rule in prose:

    Layer n DECLARES conflicts. Layer n+1 — a SUBFOLDER of n — RESOLVES them.
    Edges point down (into subfolders) and inward (toward utils). Never sideways between
    sibling resolvers. Never up from a resolver to its caller.

This file is that paragraph as code, so `legal` on an edge is COMPUTED and never guessed. The
one upward edge the doctrine permits is a resolver reaching the port it implements: the port
lives with its caller in the declaring layer, so implementing it necessarily points up.
"""
from __future__ import annotations

import posixpath
import re

# Role is decided in this order; the first match wins. Order encodes precedence, not importance:
# a test that also looks like a resolver is a test, and a util that also looks like a port is a util.
TEST_MARKS = ("test", "tests", "spec", "specs", "__tests__", "testdata", "fixtures")
ROOT_MARKS = ("config_dependency_injection", "composition_root", "compositionroot",
              "di_container", "dicontainer", "wire_gen", "wire", "bootstrap", "main", "__main__")
UTIL_DIRS = ("utils", "util", "utilities", "common", "commons", "shared", "helpers", "helper",
             "lib", "core", "misc")
ADAPTER_DIRS = ("adapters", "adapter", "infrastructure", "infra", "io", "clients", "client",
                "gateways", "gateway", "repositories", "repository", "persistence", "transport")
PORT_MARKS = ("_port", "_policy", "_strategy", "_interface", "_protocol", "_abc", "_contract")
REGISTRY_MARKS = ("registry", "__init__", "index", "mod")
CONTEXT_MARKS = ("_context", "context", "_request", "_command")


def parts(path: str) -> list[str]:
    return [p for p in posixpath.normpath(path).split("/") if p and p != "."]


def depth(path: str) -> int:
    """Folder depth of a file, which IS its layer: the folder tree is the graph (doctrine §9)."""
    return len(parts(directory(path)))


def base_name(path: str) -> str:
    return posixpath.splitext(posixpath.basename(path))[0].lower()


# What an Absent resolver is called, in any of the four first-class languages' conventions.
ABSENT_MARKS = ("absent", "null", "noop", "none", "missing")


def name_words(path: str) -> set[str]:
    """The words in a file's name, from camelCase and snake_case alike: `NoopLogger` -> {noop,
    logger}, `absent_price_feed` -> {absent, price, feed}.

    Case is split BEFORE it is folded, because folding first destroys the only word boundary
    camelCase has — which is why this does not go through `base_name`.
    """
    stem = posixpath.splitext(posixpath.basename(path))[0]
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", stem)
    return {word for word in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if word}


def is_absent_resolver(path: str) -> bool:
    """Does this resolver stand in for "no answer at all"?

    Matched on WHOLE WORDS, never as a substring: `none` sits inside `nonexistent_price`, and
    crediting that file as a port's Absent resolver would let `ports_without_absent` — a hard cap —
    be satisfied by a file that answers nothing. A cap that can be satisfied by a coincidence of
    spelling is not being enforced.
    """
    return bool(name_words(path) & set(ABSENT_MARKS))


def directory(path: str) -> str:
    return posixpath.dirname(posixpath.normpath(path))


def is_under(child_dir: str, parent_dir: str) -> bool:
    """True when child_dir is parent_dir or a subfolder of it. Prefix compare on components,
    never on the raw string: `src/billing2` must not count as inside `src/billing`."""
    if parent_dir in ("", "."):
        return True
    kid, mom = parts(child_dir), parts(parent_dir)
    return len(kid) >= len(mom) and kid[: len(mom)] == mom


def is_strictly_under(child_dir: str, parent_dir: str) -> bool:
    """`is_under` and NOT the same folder. The distinction is load-bearing: `is_under` is true for
    equal paths, so using it for "is this a subfolder" makes every same-layer peer look like a
    parent/child pair — which mislabels services as resolvers and legal peer edges as upward."""
    return child_dir != parent_dir and is_under(child_dir, parent_dir)


def initial_role(path: str, types: int, abstract: int) -> str:
    """Role from the path and the type shape. `resolver` is NOT decided here: it needs the edge
    set, so refine_roles() assigns it once every node exists."""
    segments = [p.lower() for p in parts(path)]
    name = base_name(path)
    dirs = segments[:-1]

    if any(d in TEST_MARKS for d in dirs) or name.startswith("test_") or name.endswith(
            ("_test", "_spec", ".test", ".spec")) or name in TEST_MARKS:
        return "test"
    if name in ROOT_MARKS or any(m in name for m in ("dependency_injection", "composition_root")):
        return "root"
    if any(d in UTIL_DIRS for d in dirs) or name in UTIL_DIRS:
        return "util"
    if any(m in name for m in CONTEXT_MARKS):
        return "context"
    # A file whose types are ALL abstract is a port by shape, whatever it is called. This beats
    # naming: a port that forgot the convention is still a port, and naming.md flags the name.
    if types and abstract == types:
        return "port"
    if any(m in name for m in PORT_MARKS):
        return "port"
    if name in REGISTRY_MARKS or "registry" in name:
        return "registry"
    if any(d in ADAPTER_DIRS for d in dirs):
        return "adapter"
    return "service"


def refine_roles(roles: dict[str, str], dirs: dict[str, str],
                 out_edges: dict[str, list[str]]) -> None:
    """Promote `service`/`adapter` to `resolver` when it imports a port declared ABOVE it.

    That is the structural definition of a resolver in this doctrine — a concrete answer living
    in a subfolder of the layer that asked the question — and it is checkable without naming.
    Mutates `roles` in place, because roles are one fact about a node, not a second graph.

    STRICTLY below: a file in the same folder as the port is its CALLER, not its answer. The
    caller is who declared the conflict, and calling it a resolver would then flag its perfectly
    legal edges — to its own registry, to a sibling service — as doctrine violations.
    """
    port_dirs = {nid: dirs.get(nid, "") for nid, role in roles.items() if role == "port"}
    promoted = [nid for nid, role in roles.items() if role in ("service", "adapter")
                and answers_a_port_above(dirs[nid], out_edges.get(nid, ()), port_dirs)]
    roles.update(dict.fromkeys(promoted, "resolver"))


def answers_a_port_above(node_dir: str, targets, port_dirs: dict[str, str]) -> bool:
    """True when one of `targets` is a port declared STRICTLY above `node_dir` — the structural
    signature of a resolver. `port_dirs` holds only ports, so a target absent from it is not one."""
    return any(is_strictly_under(node_dir, port_dirs[t]) for t in targets if t in port_dirs)


# The reasons, verbatim: each one is the finding text a reader acts on, so it names the rule that
# was broken and not the symptom. They live up here because the rules below read better as one line.
LEGAL = (True, "")
UTIL_SINK = "utils must be a sink node: it may not import application code"
IMPORTS_ROOT = "nothing may import the composition root; the root wires, it is not a service"
IMPORTS_TEST = "production code imports a test"
SIBLING_RESOLVER = "a resolver may not import a sibling resolver: siblings are alternatives"
OWN_REGISTRY = "a resolver may not import its own registry: edges point one way"
UPWARD = "upward edge to a {role}: only a port or a context may be imported upward"
SIDEWAYS = "sideways edge between sibling subtrees: route it through a port or a util"


def utils_are_a_sink(edge: dict) -> tuple[bool, str] | None:
    """Utils are a sink node, always (doctrine §8). Anything may point in; nothing may point out."""
    if edge["src_role"] == "util":
        return LEGAL if edge["dst_role"] == "util" else (False, UTIL_SINK)
    if edge["dst_role"] == "util":
        return LEGAL
    return None


def the_root_wires_everything(edge: dict) -> tuple[bool, str] | None:
    """The composition root is the one place allowed to know everything (di-patterns.md §1)."""
    if edge["src_role"] == "root":
        return LEGAL
    if edge["dst_role"] == "root":
        return False, IMPORTS_ROOT
    return None


def tests_may_reach_anything(edge: dict) -> tuple[bool, str] | None:
    """A test may reach anything it is testing; nothing production may reach back."""
    if edge["src_role"] == "test":
        return LEGAL
    if edge["dst_role"] == "test":
        return False, IMPORTS_TEST
    return None


def a_resolver_stands_alone(edge: dict) -> tuple[bool, str] | None:
    """Siblings are alternatives, never collaborators, and the registry chooses the resolver — so
    the edge from resolver back to registry would be the wrong way down the one-way street."""
    if edge["src_role"] != "resolver":
        return None
    if edge["dst_role"] == "resolver" and edge["dst_dir"] == edge["src_dir"]:
        return False, SIBLING_RESOLVER
    if edge["dst_role"] == "registry":
        return False, OWN_REGISTRY
    return None


def peers_in_one_layer(edge: dict) -> tuple[bool, str] | None:
    """Peers inside one layer. This must be tested BEFORE up and down, because `is_under` is true
    for equal paths: checking descent first makes every same-folder peer look like an ancestor."""
    return LEGAL if edge["dst_dir"] == edge["src_dir"] else None


def down_into_a_subfolder(edge: dict) -> tuple[bool, str] | None:
    """Down: into a subfolder. This is the ordinary declare/resolve edge."""
    return LEGAL if is_strictly_under(edge["dst_dir"], edge["src_dir"]) else None


def up_only_to_a_port(edge: dict) -> tuple[bool, str] | None:
    """Up: only to a port or a context in an ancestor layer — implementing what was declared."""
    if not is_strictly_under(edge["src_dir"], edge["dst_dir"]):
        return None
    if edge["dst_role"] in ("port", "context"):
        return LEGAL
    return False, UPWARD.format(role=edge["dst_role"])


def sideways_is_never_legal(edge: dict) -> tuple[bool, str]:
    """Neither peer, nor ancestor, nor descendant: two sibling subtrees pointing at each other.
    The last rule, so it always answers — a chain of rules with no floor would return nothing."""
    return False, SIDEWAYS


# THE ORDER IS LOAD-BEARING; this list IS doctrine §9's chain, first match wins. Roles are settled
# before paths, because a util/root/test answer does not depend on where the file sits. Among the
# path rules, `peers_in_one_layer` MUST precede the up and down rules: `is_under` is true for equal
# paths, so testing descent first makes every same-folder peer edge look like an ancestor edge.
RULES = (utils_are_a_sink, the_root_wires_everything, tests_may_reach_anything,
         a_resolver_stands_alone, peers_in_one_layer, down_into_a_subfolder,
         up_only_to_a_port, sideways_is_never_legal)


def legality(src: str, dst: str, roles: dict[str, str], dirs: dict[str, str]) -> tuple[bool, str]:
    """Is this edge legal under the layer rule? Returns (legal, reason-when-not)."""
    edge = {"src_role": roles.get(src, "unknown"), "dst_role": roles.get(dst, "unknown"),
            "src_dir": dirs.get(src, ""), "dst_dir": dirs.get(dst, "")}
    return first_verdict(edge)


def first_verdict(edge: dict) -> tuple[bool, str]:
    """Walk RULES in order and take the first rule that has an opinion; `None` means "not my
    rule, keep reading", which is what makes the order above the whole of the semantics."""
    verdicts = (rule(edge) for rule in RULES)
    return next(verdict for verdict in verdicts if verdict is not None)
