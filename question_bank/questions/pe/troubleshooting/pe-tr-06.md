---
id: pe-tr-06
domain: pe
topic: troubleshooting
difficulty: medium
tags: [tls, certificates, time-based, prevention]
companies: []
source: seed
created: 2026-09-11
---

# Prompt
At 03:00 every client starts failing TLS handshakes to your API. Nothing was deployed. What happened and how do you both fix it and stop it recurring?

## What interviewers look for
- Reads the 'nothing was deployed' + exact-time clue as a time-based failure rather than hunting code
- Confirms with evidence (openssl output, notAfter) before declaring, and considers the near-miss alternatives
- Fixes across every TLS-terminating surface, not just one host, and verifies externally
- Treats prevention as inventory + automation + expiry alerting, including internal and client certs
- Handles the chain, not just the leaf

## Strong answer covers
1. Read the clue: failures at an exact wall-clock time with no deploy means time-based — certificate expiry, a cron/rotation job, a scheduled key rotation, or clock skew; certificate notAfter is UTC, so a 03:00 local failure often maps to a round UTC timestamp
2. Confirm with evidence: `openssl s_client -connect api.example.com:443 -servername api.example.com -showcerts </dev/null | openssl x509 -noout -subject -issuer -dates` and check `notBefore`/`notAfter`; distinguish the client error strings — 'certificate has expired' vs 'unable to get local issuer certificate' (missing intermediate) vs 'certificate is not yet valid' (clock skew or a freshly issued cert)
3. Check the whole chain and all terminating surfaces: leaf, intermediate and cross-signed root expiry, OCSP stapling staleness, and every place TLS terminates — each LB/edge node, every app host, sidecars/service mesh, CDN, API gateways — a partial failure usually means one node in a pool wasn't updated
4. Rule out the near-misses deliberately: clock skew on servers (`chronyc tracking`/`timedatectl`, drift would also break tokens, JWT/OIDC and signed requests), a CA-side change or revocation, an expired client certificate in mTLS, and a renewal automation job that ran at 03:00 and installed the wrong file
5. Fix: issue/renew the cert, install the full chain in the right order, reload rather than restart where possible (`nginx -s reload`, `systemctl reload`), and roll it across the fleet; verify from an external vantage point and on multiple client trust stores, not just from inside the network
6. Verify recovery quantitatively: handshake error rate and client success rate back to baseline, `openssl` showing the new dates, `ssl_certificate_expiry` prober metric refreshed, and confirm no clients are pinning the old cert or caching a stale chain
7. Prevent with automation: ACME/cert-manager or equivalent automated renewal with monitoring on the renewal job itself (a silent renewal failure is the real risk), renew at 1/3 lifetime so there's slack, and staggered expiries so one mistake doesn't expire everything at once
8. Prevent with inventory and alerting: blackbox prober exporting days-to-expiry for every public SNI name plus internal mTLS, Kafka, database, and service-mesh certs; tiered alerts (e.g. ticket at 30 days, page at 7), a cert inventory including internal CA roots and long-lived client certs, and a postmortem action item on the detection gap — customers noticed before monitoring did

## Follow-ups
- Only older Android clients and one partner's Java service fail; browsers are fine. What's the most likely cause and how do you confirm it?
- Your internal root CA expires in nine months and thousands of services trust it. Sketch the rotation plan.
- You have mTLS client certificates on 50,000 edge devices with 1-year lifetimes. How do you avoid a mass expiry event?
- The automated renewal job has been failing silently for three weeks. What monitoring would have caught that, and how do you test that the monitoring works?

## Sample answer
Failures starting at an exact wall-clock time with nothing deployed screams time-based, and the top candidate is certificate expiry — notAfter is in UTC, so a 03:00 failure often lines up with a round UTC timestamp. I'd confirm rather than assume: `openssl s_client -connect host:443 -servername host -showcerts` and read subject, issuer and dates, and I'd read the exact client error. 'Certificate has expired' is different from 'unable to get local issuer certificate', which means a missing intermediate, and 'not yet valid' would point at clock skew — which I'd rule out with `chronyc tracking`, since drift also breaks tokens and signed requests.

Fix: renew, install the full chain in the right order, and reload rather than restart. Crucially, I'd do it on every surface that terminates TLS — each LB node, app hosts, sidecars, CDN, gateways — because partial failures usually mean one node was missed. Then verify externally, from multiple trust stores, and watch handshake error rate return to baseline.

Prevention is the real answer. Automated renewal via ACME at a third of the lifetime, with monitoring on the renewal job itself, because silent renewal failure is the actual risk. A blackbox prober exporting days-to-expiry for every public name plus internal mTLS, Kafka and mesh certs, ticket at 30 days and page at 7, staggered expiries, and a cert inventory including internal CA roots. The postmortem's headline is the detection gap: users found this, not us.
