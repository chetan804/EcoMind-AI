# EcoMind AI Mobile

Expo/React Native client using the same FastAPI backend and PostgreSQL data model as the web application.

## Run

```powershell
npm install
$env:EXPO_PUBLIC_API_URL='http://localhost:8000'
npm run start
```

The current mobile shell includes authenticated dashboard/report screens and uses the backend bearer-token contract. Camera upload, offline queues, push notifications, collector workflows, and device builds require platform credentials and are intentionally not represented as live until configured.
