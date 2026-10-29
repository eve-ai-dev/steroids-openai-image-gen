# Current state

## 1.0.0 release

Maintainer explicitly authorizes publication to `eve-ai-dev/steroids-openai-image-gen` and accepts 1.0.0 with the known mask limitation deferred. This is a substantial compatibility adaptation, not a total rewrite. Source implementation remains the independently reviewed recovery candidate; release edits update version metadata and documentation only. README and CHANGELOG own public behavior and limitations.

## Verified boundaries

- Tested installed Hermes revision: `e8c97320ac8691d4de92af49f98459f9ef9ddb08`, without a Hermes upgrade.
- Recovery suite: 60 tests passed; isolated native plugin admission, unchanged TOP quality policy and independent candidate review passed.
- Real generation and multi-reference editing visually passed during recovery.
- Maintainer-reported smoke test passed generation, asynchronous editing and status lookup. A deliberate local rejection also reached the origin chat as a background error notification without an image API call.
- Operator reports Codex use and no API spend after checking account expenses. No arbitrary-endpoint billing guarantee is implied.

## Known open work

- Masked edits return black rectangles in transparent regions on the tested endpoint; maintainer explicitly deferred repair. A separate project task retains reproduction evidence.
- Successful background image attachment delivery is not transport-confirmed; `accepted` is not delivery confirmation.
- Default profile has been enabled. Work source was placed but admission failed; other requested profiles are not confirmed installed. Native dependency admission rejects a selected dependency generation. Do not bypass it; publishing source does not resolve activation.
- Legacy direct Codex mode needs an unavailable public host helper and fails closed. The tested managed compatible route is separate.
- Historical lock and catalogue outputs are provenance, not current installation/catalogue acceptance.

## Evidence and authority

Recovery commits and existing source reviews are retained in Git. Detailed deployment-specific receipts and task packages remain outside the public repository. Current publication scope: review/sanitize release changes, local non-network validation, commit, fast-forward push, v1.0.0 tag/release and remote verification. No new image API calls, runtime changes, dependency changes or profile activation are authorized by publication.
