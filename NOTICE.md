# CongaMate: attribution and project provenance

CongaMate is a modernization of the original BadConga project by adrigzr.

The original BadConga project provided the foundation for CongaMate,
including the reverse engineering of the Cecotec Conga protocol and the
protobuf-based protocol implementation.

Original project:

https://github.com/adrigzr/badconga

Original protocol reverse engineering and BadConga implementation:

- adrigzr

CongaMate modernization, current Home Assistant compatibility, and
Conga 3290 testing:

- Magius (@magius-tr)

## About badconga_proto

The protobuf package name "badconga_proto" is intentionally preserved in
CongaMate.

This is NOT a leftover from an incomplete rename.

Keeping that namespace is a conscious decision:

- to preserve compatibility with the inherited protocol implementation;
- to document the technical provenance of the protobuf implementation;
- to explicitly acknowledge that the underlying reverse-engineering work
  originated in BadConga;
- to avoid presenting inherited protocol work as original CongaMate work.

The Home Assistant integration domain is "congamate".

Changing the "badconga_proto" package name requires regenerating
"schema_pb2.py" and fully retesting protocol parsing.

## Licensing note

The upstream BadConga repository does not appear to contain an explicit
software license or source-code licensing notice.

CongaMate therefore does not attempt to retroactively assign a license to
code inherited from BadConga.

Licensing of the complete derived project should be clarified with the
original author before an open-source license is assigned to all inherited
code.
