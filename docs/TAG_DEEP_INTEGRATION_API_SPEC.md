# TAG Sports Deep Integration - API & Platform Specification

**Document Type:** Technical Architecture & API Specification
**Date:** March 26, 2026
**Version:** 2.0 (Deep Integration - Bluetooth + Cloud API)
**Status:** SPECULATIVE — design only. Cloud backend, Bluetooth integration, and
UI components do not exist. Phase 2 (cloud sync) requires 12–18 weeks of
engineering plus infrastructure. Phase 3 (Bluetooth) is unstarted. No partnership
agreement exists. Do not treat this document as current product capability.
**Owner:** Engineering Lead + Platform Architect

---

## Executive Summary

This document defines a **comprehensive platform integration** between TAG Sports and PitchTracker that goes beyond simple data export/import. The deep integration enables:

1. **Real-time data streaming** from TAG Sports devices to PitchTracker facilities (Bluetooth PC ingest)
2. **Cloud-based athlete profiles** (unified identity across TAG mobile app and PitchTracker facilities)
3. **Bidirectional data flow** (TAG sends practice data → PitchTracker sends coaching insights back)
4. **Webhook notifications** (real-time updates between systems)
5. **Dual-mode TAG operation** (standalone mobile app OR PitchTracker facility peripheral)

**Strategic Positioning:** PitchTracker becomes the **professional backend platform** for TAG Sports facility users. TAG Sports remains consumer brand; PitchTracker provides institutional-grade data infrastructure.

**Value Proposition:**
- **For TAG Sports:** Professional platform integration (elevates brand), richer data for users (PitchTracker insights flow back to TAG app)
- **For PitchTracker:** Real-time data ingest (no manual transfer), exclusive TAG integration (competitive moat)
- **For Athletes:** Seamless experience (TAG device works at home AND at facility, data everywhere)
- **For Facilities:** Live TAG device integration (athletes can use their TAG during facility sessions)

---

## Table of Contents

