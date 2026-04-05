# Generated Client Contracts

Source folders:

- `client/newsly/newsly/Models/Generated`
- `client/newsly/OpenAPI/Generated`

## Purpose
Generated API contract artifacts synchronized from the backend schema for places where the client wants compile-time alignment with exported OpenAPI contracts.

## Runtime behavior
- Provides machine-generated request/response types instead of hand-maintained Swift models.
- Should be treated as generated output and regenerated from scripts rather than manually edited.

## Inventory scope
- Direct file inventory for generated Swift contract output directories.

## Modules and files
| File | Key symbols | Notes |
|---|---|---|
| `client/newsly/newsly/Models/Generated/APIContracts.generated.swift` | `enum APIContentType`, `enum APIContentStatus`, `enum APIContentClassification`, `enum APITaskType`, `enum APITaskStatus`, `enum APISummaryKind`, `enum APISummaryVersion` | Types: `enum APIContentType`, `enum APIContentStatus`, `enum APIContentClassification`, `enum APITaskType`, `enum APITaskStatus`, `enum APISummaryKind`, `enum APISummaryVersion` |
| `client/newsly/OpenAPI/Generated/Types.swift` | `Components`, `Operations`, generated request/response payload types | Generated from the checked-in OpenAPI document via `swift-openapi-generator`. |
| `client/newsly/OpenAPI/Generated/Client.swift` | `Client`, generated operation entrypoints | Generated from the checked-in OpenAPI document via `swift-openapi-generator`. |
