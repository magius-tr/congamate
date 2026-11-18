# CongaMate

CongaMate is a custom Home Assistant integration for Cecotec Conga robot
vacuum cleaners.

CongaMate 0.2.0 is a modernization of the original BadConga project by
adrigzr, updated for current Home Assistant releases and tested with a
Cecotec Conga 3290.

## Origin and attribution

CongaMate is derived from the original BadConga project:

https://github.com/adrigzr/badconga

The Cecotec Conga protocol reverse engineering and the original
protobuf-based implementation come from BadConga and are credited to
adrigzr.

CongaMate modernization, current Home Assistant compatibility and Conga
3290 testing are maintained by Magius (@magius-tr).

See NOTICE.md for detailed project provenance.

The legacy protobuf namespace "badconga_proto" is intentionally preserved.
It is not a leftover from an incomplete rename.

## Tested hardware

CongaMate 0.2.0 has been directly tested with:

- Cecotec Conga 3290

Compatibility with other models inherited from the BadConga protocol
implementation has not yet been verified with CongaMate 0.2.0.

Community testing is welcome.

## Features

The tested Conga 3290 exposes a Home Assistant vacuum entity with:

- current robot state;
- start cleaning;
- stop cleaning;
- return to base;
- locate;
- suction/fan level selection;
- robot alias;
- cleaning mode;
- cleaning time and cleaned area;
- model, serial, firmware and controller revision;
- robot position and orientation;
- charging-base position.

The visible Home Assistant name follows the alias configured for the robot.
No robot-specific alias is hard-coded in CongaMate.

## Live map

CongaMate 0.2.0 can retrieve and render the Conga 3290 map directly in
Home Assistant.

The tested implementation supports:

- initial full map retrieval;
- live map updates while cleaning;
- an 800 x 800 map grid on the tested Conga 3290;
- robot position and orientation;
- charging-base position;
- known but not yet cleaned areas;
- cleaned areas;
- walls and map boundaries;
- map rendering as a native Home Assistant camera/image entity.

The camera entity is only a Home Assistant mechanism for exposing the
rendered map image. It does not imply that the robot contains a physical
camera.

During testing, CongaMate also successfully parsed:

- the map catalog returned by the robot;
- the active map;
- room IDs and names;
- cleaning plans associated with the map.

Those structures are currently read from the protocol but are not yet
exposed as Home Assistant management controls.

## Map-grid observations

On the tested Conga 3290, room cells were observed using room IDs such as:

- 10: room 10, not covered by the current cleaning state;
- 11: room 11, not covered;
- 12: room 12, not covered;
- 60: cleaned form of room 10;
- 61: cleaned form of room 11;
- 62: cleaned form of room 12.

The observed relationship is:

    cleaned_value = room_id + 50

This behavior is documented as an observation from the tested Conga 3290.
CongaMate does not assume without further testing that every compatible
model uses the same encoding.

## Configuration

CongaMate currently uses YAML configuration.

Credentials may be provided in YAML:

    congamate:
      email: "cecotec-account@example.com"
      password: "your-password"
      animate: false

Alternatively, CongaMate supports these environment variables:

    CONGA_EMAIL
    CONGA_PASSWORD

With those variables available to the Home Assistant process:

    congamate:
      animate: false

Do not publish account credentials, session information or tokens in issue
reports or logs.

## Cecotec sessions

The original BadConga project documented limitations when simultaneously
using the same Cecotec account from Home Assistant and the official app.

CongaMate has also observed session invalidation when the same account is
used concurrently.

A dedicated account for Home Assistant is therefore recommended where the
Cecotec account/device-sharing mechanism allows it.

## Installation

For manual installation, copy:

    custom_components/congamate

into:

    /config/custom_components/congamate

and restart Home Assistant.

The repository also contains HACS metadata. Distribution and installation
through HACS should be considered preliminary until the public CongaMate
repository has been validated end to end.

## Live map refresh

Since 0.2.1, live map updates invalidate the Home Assistant camera image
when a new map is pushed by the robot.

This makes Lovelace request the newly rendered map automatically while
cleaning, so robot movement and cleaning progress can be followed without
manual browser refresh or frontend polling.

## Roadmap

CongaMate already reads map, room and cleaning-plan structures from the
tested Conga 3290 protocol, but 0.2.0 does not yet provide controls for:

- selecting or switching maps;
- creating a new map or scenario;
- saving, renaming or deleting maps;
- splitting rooms;
- merging rooms;
- renaming rooms;
- starting cleaning for selected rooms;
- creating or modifying cleaning plans.

These functions require additional protocol analysis and testing before
they can be exposed safely.

## Licensing

The original BadConga repository does not appear to contain an explicit
software license or source-code licensing notice.

CongaMate does not attempt to retroactively assign a license to inherited
BadConga code.

See NOTICE.md for details.

## Version

Current release candidate:

    CongaMate 0.2.0

Tested directly with:

    Cecotec Conga 3290
