# Meeting: SLA and Timeout Finalization
Date: 2026-07-19
Participants: Karl, Laura, Mike

00:01:00 Karl: After reviewing the SLA requirements, we need to revise the API Gateway timeout.
00:01:45 Laura: The timeout for upstream services must be 60 seconds, not 30, to accommodate the legacy backend.
00:02:30 Mike: This supersedes what was decided in the July 15 meeting.
00:03:00 Karl: OAuth 2.0 token introspection must be cached to reduce latency under the 60-second budget.
