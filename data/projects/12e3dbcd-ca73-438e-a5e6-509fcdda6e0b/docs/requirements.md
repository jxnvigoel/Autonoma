# 1. Problem Statement
Create an end-to-end encrypted file sync tool for creative teams like video editors and 3D artists, using peer-to-peer file transfer over LAN with zero-knowledge AES-256-GCM encryption.

# 2. Personas
P-01: Video Editor
P-02: 3D Artist

# 3. User Journeys
User will transfer a large file (20GB) between users, with a desired transfer speed of 1Gbps or 10Gbps local network.

# 4. Functional Requirements
FR-01: Must Have - Peer-to-peer file transfer over LAN with zero-knowledge AES-256-GCM encryption. [Source: Q-005]
FR-02: Must Have - LAN discovery. [Source: Q-005]
FR-03: Must Have - Block-level diffing. [Source: Q-005]
FR-04: Should Have - Cloud relay out of scope for initial version (v1). [Source: Q-005]
FR-05: Could Have - Automatic file format conversion. [Source: Q-006]
FR-06: Won't Have - Real-time collaboration features. [Source: Q-006]

# 5. Non-Functional Requirements
NFR-01: Must Have - Transfer a 20GB video project file in under 3 minutes with verified SHA-256 hash match. [Source: Q-006]
NFR-02: Should Have - Transfer speed of 1Gbps or 10Gbps local network. [Source: Q-003]
NFR-03: Must Have - Authentication process with local passkey or team invite link. [Source: Q-004]

# 6. Data Requirements & Entities
* User data: local passkey, team invite link
* File data: encrypted files, SHA-256 hash matches

# 7. Integrations & External Services
None

# 8. Timeline & Budget
* Timeline: 8 weeks
* Budget: $0,000

# 9. v1 Scope vs Later
Cloud relay is out of scope for initial version (v1).

# 10. Definition of Success & Key Metrics
Success metric: transfer a 20GB video project file in under 3 minutes with verified SHA-256 hash match.

# 11. Assumptions
ASM-01: No cloud server will be responsible for holding decryption keys. (Risk: data breaches, Reason: security requirement)
ASM-02: Users will authenticate via local passkey or team invite link. (Risk: security breaches, Reason: security requirement)