---
policy_id: restricted-area
title: Restricted Area Policy
version: "1.0"
effective_date: 2026-01-15
category: restricted_area
---

## Purpose

Define which physical areas are restricted, who may enter them, and how
unauthorized presence is detected, assessed, and escalated by the GuardX
security system.

## Rules

1. Restricted zones are marked on the facility map and in the GuardX dashboard.
   Examples include server rooms, electrical switchgear rooms, cash handling
   areas, and records archives.
2. Only personnel with an active access grant for a zone may enter it.
3. Access grants are issued by the facility security officer and expire
   automatically after 90 days unless renewed.
4. Tailgating (following an authorized person through a secured door without
   badging in) is prohibited.
5. Contractors and visitors must be escorted by an authorized employee at all
   times inside restricted zones.
6. Doors to restricted zones must remain closed and locked when not in active
   use. Propping doors open is prohibited.

## Severity Guidance

- A person detected inside a restricted zone without a matching access grant
  is a HIGH severity event.
- A person loitering at the boundary of a restricted zone for more than
  60 seconds is a MEDIUM severity event.
- A door held open for more than 30 seconds is a MEDIUM severity event.
- Authorized personnel performing scheduled work is LOW severity (informational).

## Recommended Response

1. Verify the person's identity and access grant in the access-control system.
2. If unauthorized, dispatch security personnel to the zone immediately and
   issue a verbal warning over the PA system.
3. If the person does not leave within 2 minutes, escalate to the facility
   security officer and consider contacting local law enforcement.
4. Log the incident with camera ID, zone name, timestamps, and a snapshot.