1. [Integration Architecture Overview](#1-integration-architecture-overview)
2. [Bluetooth PC Ingest Specification](#2-bluetooth-pc-ingest-specification)
3. [Cloud API Specification](#3-cloud-api-specification)
4. [Athlete Profile Service](#4-athlete-profile-service)
5. [Real-time Streaming Protocol](#5-real-time-streaming-protocol)
6. [Bidirectional Data Flow](#6-bidirectional-data-flow)
7. [Security & Authentication](#7-security--authentication)
8. [Implementation Phases](#8-implementation-phases)
9. [Use Cases & Workflows](#9-use-cases--workflows)
10. [Infrastructure Requirements](#10-infrastructure-requirements)

---

## 1. Integration Architecture Overview

### Three-Tier Integration Model

```
┌─────────────────────────────────────────────────────────────┐
│                    TIER 1: DEVICE LAYER                     │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │ TAG Sports   │         │ PitchTracker │                 │
│  │ Radar Device │         │ Cameras      │                 │
│  └──────┬───────┘         └──────┬───────┘                 │
│         │ Bluetooth               │ USB                     │
│         │ (at home or facility)   │ (facility only)         │
└─────────┼─────────────────────────┼─────────────────────────┘
          │                         │
          v                         v
┌─────────────────────────────────────────────────────────────┐
│                    TIER 2: LOCAL LAYER                      │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │ TAG Sports   │         │ PitchTracker │                 │
│  │ Mobile App   │         │ Desktop App  │                 │
│  │ (iOS/Android)│         │ (Windows PC) │                 │
│  └──────┬───────┘         └──────┬───────┘                 │
│         │                         │                         │
│         │      REST API           │                         │
│         └───────┬─────────────────┘                         │
│                 │                                           │
└─────────────────┼───────────────────────────────────────────┘
                  │
                  v
┌─────────────────────────────────────────────────────────────┐
│                   TIER 3: CLOUD LAYER                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │      PitchTracker Cloud Platform (NEW)             │    │
│  │                                                     │    │
│  │  • Athlete Profile Service (unified identity)      │    │
│  │  • Data Sync Service (TAG ↔ PitchTracker)         │    │
│  │  │  Session Store (practice + facility sessions)   │    │
│  │  • Analytics Engine (combined dataset insights)    │    │
│  │  • Notification Service (webhooks, push)           │    │
│  │  • Authentication (OAuth 2.0, JWT tokens)          │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Integration Modes

#### Mode 1: Standalone (No Integration)
- TAG Sports device → TAG mobile app (Bluetooth)
- PitchTracker cameras → PitchTracker desktop app
- **No data sharing** (existing behavior)

#### Mode 2: Manual Sync (Phase 1 - MVP)
- TAG Sports app exports JSON → PitchTracker imports
- **One-way data flow** (TAG → PitchTracker)
- **Manual transfer** (athlete action required)

#### Mode 3: Cloud Sync (Phase 2)
- TAG Sports app → Cloud platform ← PitchTracker app
- **Automatic sync** (no athlete action)
- **Bidirectional** (insights flow back to TAG app)

#### Mode 4: Live PC Ingest (Phase 3 - DEEP INTEGRATION)
- TAG Sports device → Bluetooth → Facility PC → PitchTracker
- **Real-time streaming** (pitch-by-pitch during facility sessions)
- **Dual-mode TAG device** (works as mobile app peripheral OR PitchTracker peripheral)

#### Mode 5: Unified Platform (Phase 4 - Future)
- Single athlete account across TAG Sports and PitchTracker
- Mobile app shows TAG + PitchTracker data
- Desktop app shows TAG + camera data
- **Seamless experience** (one platform, multiple devices)

---

## 2. Bluetooth PC Ingest Specification

### Use Case

**Scenario:** Athlete brings TAG Sports device to PitchTracker facility. Instead of using TAG mobile app, device pairs with facility PC running PitchTracker. During session, TAG device measures velocity in real-time and streams to PitchTracker, which combines with stereo camera data for comprehensive analysis.

**Benefit:**
- **For Athlete:** One device for home (TAG app) and facility (PitchTracker integration)
- **For Facility:** Redundant velocity measurement (TAG radar + PitchTracker stereo = cross-validation)
- **For Accuracy:** Compare TAG velocity vs. PitchTracker velocity in real-time (immediate calibration feedback)

### Bluetooth Protocol

**Transport:** Bluetooth Low Energy (BLE) - standard for low-power devices
**Range:** 10-30 feet (sufficient for facility use)
**Pairing:** One-time pairing, saved for future sessions

#### BLE Service Definition

**Service UUID:** `0000PT01-0000-1000-8000-00805f9b34fb` (PitchTracker Integration Service)

**Characteristics:**

1. **Device Info (Read-Only)**
   - UUID: `0000PT02-0000-1000-8000-00805f9b34fb`
   - Value: JSON string
   ```json
   {
     "device_id": "TAG_12345ABC",
     "model": "TAG_One_v2",
     "firmware_version": "2.1.0",
     "battery_level": 85,
     "athlete_id": "tag_user_xyz" // if logged in
   }
   ```

2. **Pitch Data Stream (Notify)**
   - UUID: `0000PT03-0000-1000-8000-00805f9b34fb`
   - Value: JSON string (sent on each pitch detection)
   ```json
   {
     "timestamp": "2026-03-26T15:23:45.123Z",
     "speed_mph": 72.3,
     "measurement_confidence": 0.95, // 0-1 scale
     "pitch_sequence_num": 12, // session-local pitch count
     "device_battery": 85
   }
   ```

3. **Session Control (Read/Write)**
   - UUID: `0000PT04-0000-1000-8000-00805f9b34fb`
   - Write: `{"command": "start_session"}` or `{"command": "end_session"}`
   - Read: `{"status": "active"}` or `{"status": "idle"}`

4. **Configuration (Read/Write)**
   - UUID: `0000PT05-0000-1000-8000-00805f9b34fb`
   - Write: Configure TAG device settings from PitchTracker
   ```json
   {
     "sensitivity": "high", // low, medium, high
     "measurement_mode": "peak_velocity", // or "release_velocity"
     "auto_pitch_detection": true
   }
   ```

---

### PitchTracker Implementation (PC Side)

**File:** `app/hardware/tag_sports_bluetooth.py` (NEW)

```python
"""Bluetooth integration for TAG Sports devices."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable

from bleak import BleakClient, BleakScanner
from loguru import logger


# BLE Service/Characteristic UUIDs
TAG_SERVICE_UUID = "0000PT01-0000-1000-8000-00805f9b34fb"
DEVICE_INFO_UUID = "0000PT02-0000-1000-8000-00805f9b34fb"
PITCH_STREAM_UUID = "0000PT03-0000-1000-8000-00805f9b34fb"
SESSION_CONTROL_UUID = "0000PT04-0000-1000-8000-00805f9b34fb"
CONFIG_UUID = "0000PT05-0000-1000-8000-00805f9b34fb"


@dataclass
class TagDeviceInfo:
    """TAG Sports device information."""
    device_id: str
    model: str
    firmware_version: str
    battery_level: int
    athlete_id: Optional[str] = None


@dataclass
class TagPitchMeasurement:
    """Individual pitch measurement from TAG device."""
    timestamp: datetime
    speed_mph: float
    measurement_confidence: float  # 0-1
    pitch_sequence_num: int
    device_battery: int


class TagSportsBluetoothService:
    """Service for connecting to and receiving data from TAG Sports devices via Bluetooth."""

    def __init__(self):
        self._client: Optional[BleakClient] = None
        self._device_info: Optional[TagDeviceInfo] = None
        self._connected = False
        self._pitch_callback: Optional[Callable[[TagPitchMeasurement], None]] = None

    async def scan_for_devices(self, timeout: float = 10.0) -> list[str]:
        """Scan for nearby TAG Sports devices.

        Args:
            timeout: Scan duration in seconds

        Returns:
            List of device addresses/names found
        """
        logger.info(f"Scanning for TAG Sports devices ({timeout}s)...")
        devices = await BleakScanner.discover(timeout=timeout)

        tag_devices = []
        for device in devices:
            # Filter for TAG Sports devices (by name or service UUID)
            if "TAG" in device.name or TAG_SERVICE_UUID in device.metadata.get("uuids", []):
                tag_devices.append(device.address)
                logger.info(f"Found TAG device: {device.name} ({device.address})")

        return tag_devices

    async def connect(self, device_address: str) -> bool:
        """Connect to TAG Sports device via Bluetooth.

        Args:
            device_address: Bluetooth address of TAG device

        Returns:
            True if connection successful
        """
        try:
            logger.info(f"Connecting to TAG device: {device_address}")
            self._client = BleakClient(device_address)
            await self._client.connect()

            if not self._client.is_connected:
                logger.error("Failed to connect to TAG device")
                return False

            logger.info("Connected to TAG device successfully")

            # Read device info
            device_info_bytes = await self._client.read_gatt_char(DEVICE_INFO_UUID)
            device_info_json = device_info_bytes.decode('utf-8')
            device_info_data = json.loads(device_info_json)

            self._device_info = TagDeviceInfo(
                device_id=device_info_data["device_id"],
                model=device_info_data["model"],
                firmware_version=device_info_data["firmware_version"],
                battery_level=device_info_data["battery_level"],
                athlete_id=device_info_data.get("athlete_id")
            )

            logger.info(f"Device info: {self._device_info}")

            # Subscribe to pitch data stream
            await self._client.start_notify(PITCH_STREAM_UUID, self._on_pitch_data_received)

            self._connected = True
            return True

        except Exception as e:
            logger.exception(f"Failed to connect to TAG device: {e}")
            self._connected = False
            return False

    def _on_pitch_data_received(self, sender, data: bytearray) -> None:
        """Callback when pitch data is received via BLE notification.

        Args:
            sender: Characteristic that sent notification
            data: Pitch data as bytes
        """
        try:
            # Decode JSON
            pitch_json = data.decode('utf-8')
            pitch_data = json.loads(pitch_json)

            # Parse pitch measurement
            measurement = TagPitchMeasurement(
                timestamp=datetime.fromisoformat(pitch_data["timestamp"].replace('Z', '+00:00')),
                speed_mph=pitch_data["speed_mph"],
                measurement_confidence=pitch_data["measurement_confidence"],
                pitch_sequence_num=pitch_data["pitch_sequence_num"],
                device_battery=pitch_data["device_battery"]
            )

            logger.info(f"Pitch received: {measurement.speed_mph:.1f} mph (confidence: {measurement.measurement_confidence:.2f})")

            # Forward to callback (PitchTracker pipeline)
            if self._pitch_callback:
                self._pitch_callback(measurement)

        except Exception as e:
            logger.exception(f"Failed to parse pitch data: {e}")

    def set_pitch_callback(self, callback: Callable[[TagPitchMeasurement], None]) -> None:
        """Set callback function to receive pitch measurements.

        Args:
            callback: Function that takes TagPitchMeasurement and processes it
        """
        self._pitch_callback = callback

    async def start_session(self) -> bool:
        """Send command to TAG device to start session.

        Returns:
            True if command successful
        """
        if not self._connected or not self._client:
            logger.error("Not connected to TAG device")
            return False

        try:
            command = json.dumps({"command": "start_session"})
            await self._client.write_gatt_char(SESSION_CONTROL_UUID, command.encode('utf-8'))
            logger.info("Sent start_session command to TAG device")
            return True
        except Exception as e:
            logger.exception(f"Failed to start session: {e}")
            return False

    async def end_session(self) -> bool:
        """Send command to TAG device to end session.

        Returns:
            True if command successful
        """
        if not self._connected or not self._client:
            logger.error("Not connected to TAG device")
            return False

        try:
            command = json.dumps({"command": "end_session"})
            await self._client.write_gatt_char(SESSION_CONTROL_UUID, command.encode('utf-8'))
            logger.info("Sent end_session command to TAG device")
            return True
        except Exception as e:
            logger.exception(f"Failed to end session: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from TAG device."""
        if self._client and self._client.is_connected:
            await self._client.disconnect()
            logger.info("Disconnected from TAG device")
        self._connected = False

    def is_connected(self) -> bool:
        """Check if connected to TAG device."""
        return self._connected and self._client and self._client.is_connected

    @property
    def device_info(self) -> Optional[TagDeviceInfo]:
        """Get connected device information."""
        return self._device_info
```

**Dependencies:**
- `bleak` (Python BLE library, cross-platform) - Add to requirements.txt
- `asyncio` (Python stdlib, for async BLE operations)

---

### Dual-Mode Operation (TAG Device Perspective)

**MODE A: Standalone (Current TAG Sports Behavior)**
```
TAG Device --[Bluetooth]--> TAG Mobile App (iOS/Android)
                                 |
                                 v
                         TAG Sports Cloud
                                 |
                                 v
                         Athlete's Practice History
```

**MODE B: Facility Integration (NEW)**
```
TAG Device --[Bluetooth]--> Facility PC (PitchTracker)
                                 |
                                 v
                         PitchTracker Local Session
                                 |
                                 v
                         PitchTracker Cloud Platform
                                 |
                                 v
                         Unified Athlete Profile (TAG + PitchTracker)
```

**MODE C: Hybrid (Simultaneous)**
```
TAG Device --[Bluetooth]--> TAG Mobile App (monitoring/backup)
      |
      └─────[Bluetooth]────> Facility PC (primary data)
```

**Implementation:** TAG device supports multiple Bluetooth connections (common BLE capability)

---

## 3. Cloud API Specification

### PitchTracker Cloud Platform (NEW)

**Base URL:** `https://api.pitchtracker.io/v1`
**Protocol:** REST API (JSON payloads)
**Authentication:** OAuth 2.0 + JWT Bearer tokens
**Rate Limiting:** 1000 requests/hour per API key

### API Endpoints

#### Authentication

**POST /auth/oauth/token**
Get OAuth access token for API access

```http
POST /auth/oauth/token
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "client_id": "tag_sports_integration",
  "client_secret": "SECRET_KEY_PROVIDED_BY_PITCHTRACKER"
}

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read:athletes write:sessions"
}
```

---

#### Athlete Profile Management

**POST /athletes**
Create or link athlete profile (unified identity)

```http
POST /athletes
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "tag_user_id": "tag_abc123xyz",
  "name": "John Doe",
  "birth_year": 2010,
  "throws": "right",
  "position": "pitcher",
  "email": "john.doe@example.com",
  "consent": {
    "data_sharing": true,
    "marketing": false,
    "parent_email": "parent@example.com" // if under 13 (COPPA)
  }
}

Response:
{
  "athlete_id": "pt_athlete_xyz789",
  "tag_user_id": "tag_abc123xyz",
  "pitchtracker_profile_created": true,
  "profile_url": "https://api.pitchtracker.io/v1/athletes/pt_athlete_xyz789"
}
```

**GET /athletes/{athlete_id}**
Get athlete profile (unified TAG + PitchTracker data)

```http
GET /athletes/pt_athlete_xyz789
Authorization: Bearer {access_token}

Response:
{
  "athlete_id": "pt_athlete_xyz789",
  "tag_user_id": "tag_abc123xyz",
  "name": "John Doe",
  "birth_year": 2010,
  "throws": "right",
  "stats": {
    "practice_sessions_tag": 45, // from TAG Sports
    "facility_sessions_pt": 12,  // from PitchTracker
    "total_pitches": 1823,
    "avg_velocity_practice": 71.4, // TAG Sports
    "avg_velocity_facility": 73.8,  // PitchTracker
    "velocity_trend": 1.3 // mph/week improvement
  },
  "last_updated": "2026-03-26T10:30:00Z"
}
```

---

#### Session Data Sync

**POST /sessions**
Upload session data (from TAG Sports or PitchTracker)

```http
POST /sessions
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "source": "tag_sports", // or "pitchtracker"
  "session_id": "tag_session_001",
  "athlete_id": "pt_athlete_xyz789",
  "date": "2026-03-20T15:00:00Z",
  "location": "Backyard practice",
  "session_type": "practice",
  "pitches": [
    {
      "pitch_number": 1,
      "timestamp": "2026-03-20T15:05:23Z",
      "speed_mph": 72.3,
      "pitch_type": "Fastball" // if athlete-tagged
    },
    // ... more pitches
  ],
  "summary": {
    "total_pitches": 45,
    "avg_speed_mph": 71.2,
    "max_speed_mph": 74.8
  }
}

Response:
{
  "session_id": "pt_session_xyz",
  "cloud_session_id": "cloud_123abc",
  "athlete_id": "pt_athlete_xyz789",
  "pitches_stored": 45,
  "status": "synced"
}
```

**GET /athletes/{athlete_id}/sessions**
Get athlete's session history (TAG + PitchTracker combined)

```http
GET /athletes/pt_athlete_xyz789/sessions?start_date=2026-03-01&end_date=2026-03-31
Authorization: Bearer {access_token}

Response:
{
  "athlete_id": "pt_athlete_xyz789",
  "sessions": [
    {
      "session_id": "cloud_123abc",
      "source": "tag_sports",
      "date": "2026-03-20T15:00:00Z",
      "location": "Backyard practice",
      "total_pitches": 45,
      "avg_speed_mph": 71.2
    },
    {
      "session_id": "cloud_456def",
      "source": "pitchtracker",
      "date": "2026-03-22T16:00:00Z",
      "location": "Elite Baseball Academy",
      "total_pitches": 52,
      "avg_speed_mph": 73.8,
      "trajectory_data_available": true, // PitchTracker has 3D data
      "movement_data_available": true
    }
    // ... more sessions
  ],
  "total_sessions": 57,
  "date_range": {
    "start": "2026-03-01",
    "end": "2026-03-31"
  }
}
```

---

#### Analytics & Insights

**GET /athletes/{athlete_id}/insights**
Get AI-generated insights (PitchTracker pattern detection combined with TAG practice data)

```http
GET /athletes/pt_athlete_xyz789/insights
Authorization: Bearer {access_token}

Response:
{
  "athlete_id": "pt_athlete_xyz789",
  "generated_at": "2026-03-26T10:30:00Z",
  "insights": [
    {
      "type": "velocity_trend",
      "severity": "info",
      "title": "Velocity Increasing",
      "description": "Practice velocity up 1.3 mph/week over last 30 days. Facility sessions confirm trend with 1.5 mph/week improvement.",
      "recommendation": "Continue current training regimen. Consider adding weighted ball work to further increase velocity.",
      "data": {
        "practice_trend_mph_per_week": 1.3,
        "facility_trend_mph_per_week": 1.5,
        "confidence": 0.92
      }
    },
    {
      "type": "pitch_repertoire",
      "severity": "info",
      "title": "Developing Changeup",
      "description": "Changeup velocity gap improved from 8 mph to 5 mph over last 60 days. Good progress on deception.",
      "recommendation": "Continue changeup development. Current gap (5 mph) is approaching MLB average (6-8 mph).",
      "data": {
        "fastball_avg": 73.4,
        "changeup_avg": 68.2,
        "velocity_gap": 5.2,
        "historical_gap": 8.1
      }
    },
    {
      "type": "anomaly",
      "severity": "warning",
      "title": "Practice Velocity Drop",
      "description": "Home practice velocity dropped 3 mph in last week. Possible fatigue or mechanical change.",
      "recommendation": "Coach should check for fatigue, mechanical issues, or injury concerns in next facility session.",
      "data": {
        "recent_avg": 69.8,
        "baseline_avg": 72.5,
        "drop_mph": 2.7,
        "statistical_significance": 0.03 // p-value
      }
    }
  ]
}
```

**Purpose:** PitchTracker generates insights combining TAG practice data and PitchTracker facility data, sends back to TAG Sports app for athlete/parent viewing.

---

#### Webhooks (Real-Time Notifications)

**POST /webhooks/subscribe**
TAG Sports subscribes to athlete events

```http
POST /webhooks/subscribe
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "url": "https://api.tagsports.ai/webhooks/pitchtracker",
  "events": ["session.completed", "insight.generated", "anomaly.detected"],
  "athlete_ids": ["pt_athlete_xyz789"] // or ["*"] for all linked athletes
}

Response:
{
  "subscription_id": "sub_abc123",
  "webhook_url": "https://api.tagsports.ai/webhooks/pitchtracker",
  "events": ["session.completed", "insight.generated", "anomaly.detected"],
  "status": "active"
}
```

**Webhook Payload (sent to TAG Sports when event occurs):**

```json
{
  "event": "insight.generated",
  "timestamp": "2026-03-26T10:35:00Z",
  "athlete_id": "pt_athlete_xyz789",
  "data": {
    "insight_type": "velocity_trend",
    "title": "Velocity Increasing",
    "description": "Practice velocity up 1.3 mph/week...",
    "severity": "info",
    "action_url": "https://app.pitchtracker.io/athletes/pt_athlete_xyz789/insights"
  }
}
```

**Use Case:** When PitchTracker detects anomaly or generates insight, TAG Sports app shows push notification to athlete ("New insight from your facility training!")

---

## 4. Athlete Profile Service

### Unified Identity Model

**Challenge:** Athletes have TAG Sports account (tag_user_id) and PitchTracker profile (pitcher_id). Need to link them.

**Solution:** Cloud-based athlete profile service that maps TAG user ID ↔ PitchTracker profile ID.

### Profile Linking Flow

**Step 1: Athlete Links Accounts (One-Time)**

**In TAG Sports App:**
1. Navigate to Settings → Integrations
2. Tap "Connect to PitchTracker"
3. OAuth flow: Redirect to PitchTracker login page
4. Athlete logs in (or creates PitchTracker account)
5. Consent screen: "Allow TAG Sports to sync practice data to PitchTracker?"
6. Approve → Accounts linked

**Backend (OAuth Flow):**
```
TAG Sports App
    |
    v
https://auth.pitchtracker.io/oauth/authorize?
    client_id=tag_sports&
    redirect_uri=tagsports://oauth/callback&
    scope=read:profile write:sessions&
    state=random_state_xyz
    |
    v
PitchTracker Login Page (web)
    |
    v
Athlete logs in / creates account
    |
    v
Consent screen ("Allow TAG Sports to sync data?")
    |
    v
Athlete approves
    |
    v
Redirect: tagsports://oauth/callback?code=AUTH_CODE&state=random_state_xyz
    |
    v
TAG Sports App exchanges code for access token
    |
    v
POST /auth/oauth/token
    |
    v
Access Token + Refresh Token stored in TAG app
    |
    v
Accounts linked (tag_user_id ↔ pt_athlete_id)
```

**Step 2: Automatic Sync (Ongoing)**

TAG Sports app automatically uploads practice sessions to PitchTracker cloud whenever:
- Session ends (immediate sync)
- App opened (background sync)
- Wi-Fi connected (batch sync)

---

### Profile Data Structure (Cloud)

**Unified Athlete Profile:**

```json
{
  "athlete_id": "pt_athlete_xyz789",
  "tag_user_id": "tag_abc123xyz",
  "linked_date": "2026-03-26T10:00:00Z",
  "consent": {
    "data_sharing": true,
    "marketing": false,
    "parent_email": "parent@example.com", // if under 13
    "consent_date": "2026-03-26T10:00:00Z"
  },
  "profile": {
    "name": "John Doe",
    "birth_year": 2010,
    "throws": "right",
    "position": "pitcher",
    "email": "john.doe@example.com"
  },
  "practice_stats": {
    "total_sessions_tag": 45,
    "total_pitches_tag": 1823,
    "avg_velocity_tag": 71.4,
    "last_practice_date": "2026-03-25",
    "practice_frequency": 3.2 // sessions/week
  },
  "facility_stats": {
    "total_sessions_pt": 12,
    "total_pitches_pt": 624,
    "avg_velocity_pt": 73.8,
    "facilities_visited": ["Elite Baseball Academy", "Diamond Sports Complex"],
    "last_facility_session": "2026-03-22"
  },
  "combined_insights": {
    "velocity_trend_mph_per_week": 1.3,
    "practice_to_facility_velocity_gap": 2.4, // mph faster at facility
    "repertoire": ["Fastball", "Changeup", "Curveball"],
    "development_phase": "improving" // improving, plateau, declining
  }
}
```

---

## 5. Real-Time Streaming Protocol

### WebSocket for Live Data (Facility PC ↔ Cloud)

**Use Case:** During facility session, PitchTracker desktop app streams data to cloud in real-time. TAG Sports mobile app (if athlete has it open) receives live updates.

**WebSocket URL:** `wss://stream.pitchtracker.io/v1/live`

**Connection Flow:**
```javascript
// PitchTracker Desktop App
const ws = new WebSocket('wss://stream.pitchtracker.io/v1/live');

ws.on('open', () => {
  ws.send(JSON.stringify({
    action: 'authenticate',
    token: 'JWT_ACCESS_TOKEN',
    session_id: 'pt_session_001',
    athlete_id: 'pt_athlete_xyz789'
  }));
});

ws.on('message', (data) => {
  const message = JSON.parse(data);
  if (message.type === 'authenticated') {
    console.log('WebSocket authenticated, streaming enabled');
  }
});

// Stream pitch data
function onPitchDetected(pitch) {
  ws.send(JSON.stringify({
    action: 'pitch_data',
    timestamp: pitch.timestamp,
    speed_mph: pitch.speed_mph,
    movement_h: pitch.run_in,
    movement_v: pitch.rise_in,
    location: {zone_row: 1, zone_col: 2},
    is_strike: true
  }));
}
```

**TAG Sports Mobile App (Receiving Live Updates):**
```javascript
// TAG Sports App listening for athlete's facility session
const ws = new WebSocket('wss://stream.pitchtracker.io/v1/live');

ws.on('open', () => {
  ws.send(JSON.stringify({
    action: 'subscribe',
    token: 'TAG_OAUTH_TOKEN',
    athlete_id: 'pt_athlete_xyz789'
  }));
});

ws.on('message', (data) => {
  const pitch = JSON.parse(data);
  if (pitch.type === 'pitch_data') {
    // Display live pitch in TAG app (parent watching from home)
    updateLiveSession(pitch);
  }
});
```

**Value:** Parents/coaches can watch live facility session from TAG Sports app even if not physically present.

---

## 6. Bidirectional Data Flow

### TAG Sports → PitchTracker (Practice Data)

**What Flows:**
- Session date/time
- Pitch count
- Velocity measurements
- Athlete-tagged pitch types
- Practice notes

**When:**
- Manual export/import (MVP)
- Automatic cloud sync (Phase 2)
- Real-time during session (Phase 3 - if TAG device at facility)

**Purpose:** Coaches see athlete's home practice baseline before facility session.

---

### PitchTracker → TAG Sports (Coaching Insights)

**What Flows Back:**
- **AI Coaching Insights** (from PitchTracker pattern detection)
  - Velocity trends
  - Pitch repertoire analysis
  - Anomaly detection (fatigue, mechanical issues)
  - Baseline comparison
- **3D Trajectory Data** (simplified for mobile viewing)
  - Movement charts (break/rise)
  - Strike zone heat maps
  - Pitch location visualizations
- **Coaching Notes** (from facility coaches)
  - Session summaries
  - Technique feedback
  - Development recommendations

**When:**
- After facility session ends → insights appear in TAG Sports app
- Weekly summary → sent via push notification
- Anomaly detected → immediate notification

**Purpose:** Athletes get professional coaching insights in their TAG Sports app (value add for TAG Sports users).

---

### Insight Flow Example

**Scenario:**
1. **Monday:** Athlete practices at home with TAG Sports (45 pitches, avg 71 mph)
2. **Tuesday:** Athlete practices at home (48 pitches, avg 72 mph)
3. **Wednesday:** Athlete has facility session with PitchTracker (52 pitches, avg 74 mph)
4. **Wednesday Evening:** PitchTracker pattern detection runs, generates insight
5. **Thursday Morning:** TAG Sports app shows push notification:

```
┌────────────────────────────────────┐
│  🎯 New Insight from Your Coach   │
├────────────────────────────────────┤
│  Velocity Improving!               │
│                                    │
│  Your practice sessions this week  │
│  averaged 71.5 mph. Your facility  │
│  session hit 74 mph.               │
│                                    │
│  Coach's note: "Great mechanics    │
│  improvement this week. Keep       │
│  focusing on lower half drive."    │
│                                    │
│  [View Full Analysis]              │
└────────────────────────────────────┘
```

**Value:**
- **For Athlete:** Professional insights delivered to their TAG Sports app (familiar interface)
- **For TAG Sports:** More valuable to users (not just data collection, but professional analysis)
- **For Facility:** Touchpoint between sessions (athlete stays engaged)

---

## 7. Security & Authentication

### OAuth 2.0 Flow (TAG Sports ↔ PitchTracker)

**Grant Type:** Authorization Code with PKCE (Proof Key for Code Exchange)
**Token Lifetime:** 1 hour (access token), 30 days (refresh token)
**Scopes:**
- `read:profile` - Read athlete profile
- `write:sessions` - Upload session data
- `read:sessions` - Read session history
- `read:insights` - Read coaching insights
- `write:insights` - Post coaching notes (facility side)

### API Authentication

**All API requests require Bearer token:**

```http
GET /athletes/pt_athlete_xyz789
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Token Refresh:**
```http
POST /auth/oauth/token
Content-Type: application/json

{
  "grant_type": "refresh_token",
  "refresh_token": "REFRESH_TOKEN_HERE",
  "client_id": "tag_sports_integration"
}

Response:
{
  "access_token": "NEW_ACCESS_TOKEN",
  "expires_in": 3600,
  "refresh_token": "NEW_REFRESH_TOKEN" // rotated
}
```

---

### Data Encryption

**In Transit:**
- All API calls over HTTPS (TLS 1.3)
- WebSocket connections over WSS (secure WebSocket)
- Bluetooth data encrypted (BLE Secure Connections)

**At Rest:**
- Athlete data encrypted in cloud database (AES-256)
- Session data encrypted
- Access logs encrypted

**Compliance:**
- HIPAA not required (performance data, not health data)
- COPPA compliance (parental consent for <13)
- GDPR compliance (EU athletes can request deletion)
- CCPA compliance (California athletes have enhanced rights)

---

### Access Control

**Role-Based Access Control (RBAC):**

| Role | Permissions |
|------|------------|
| **Athlete** | Read own profile, sessions, insights; Write practice notes |
| **Parent** | Read child's profile, sessions, insights (if child <18) |
| **Facility Coach** | Read athlete profile (if enrolled); Write coaching notes, insights |
| **Facility Admin** | Manage facility settings, athlete enrollments |
| **TAG Sports (API)** | Write sessions (upload practice data); Read insights (for app display) |
| **PitchTracker (API)** | Write facility sessions; Read TAG practice data; Write insights |

**Data Isolation:**
- Athletes only see their own data (or children if parent)
- Coaches only see enrolled athletes' data
- Facilities can't see other facilities' data
- Cross-facility data sharing requires athlete consent

---

## 8. Implementation Phases

### Phase 1: Manual Export/Import (Months 1-3)
**Status:** MVP - Defined in TAG_INTEGRATION_TECHNICAL_SPEC.md

**Features:**
- TAG Sports app: "Export to PitchTracker" button
- PitchTracker: "Import TAG Sports Data" dialog
- Manual file transfer (email, USB, cloud link)

**Effort:** 2-4 weeks (both sides)
**Risk:** Low (simple, no cloud infrastructure)

---

### Phase 2: Cloud Sync (Months 4-6)

**Features:**
- **Athlete Profile Service** (unified identity)
  - OAuth 2.0 account linking
  - Cloud-hosted athlete profiles
  - Automatic data sync (TAG → cloud → PitchTracker)
- **Session Storage Service**
  - TAG practice sessions auto-upload to cloud
  - PitchTracker facilities auto-pull from cloud
- **Basic Insights** (velocity trends, session summaries)

**Infrastructure:**
- Cloud hosting (AWS, GCP, or Azure)
- PostgreSQL database (athlete profiles, sessions)
- Redis cache (real-time data)
- S3 storage (session files, video links)

**Effort:** 8-12 weeks (backend + both clients)
**Cost:** $100-300/month cloud hosting (scales with users)
**Risk:** Medium (cloud infrastructure, privacy/security)

---

### Phase 3: Live PC Ingest (Months 7-9)

**Features:**
- **Bluetooth PC Integration** (TAG device → facility PC)
  - Real-time pitch data streaming
  - Dual-mode TAG operation (mobile app OR PC)
  - Cross-validation (TAG velocity vs. PitchTracker stereo velocity)
- **WebSocket Streaming** (facility PC → cloud → TAG mobile app)
  - Parents watch live facility sessions from TAG app
  - Real-time pitch notifications

**Hardware:**
- Facility PC needs Bluetooth adapter (if not built-in)
- TAG Sports firmware update (support PC pairing mode)

**Effort:** 6-8 weeks (BLE protocol, firmware coordination)
**Risk:** Medium-High (hardware dependencies, TAG firmware changes)

---

### Phase 4: Bidirectional Insights (Months 10-12)

**Features:**
- **AI Insights Flow Back to TAG App**
  - PitchTracker pattern detection runs on combined dataset
  - Insights appear in TAG Sports app (push notifications)
  - Coaching notes from facilities visible to athletes
- **Webhook Integration**
  - Real-time notifications (session complete, anomaly detected)
  - TAG Sports can react to PitchTracker events
- **Advanced Analytics**
  - Combine TAG practice + PitchTracker facility data
  - Predictive models (ML using integrated dataset)
  - Development trajectory forecasting

**Effort:** 8-12 weeks (analytics engine, webhook infrastructure)
**Risk:** Medium (complex data flows, ML models)

---

### Phase 5: Unified Mobile App (2027+)

**Features:**
- **Co-developed Mobile App** (TAG Sports + PitchTracker joint product)
  - Connects to TAG device via Bluetooth (home practice)
  - Connects to PitchTracker facilities via API (facility booking, data viewing)
  - Single app for all pitch tracking needs
- **Facility Marketplace**
  - Find facilities near you (map search)
  - Book sessions directly
  - Pay through app
- **Social Features**
  - Share progress with teammates
  - Compare stats (opt-in)
  - Coaching marketplace (find coaches)

**Effort:** 6-12 months (full mobile app development)
**Risk:** High (requires deep business alignment, revenue sharing)

---

## 9. Use Cases & Workflows

### Use Case 1: Hybrid Session (TAG Device as Secondary Velocity Source)

**Scenario:** Athlete brings TAG Sports device to PitchTracker facility. Facility has stereo cameras (primary) and TAG device (secondary for velocity cross-validation).

**Workflow:**
1. **Pre-Session (2 minutes)**
   - Operator opens PitchTracker session
   - Clicks "Connect TAG Sports Device"
   - PitchTracker scans for nearby TAG devices via Bluetooth
   - Selects athlete's TAG device from list
   - TAG device pairs with facility PC

2. **During Session (30-60 minutes)**
   - Athlete throws pitches
   - PitchTracker cameras track 3D trajectory, movement, location
   - TAG device measures velocity (redundant measurement)
   - **Both systems send data to PitchTracker simultaneously**
   - PitchTracker UI shows:
     - Stereo camera velocity: 73.2 mph
     - TAG device velocity: 72.9 mph
     - Difference: 0.3 mph ✅ (agreement validates accuracy)

3. **Post-Session (5 minutes)**
   - Session ends, TAG device disconnects
   - PitchTracker uploads session to cloud
   - TAG Sports app syncs and shows new facility session
   - Athlete sees in TAG app: "Facility session today: 52 pitches, 73.8 mph avg, +1.4 mph vs. home practice"

**Benefits:**
- **Cross-validation:** Two independent velocity measurements (builds trust)
- **Convenience:** Athlete doesn't need two separate devices
- **Data quality:** Catch calibration drift (if TAG and cameras disagree, recalibrate)

---

### Use Case 2: Practice-to-Facility Continuity

**Scenario:** Athlete practices at home Monday-Thursday with TAG Sports. Visits PitchTracker facility Friday. Coach wants to see practice trends.

**Workflow:**
1. **Monday-Thursday (Home Practice)**
   - Athlete uses TAG Sports device + mobile app
   - 4 practice sessions, 180 total pitches
   - TAG app auto-syncs to cloud (if accounts linked)

2. **Friday (Facility Session)**
   - Athlete arrives at facility
   - Operator selects athlete from roster
   - PitchTracker pulls practice history from cloud
   - **Coach Dashboard shows:**
     ```
     John Doe - Practice Activity This Week
     ────────────────────────────────────────
     Mon: 45 pitches, 71.2 mph avg (Backyard)
     Tue: 48 pitches, 72.1 mph avg (Cage)
     Wed: 42 pitches, 71.8 mph avg (Backyard)
     Thu: 45 pitches, 72.5 mph avg (Cage)

     Trend: +0.4 mph/day (improving)
     Volume: 180 pitches this week (good)

     💡 Coaching Note: Velocity trending up.
     Expect 73-74 mph today with proper warmup.
     ```

3. **During Facility Session**
   - Coach sees real-time velocity: 73.2, 74.1, 73.8 mph
   - Confirms trend (practice improvement translating to facility)
   - Adjusts coaching based on practice data (knows athlete worked on changeup, can focus on that)

4. **After Session**
   - PitchTracker uploads facility session
   - TAG Sports app shows notification: "Facility session complete! +1.4 mph vs. practice average"
   - Athlete views detailed 3D trajectory data in TAG app (sourced from PitchTracker)

**Benefits:**
- Coach has context before session starts
- Athlete sees continuity (practice → facility progression)
- No manual data transfer required

---

### Use Case 3: Parent Monitoring (Live Updates)

**Scenario:** Parent purchased TAG Sports for child ($230). Child enrolled in PitchTracker facility. Parent wants to monitor facility sessions remotely.

**Workflow:**
1. **Setup (One-Time)**
   - Parent links TAG Sports app to child's PitchTracker profile (parental access)
   - Grants permission to receive live updates

2. **During Facility Session (Child Throwing)**
   - Child at facility, throwing pitches (tracked by PitchTracker)
   - Parent at home/work with TAG Sports app open
   - **Parent's TAG Sports app shows live feed:**
     ```
     📍 Live Session - Elite Baseball Academy
     ────────────────────────────────────────
     Started: 4:15 PM (23 minutes ago)

     Pitches: 18
     Avg Velocity: 73.4 mph
     Max Velocity: 76.2 mph
     Strikes: 14/18 (78%)

     Latest Pitch:
     ⚡ 74.1 mph - Strike (high inside)

     [View Full Session] [End Updates]
     ```

3. **Post-Session**
   - Parent receives summary notification
   - Views detailed analysis (3D trajectory, movement, coaching notes)
   - All data visible in familiar TAG Sports app interface

**Benefits:**
- **For Parents:** Stay connected to child's training (don't need separate PitchTracker account)
- **For TAG Sports:** Increased app engagement (parents open app during facility sessions)
- **For Facility:** Transparency builds trust with parents

---

### Use Case 4: Multi-Facility Portability

**Scenario:** Athlete travels to different facilities (tournaments, camps, private coaching). Each facility uses PitchTracker. Athlete's data follows them.

**Workflow:**
1. **Facility A (Home Facility):**
   - Athlete enrolled, practice data imported
   - 20 sessions over 3 months
   - Baseline established: 72 mph avg

2. **Facility B (Tournament):**
   - Athlete visits for weekend tournament
   - Facility B operator selects athlete from cloud roster
   - **Athlete's full history visible:**
     - TAG Sports practice data (45 sessions)
     - Facility A sessions (20 sessions)
     - Combined baseline: 72.3 mph, repertoire: FB/CH/CB
   - Tournament session recorded at Facility B
   - Data syncs back to cloud

3. **Facility C (Private Coaching):**
   - Athlete works with private coach (uses PitchTracker)
   - Coach pulls athlete's history from cloud
   - Sees practice (TAG), Facility A, Facility B data
   - Coaching notes added: "Focus on changeup consistency"

4. **Back to Facility A:**
   - Home facility coach sees updates from tournament and private coaching
   - Continuity preserved across all training contexts

**Benefits:**
- **For Athlete:** Data portability (history follows them everywhere)
- **For Facilities:** Don't lose data when athlete trains elsewhere (ecosystem lock-in)
- **For TAG Sports:** More valuable to users (practice data + facility data in one place)

---

## 10. Infrastructure Requirements

### Cloud Platform Architecture

**Hosting:** AWS, GCP, or Azure (recommended: AWS for maturity)

**Components:**

1. **API Gateway** (AWS API Gateway or Kong)
   - REST API routing
   - Rate limiting (1000 req/hour per API key)
   - Authentication (JWT validation)
   - Request logging

2. **Application Servers** (AWS ECS or EC2)
   - Node.js or Python (FastAPI) backend
   - Horizontal scaling (auto-scale with load)
   - Health checks and monitoring

3. **Database** (AWS RDS - PostgreSQL)
   - Athlete profiles
   - Session data
   - Insights and analytics
   - Access control (RBAC)

4. **Cache** (AWS ElastiCache - Redis)
   - Session data (hot data)
   - API response caching
   - Real-time leaderboards

5. **Object Storage** (AWS S3)
   - Session export files
   - Video links (if applicable)
   - Report PDFs

6. **WebSocket Server** (AWS API Gateway WebSocket or custom)
   - Real-time streaming
   - Live session updates
   - Push notifications

7. **Message Queue** (AWS SQS or RabbitMQ)
   - Async processing (insights generation)
   - Webhook delivery
   - Background jobs

8. **Analytics Engine** (Separate service)
   - Pattern detection (PitchTracker's existing system)
   - Trend analysis
   - ML models (future)

---

### Cost Estimation (Cloud Infrastructure)

**Month 1-3 (Pilot - Low Volume):**
- API Gateway: $10/month (1M requests)
- Application Servers: $50/month (1× small instance)
- Database: $30/month (RDS small instance)
- Cache: $15/month (Redis small instance)
- Storage: $5/month (S3)
- **Total: ~$110/month**

**Month 6 (100 Facilities, 1,000 Athletes):**
- API Gateway: $50/month (5M requests)
- Application Servers: $200/month (2× medium instances)
- Database: $150/month (RDS medium instance)
- Cache: $50/month (Redis medium)
- Storage: $25/month (S3)
- **Total: ~$475/month**

**Year 1 (500 Facilities, 5,000 Athletes):**
- API Gateway: $200/month
- Application Servers: $600/month (4× large instances)
- Database: $500/month (RDS large)
- Cache: $150/month
- Storage: $100/month
- CDN: $50/month (CloudFront)
- **Total: ~$1,600/month = $19,200/year**

**Breakeven:** ~50-100 facilities (facility revenue covers infrastructure costs)

---

### Development Resources Required

**Phase 1 (MVP - Manual Export/Import):**
- Engineering: 1 developer × 2 weeks = 80 hours
- Testing/QA: 20 hours
- Documentation: 10 hours
- **Total: 110 hours (~$11,000 at $100/hour)**

**Phase 2 (Cloud Sync):**
- Backend: 1 developer × 8 weeks = 320 hours (API, database, auth)
- Frontend (PitchTracker): 1 developer × 2 weeks = 80 hours
- TAG Sports (their side): Estimated 2 weeks
- DevOps: 40 hours (cloud setup, CI/CD)
- Testing/QA: 60 hours
- Documentation: 20 hours
- **Total: 520 hours (~$52,000)**

**Phase 3 (Bluetooth PC Ingest):**
- Backend: 1 developer × 4 weeks = 160 hours (BLE protocol, streaming)
- Frontend (PitchTracker): 1 developer × 3 weeks = 120 hours
- TAG Sports (their side): Firmware update (estimated 4-6 weeks)
- Testing/QA: 60 hours (hardware testing, cross-platform)
- Documentation: 20 hours
- **Total: 360 hours (~$36,000)**

**Phase 4 (Bidirectional Insights):**
- Backend: 1 developer × 6 weeks = 240 hours (analytics, webhooks)
- TAG Sports (their side): App UI updates (estimated 2-3 weeks)
- Testing/QA: 40 hours
- Documentation: 20 hours
- **Total: 300 hours (~$30,000)**

**Total Investment (All Phases):** ~$129,000 + $19,200/year cloud hosting

**Partnership Cost Sharing:**
- PitchTracker: Backend infrastructure, API development ($80K-100K)
- TAG Sports: Mobile app integration, firmware updates ($30K-50K)
- **Shared:** Cloud hosting costs (split 50/50 or based on usage)

---

## API Specification Details

### REST API Endpoints (Complete List)

#### Authentication
- `POST /auth/oauth/authorize` - OAuth authorization endpoint
- `POST /auth/oauth/token` - Exchange code for access token
- `POST /auth/oauth/refresh` - Refresh access token
- `POST /auth/logout` - Revoke tokens

#### Athletes
- `POST /athletes` - Create athlete profile (link TAG user ID)
- `GET /athletes/{athlete_id}` - Get athlete profile
- `PUT /athletes/{athlete_id}` - Update athlete profile
- `DELETE /athletes/{athlete_id}` - Delete athlete profile (GDPR compliance)
- `GET /athletes/{athlete_id}/sessions` - Get session history (TAG + PitchTracker)
- `GET /athletes/{athlete_id}/insights` - Get AI-generated insights
- `GET /athletes/{athlete_id}/stats` - Get aggregate statistics

#### Sessions
- `POST /sessions` - Upload session (TAG Sports or PitchTracker)
- `GET /sessions/{session_id}` - Get session details
- `PUT /sessions/{session_id}` - Update session (add notes, tags)
- `DELETE /sessions/{session_id}` - Delete session
- `GET /sessions/{session_id}/pitches` - Get pitch-by-pitch data
- `POST /sessions/{session_id}/insights` - Generate insights for session

#### Facilities
- `POST /facilities` - Register facility (PitchTracker installation)
- `GET /facilities/{facility_id}` - Get facility details
- `GET /facilities/search` - Search facilities (lat/lon, radius)
- `GET /facilities/{facility_id}/athletes` - Get enrolled athletes
- `POST /facilities/{facility_id}/athletes/{athlete_id}` - Enroll athlete
- `DELETE /facilities/{facility_id}/athletes/{athlete_id}` - Unenroll athlete

#### Insights
- `POST /insights/generate` - Trigger insight generation (pattern detection)
- `GET /insights/{insight_id}` - Get specific insight
- `POST /insights/{insight_id}/feedback` - Provide feedback (helpful/not helpful)

#### Webhooks
- `POST /webhooks/subscribe` - Subscribe to events
- `GET /webhooks/subscriptions` - List active subscriptions
- `DELETE /webhooks/subscriptions/{sub_id}` - Unsubscribe
- `POST /webhooks/test` - Test webhook endpoint

#### Admin (Internal Only)
- `GET /admin/stats` - Platform statistics (users, sessions, revenue)
- `GET /admin/health` - System health check
- `POST /admin/analytics/run` - Trigger batch analytics job

---

### WebSocket Events (Real-Time Streaming)

**Client → Server:**
- `authenticate` - Authenticate WebSocket connection
- `subscribe` - Subscribe to athlete's live sessions
- `unsubscribe` - Unsubscribe from updates
- `ping` - Keep-alive ping

**Server → Client:**
- `authenticated` - Authentication successful
- `pitch_data` - New pitch detected
- `session_started` - Session began
- `session_ended` - Session ended
- `insight_generated` - New insight available
- `error` - Error occurred
- `pong` - Response to ping

**Example WebSocket Message:**
```json
{
  "type": "pitch_data",
  "timestamp": "2026-03-26T15:23:45.123Z",
  "session_id": "pt_session_001",
  "athlete_id": "pt_athlete_xyz789",
  "pitch": {
    "pitch_number": 23,
    "speed_mph": 73.4,
    "movement_h": 8.2,
    "movement_v": -2.1,
    "location": {"zone_row": 1, "zone_col": 2},
    "is_strike": true,
    "sources": {
      "pitchtracker_camera": 73.2,
      "tag_device": 73.4
    }
  }
}
```

---

## Bluetooth Integration UI (PitchTracker)

### TAG Device Connection Panel

**Location:** Coaching window, right sidebar (optional panel)

**UI Mock:**
```
┌────────────────────────────────────┐
│  TAG Sports Device                 │
├────────────────────────────────────┤
│  Status: ⚪ Not Connected          │
│                                    │
│  [Scan for Devices]                │
│                                    │
│  Nearby Devices:                   │
│  ○ TAG_12345ABC (John Doe)         │
│  ○ TAG_67890DEF (Jane Smith)       │
│                                    │
│  [Connect Selected]                │
└────────────────────────────────────┘

(After connection)

┌────────────────────────────────────┐
│  TAG Sports Device                 │
├────────────────────────────────────┤
│  Status: ✅ Connected              │
│                                    │
│  Device: TAG_12345ABC              │
│  Athlete: John Doe                 │
│  Battery: 85%                      │
│  Signal: ████░ Strong              │
│                                    │
│  Live Data:                        │
│  ┌──────────────────────────────┐ │
│  │ Pitch #18: 73.4 mph          │ │
│  │ PitchTracker: 73.2 mph       │ │
│  │ Difference: 0.2 mph ✅       │ │
│  └──────────────────────────────┘ │
│                                    │
│  [Disconnect]    [Settings]       │
└────────────────────────────────────┘
```

**Settings Dialog:**
- Enable/disable TAG device integration
- Select measurement mode (peak velocity vs. release velocity)
- Configure auto-pairing (remember this device)
- Calibration offset (if TAG consistently reads +/- X mph, adjust)

---

### Cross-Validation Dashboard

**When TAG device and PitchTracker cameras both active:**

```
┌────────────────────────────────────────────────────┐
│  Velocity Cross-Validation (TAG + PitchTracker)   │
├────────────────────────────────────────────────────┤
│                                                    │
│  Pitch #  │  TAG Device  │  PitchTracker  │  Δ   │
│  ─────────┼──────────────┼────────────────┼───── │
│     15    │   72.1 mph   │    71.9 mph    │ 0.2  │
│     16    │   73.8 mph   │    73.5 mph    │ 0.3  │
│     17    │   72.4 mph   │    72.6 mph    │ 0.2  │
│     18    │   74.1 mph   │    73.2 mph    │ 0.9  │ ⚠️
│     19    │   73.3 mph   │    73.1 mph    │ 0.2  │
│                                                    │
│  Session Average Difference: 0.36 mph ✅          │
│  Max Difference: 0.9 mph (Pitch #18)              │
│  Agreement Rate: 100% (within ±1.5 mph)           │
│                                                    │
│  💡 Calibration Status: EXCELLENT                 │
│  Both systems showing strong agreement.           │
└────────────────────────────────────────────────────┘
```

**Purpose:**
- Validate PitchTracker accuracy in real-time (TAG device is reference)
- Build user trust (two independent measurements agree)
- Catch calibration drift early (if systems diverge >1.5 mph, recalibrate)

---

## Partnership Value Proposition (Enhanced)

### For TAG Sports (Why This is Better Than MVP)

**MVP (Manual Export/Import):**
- One-way data flow (TAG → PitchTracker)
- Manual athlete action required
- No real-time updates
- Limited value add for TAG users

**Deep Integration (Bluetooth + Cloud API):**
- ✅ **Bidirectional data flow** (PitchTracker insights flow back to TAG app)
- ✅ **Real-time updates** (parents watch facility sessions live in TAG app)
- ✅ **Dual-mode TAG device** (works at home AND at facility)
- ✅ **Professional backend** (TAG Sports elevated to enterprise-grade platform)
- ✅ **Network effects** (more facilities → more valuable to TAG users → more TAG sales)
- ✅ **Revenue diversification** (referrals + bundles + data licensing)

**Competitive Moat:** Pocket Radar, Bushnell can't match this (no facility integration, no cloud platform, no bidirectional insights)

---

### For PitchTracker (Why This is Better Than MVP)

**MVP:**
- Qualified leads from TAG users
- Manual data import (friction)
- One-way value flow

**Deep Integration:**
- ✅ **Real-time ingest** (TAG device streams to facility PC)
- ✅ **Cross-validation** (TAG velocity validates PitchTracker accuracy)
- ✅ **Exclusive integration** (competitive moat vs. Rapsodo/TrackMan)
- ✅ **Cloud platform** (enables future features: multi-facility, mobile app, analytics)
- ✅ **Data enrichment** (TAG practice data improves PitchTracker insights)

**Strategic Positioning:** PitchTracker becomes the **professional data platform** for serious baseball/softball training, not just a facility tool.

---

### For Athletes (Why This Matters)

**MVP:**
- Some data continuity (if they remember to export/import)
- Better coaching (coach sees practice baseline)

**Deep Integration:**
- ✅ **Seamless experience** (data flows automatically, no athlete action)
- ✅ **Single device** (TAG works at home AND at facility)
- ✅ **Live updates** (parents watch facility sessions from TAG app)
- ✅ **Professional insights** (PitchTracker analysis appears in TAG app)
- ✅ **Data portability** (history follows them to any PitchTracker facility)
- ✅ **Complete picture** (practice + facility in one place)

**Ecosystem Lock-In:** Athletes invested in TAG device + PitchTracker facilities unlikely to switch to competing products.

---

## Implementation Roadmap (Revised)

### Phase 1: Manual Export/Import (Months 1-3) - FOUNDATION
**Effort:** 2-4 weeks
**Cost:** $11,000
**Risk:** Low

**Deliverables:**
- TAG Sports: "Export to PitchTracker" button
- PitchTracker: "Import TAG Sports Data" dialog
- Data format spec (JSON schema)

---

### Phase 2: Cloud Platform MVP (Months 4-6) - INFRASTRUCTURE
**Effort:** 8-12 weeks
**Cost:** $52,000 + $100-300/month hosting
**Risk:** Medium

**Deliverables:**
- Athlete profile service (unified identity, OAuth)
- Session storage service (auto-sync)
- REST API (core endpoints)
- TAG Sports app: Auto-sync to cloud
- PitchTracker app: Pull from cloud

---

### Phase 3: Bluetooth PC Ingest (Months 7-9) - DEEP INTEGRATION
**Effort:** 6-8 weeks
**Cost:** $36,000
**Risk:** Medium-High

**Deliverables:**
- BLE service specification (TAG firmware support)
- PitchTracker Bluetooth integration (PC side)
- Cross-validation dashboard (TAG vs. PitchTracker velocity)
- Dual-mode TAG operation (mobile OR PC)

**Dependencies:**
- TAG Sports firmware update (requires their hardware team)
- Bluetooth adapter on facility PCs (most modern PCs have built-in)

---

### Phase 4: Bidirectional Insights (Months 10-12) - VALUE MULTIPLICATION
**Effort:** 8-12 weeks
**Cost:** $30,000
**Risk:** Medium

**Deliverables:**
- Insights engine (PitchTracker pattern detection on combined dataset)
- Webhook service (real-time notifications)
- TAG Sports app: Display PitchTracker insights
- Push notifications (anomalies, coaching notes)
- Live session viewing in TAG app

---

### Phase 5: Unified Mobile App (2027) - FULL ECOSYSTEM
**Effort:** 6-12 months
**Cost:** $150,000-300,000
**Risk:** High

**Deliverables:**
- Co-developed mobile app (TAG Sports + PitchTracker)
- Facility marketplace (find, book, pay)
- Social features (share progress, compare)
- Unified experience (one app for home + facility)

---

## Capability Contract Evaluation

### Does Deep Integration Pass Contract?

**1. User Value:** ✅
- Solves real problem: Data continuity, live updates, cross-validation
- Evidence of demand: TAG's 10K users + facility coaches want practice context
- Repeatable: Used every session (if TAG device present)

**2. Evidence & Validation:** ✅
- Easy to validate (does data sync work?)
- Cross-validation feature (TAG vs. PitchTracker velocity agreement)
- Measurable success (sync rate, accuracy agreement)

**3. Workflow Fit:** ✅
- Pre-session: Link athlete account (one-time setup)
- During session: TAG device streams data (optional, adds value)
- Post-session: Insights flow back to TAG app (no athlete action)

**4. Setup Impact:** ✅
- Phase 1: No impact (manual import is optional)
- Phase 2: Improves setup (auto-sync eliminates manual step)
- Phase 3: Minimal impact (Bluetooth pairing is optional convenience)

**5. Architectural Fit:** ✅
- Clean service layer (new TagSportsIntegrationService)
- Versioned contract (JSON schema v1.0)
- UI/backend separation (BLE service, cloud API)

**6. Supportability:** ✅
- Well-defined API (documented, testable)
- Clear error messages ("TAG device not found", "Sync failed: retry?")
- Self-service (athletes link accounts themselves)

**7. Commercial Relevance:** ✅
- Directly serves facility market (TAG integration attracts users)
- Differentiates vs. Rapsodo/TrackMan (unique integration)
- Compounds value (exclusive partnership creates moat)

**8. Release Readiness:** ✅
- Phased rollout (MVP → Cloud → Bluetooth → Insights)
- Each phase has clear scope, validation, documentation
- Pilot before scaling (5-10 facilities test each phase)

**SCORE: 88/100** (Strong Candidate - High Priority)

**Decision:** ✅ **APPROVED FOR DEVELOPMENT** (pending TAG Sports MOU)

---

## Next Steps

### Immediate (This Week)
1. **Finalize TAG Sports outreach**
   - Include deep integration vision in partnership proposal
   - Emphasize Bluetooth PC ingest as differentiator
   - Position as "professional backend platform" (not just data export)

2. **Prepare technical demo**
   - Mock Bluetooth connection (simulated TAG device)
   - Show cross-validation dashboard UI
   - Demonstrate value proposition visually

### Short-Term (Weeks 2-4)
3. **Discovery call with TAG Sports**
   - Present deep integration architecture
   - Discuss technical feasibility (Bluetooth, firmware, cloud)
   - Align on phased approach (MVP → Cloud → Bluetooth → Insights)

4. **Technical alignment meeting**
   - TAG Sports engineering team + PitchTracker engineering
   - Review API spec, BLE protocol, data format
   - Identify technical challenges and dependencies

5. **Sign MOU with development timeline**
   - Phase 1: 2-4 weeks (manual export/import)
   - Phase 2: 8-12 weeks (cloud sync)
   - Phase 3: 6-8 weeks (Bluetooth PC ingest)
   - Phase 4: 8-12 weeks (bidirectional insights)

### Medium-Term (Months 2-6)
6. **Build Phase 1 (MVP)**
   - Manual export/import
   - Validate demand with 5-10 facilities

7. **Build Phase 2 (Cloud Platform)**
   - Athlete profile service
   - Session sync service
   - REST API

8. **Launch public beta**
   - 50-100 facilities
   - 500-1,000 athletes
   - Measure adoption, refine

### Long-Term (Months 7-12)
9. **Build Phase 3 (Bluetooth)**
   - PC ingest capability
   - Cross-validation dashboard
   - Dual-mode TAG operation

10. **Build Phase 4 (Bidirectional)**
    - Insights flow back to TAG app
    - Webhook notifications
    - Advanced analytics

---

**Document Status:** COMPLETE - Ready for TAG Sports partnership proposal
**Owner:** Engineering Lead + Platform Architect
**Next Action:** Include in TAG Sports outreach materials (enhanced value proposition)
**Created:** March 26, 2026
**Version:** 2.0 (Deep Integration Specification)
