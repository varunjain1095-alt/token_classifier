# Review Classification Workbench

## Quick Start

### Option 1: Automatic Startup (Recommended)
```bash
# Windows Batch
start.bat

# OR PowerShell
.\start.ps1
```

### Option 2: Manual Startup

**Terminal 1 - Backend:**
```bash
cd "C:\Projects\Scraper token review and classification review project"
uvicorn src.api.main:app --host 0.0.0.0 --port 8020 --reload
```

**Terminal 2 - Frontend:**
```bash
cd "C:\Projects\Scraper token review and classification review project\frontend"
npm run dev
```

## Access URLs

- **Frontend**: http://localhost:3000
- **Backend**: http://localhost:8020
- **API Docs**: http://localhost:8020/docs

## Testing

Run the test script to verify everything works:
```bash
test.bat
```

## File Upload

The system accepts CSV, XLSX, and XLS files up to 50MB. Upload through the web interface at http://localhost:3000.

## Troubleshooting

### Port Already in Use
```bash
# Kill all Node processes
taskkill /F /IM node.exe

# Kill all Python processes
taskkill /F /IM python.exe
```

### File Upload Not Working
1. Check backend is running: http://localhost:8020/health
2. Check frontend proxy: http://localhost:3000/api/health
3. Check browser console for errors

### Redis Not Available
The system automatically falls back to in-memory sessions if Redis is not available.

## Features

- File upload (CSV, Excel)
- Database connection
- Field mapping
- Category configuration
- AI classification preview
- Results analysis
- Recommendations
- Full dataset processing
- Export functionality

## Dependencies

- Python 3.12+
- Node.js 18+
- PostgreSQL (optional, for database features)
- Redis (optional, for session persistence)
