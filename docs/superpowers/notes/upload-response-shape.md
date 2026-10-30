# Upload response shape (verified 2026-10-30, one real 1x1 PNG upload)

`POST https://capture-api.avada.io/api/v1/upload` → `200`, `application/json; charset=utf-8`:

```json
{"success": true, "url": "https://capture.avada.io/i/<id>", "imageId": "<id>", "width": 1, "height": 1, "bytes": 44}
```

Without a token: `401 {"error": "Missing access token"}`.
