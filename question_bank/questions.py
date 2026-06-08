"""Hardcoded question bank for Phase 1 (replaced by a vector DB in Phase 2).

Each question:
    id, domain, topic, difficulty, tags, prompt, expected_answer_notes

Helpers let the Interviewer filter by domain/topic and exclude already-seen IDs.
"""

QUESTIONS = [
    # ===================== PE: Coding =====================
    {
        "id": "pe-cod-01", "domain": "pe", "topic": "coding", "difficulty": "easy",
        "tags": ["file-io", "memory-safety"],
        "prompt": "Given a multi-GB log file, compute the average response time from "
                  "a numeric field on each line. The file does not fit in memory.",
        "expected_answer_notes": "Line-by-line streaming, running sum + count, O(1) memory. "
                                  "Handle malformed lines and empty file.",
    },
    {
        "id": "pe-cod-02", "domain": "pe", "topic": "coding", "difficulty": "medium",
        "tags": ["hash-map", "top-k"],
        "prompt": "Find the top 5 IPs by request count in an access log.",
        "expected_answer_notes": "Counter for tallies, heapq.nlargest(5) or a size-5 heap. "
                                  "State O(n) time, O(unique) space.",
    },
    {
        "id": "pe-cod-03", "domain": "pe", "topic": "coding", "difficulty": "medium",
        "tags": ["heap", "streaming"],
        "prompt": "Maintain a running median of latencies from a stream of values.",
        "expected_answer_notes": "Two heaps (max-heap low half, min-heap high half), rebalance. "
                                  "O(log n) per insert.",
    },

    # ===================== PE: Linux / Troubleshooting =====================
    {
        "id": "pe-lnx-01", "domain": "pe", "topic": "linux", "difficulty": "medium",
        "tags": ["disk", "inodes"],
        "prompt": "A service reports 'No space left on device' but `df -h` shows 40% free. "
                  "Walk me through diagnosing it.",
        "expected_answer_notes": "Check `df -i` for inode exhaustion; also deleted-but-open "
                                  "files held by a process (`lsof | grep deleted`).",
    },
    {
        "id": "pe-lnx-02", "domain": "pe", "topic": "troubleshooting", "difficulty": "hard",
        "tags": ["latency", "methodology"],
        "prompt": "One host in a fleet shows 10x p99 latency vs its peers. Same code, same "
                  "config. How do you find why?",
        "expected_answer_notes": "Characterise, compare to a healthy peer, USE method, check "
                                  "noisy neighbour / NIC errors / disk await / one hot CPU. "
                                  "Preserve data, simplest safe fix, fleet-wide prevention.",
    },

    # ===================== PE: System Design =====================
    {
        "id": "pe-sd-01", "domain": "pe", "topic": "system_design", "difficulty": "hard",
        "tags": ["rate-limiting"],
        "prompt": "Design a distributed rate limiter for an API gateway at 1M QPS.",
        "expected_answer_notes": "Token bucket, where state lives (Redis vs local + sync), "
                                  "accuracy vs latency trade-off, failure modes, hot keys.",
    },
    {
        "id": "pe-sd-02", "domain": "pe", "topic": "system_design", "difficulty": "hard",
        "tags": ["observability"],
        "prompt": "Design a metrics pipeline that ingests 10M datapoints/sec.",
        "expected_answer_notes": "Sharding, aggregation at edge, time-series store, "
                                  "cardinality control, downsampling, backpressure.",
    },

    # ===================== NE: Fundamentals =====================
    {
        "id": "ne-fun-01", "domain": "ne", "topic": "networking_fundamentals", "difficulty": "easy",
        "tags": ["subnetting", "cidr"],
        "prompt": "How many usable hosts in a /26? Explain how you got there, and give a "
                  "case where you'd use a /30.",
        "expected_answer_notes": "/26 = 64 addrs, 62 usable. /30 (2 usable) for point-to-point links.",
    },
    {
        "id": "ne-fun-02", "domain": "ne", "topic": "networking_fundamentals", "difficulty": "medium",
        "tags": ["tcp", "mtu"],
        "prompt": "Small requests work but large file transfers hang intermittently across a "
                  "tunnel. What's your leading hypothesis and how do you confirm?",
        "expected_answer_notes": "PMTU black hole / MTU mismatch. Confirm with ping -M do -s "
                                  "(DF bit) sweeping sizes; fix via MSS clamping.",
    },

    # ===================== NE: Routing =====================
    {
        "id": "ne-rt-01", "domain": "ne", "topic": "routing", "difficulty": "hard",
        "tags": ["bgp"],
        "prompt": "Walk me through exactly what happens when a BGP session drops, end to end.",
        "expected_answer_notes": "Hold timer expiry → session torn down → routes withdrawn → "
                                  "reconvergence on alternate paths → traffic shift. Mention "
                                  "dampening, next-hop, blast radius.",
    },
    {
        "id": "ne-rt-02", "domain": "ne", "topic": "routing", "difficulty": "medium",
        "tags": ["bgp", "path-selection"],
        "prompt": "Two paths to the same prefix; traffic takes the longer one. How do you "
                  "find why BGP chose it?",
        "expected_answer_notes": "Walk path-selection order: Local Pref before AS_PATH length, "
                                  "then MED, etc. Check route-maps and Local Preference settings.",
    },

    # ===================== NE: Network Troubleshooting =====================
    {
        "id": "ne-tr-01", "domain": "ne", "topic": "network_troubleshooting", "difficulty": "hard",
        "tags": ["latency", "methodology"],
        "prompt": "Users in one region report intermittent high latency to your service; "
                  "other regions are fine. Diagnose it.",
        "expected_answer_notes": "mtr to compare per-hop loss/latency, isolate the bad hop/path, "
                                  "check for BGP flap/route change, asymmetric routing, regional "
                                  "peering. Distinguish ICMP-deprioritised hops from real loss.",
    },
    {
        "id": "ne-tr-02", "domain": "ne", "topic": "network_troubleshooting", "difficulty": "medium",
        "tags": ["tcp", "firewall"],
        "prompt": "A client gets connection timeouts to a service that's confirmed up and "
                  "listening. tcpdump shows SYN sent, no SYN-ACK. What's happening?",
        "expected_answer_notes": "Firewall/ACL silently dropping, security-group misconfig, or "
                                  "asymmetric return path. RST would mean closed/rejected instead.",
    },

    # ===================== NE: Network Design =====================
    {
        "id": "ne-des-01", "domain": "ne", "topic": "network_design", "difficulty": "hard",
        "tags": ["datacenter", "fabric"],
        "prompt": "Design a datacenter network for 10,000 servers. Walk me through topology, "
                  "routing, and how you'd handle a spine failure.",
        "expected_answer_notes": "Spine-leaf Clos, L3 to leaf with eBGP + ECMP, oversubscription "
                                  "ratio, spine failure absorbed by ECMP, capacity headroom.",
    },
    {
        "id": "ne-des-02", "domain": "ne", "topic": "network_design", "difficulty": "medium",
        "tags": ["cloud", "vpc"],
        "prompt": "Design a multi-region VPC architecture for a service that must survive a "
                  "full region outage.",
        "expected_answer_notes": "Per-region VPC, non-overlapping CIDRs, transit gateway/peering, "
                                  "multi-AZ subnets, anycast/global LB, data replication strategy.",
    },

    # ===================== NE: Network Security =====================
    {
        "id": "ne-sec-01", "domain": "ne", "topic": "network_security", "difficulty": "medium",
        "tags": ["acl", "firewall"],
        "prompt": "An ACL change was meant to block one subnet but broke production traffic. "
                  "How do you reason about what went wrong?",
        "expected_answer_notes": "First-match ordering, stateful vs stateless return traffic, "
                                  "implicit deny, blast radius. Roll back safely, test narrowly.",
    },
]


def get_questions(domain: str | None = None, topic: str | None = None,
                  exclude_ids: set | None = None) -> list[dict]:
    exclude_ids = exclude_ids or set()
    out = []
    for q in QUESTIONS:
        if domain and q["domain"] != domain:
            continue
        if topic and q["topic"] != topic:
            continue
        if q["id"] in exclude_ids:
            continue
        out.append(q)
    return out


def get_question_by_id(qid: str) -> dict | None:
    return next((q for q in QUESTIONS if q["id"] == qid), None)
