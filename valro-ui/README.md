# Valro UI - React Frontend

Modern, responsive React frontend for the Valro home services concierge POC.

## Features

- ✅ Create home service tasks with natural language
- ✅ Real-time task status updates (3-second polling)
- ✅ View vendor contacts and quotes
- ✅ Activity timeline for each task
- ✅ Responsive design (mobile & desktop)
- ✅ Clean, modern UI with status badges

## Tech Stack

- **React 18** - UI framework
- **Vite** - Build tool & dev server
- **Native CSS** - No external CSS frameworks

## Quick Start

### Prerequisites

- Node.js 18+ (with npm)
- Lambda backend deployed with API Gateway URL

### Installation

```bash
# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Edit .env and add your API Gateway URL
# VITE_API_BASE=https://your-api-id.execute-api.us-east-1.amazonaws.com
```

### Development

```bash
# Start dev server (runs on http://localhost:3000)
npm run dev
```

### Build for Production

```bash
# Create optimized production build
npm run build

# Preview production build locally
npm run preview
```

The build output will be in the `dist/` directory.

## Environment Variables

Create a `.env` file in the project root:

```env
VITE_API_BASE=https://your-api-gateway-url.com
```

**Important:** Don't include a trailing slash in the URL.

## Deployment Options

### Option 1: AWS Amplify (Recommended)

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Add Valro UI"
   git push origin main
   ```

2. **Connect to Amplify:**
   - Go to AWS Amplify Console
   - Click "New app" → "Host web app"
   - Connect your GitHub repository
   - Select the `valro-ui` directory as the app root (if monorepo)

3. **Configure Build:**
   Amplify should auto-detect Vite. If not, use:
   ```yaml
   version: 1
   frontend:
     phases:
       preBuild:
         commands:
           - npm install
       build:
         commands:
           - npm run build
     artifacts:
       baseDirectory: dist
       files:
         - '**/*'
     cache:
       paths:
         - node_modules/**/*
   ```

4. **Add Environment Variable:**
   - In Amplify Console → App Settings → Environment variables
   - Add: `VITE_API_BASE` = `https://your-api-gateway-url.com`

5. **Deploy:**
   - Click "Save and deploy"
   - Your app will be live at: `https://branch-name.amplifyapp.com`

### Option 2: S3 + CloudFront

1. **Build the app:**
   ```bash
   npm run build
   ```

2. **Create S3 bucket:**
   ```bash
   aws s3 mb s3://valro-ui-bucket

   # Enable static website hosting
   aws s3 website s3://valro-ui-bucket --index-document index.html
   ```

3. **Upload build:**
   ```bash
   aws s3 sync dist/ s3://valro-ui-bucket --delete
   ```

4. **Create CloudFront distribution:**
   - Go to CloudFront console
   - Create distribution with S3 bucket as origin
   - Set default root object to `index.html`
   - Configure error pages (404 → index.html for client-side routing)

5. **Configure CORS:**
   Make sure your API Gateway has CORS enabled for the CloudFront domain.

### Option 3: Vercel

1. **Install Vercel CLI:**
   ```bash
   npm install -g vercel
   ```

2. **Deploy:**
   ```bash
   vercel
   ```

3. **Add environment variable:**
   ```bash
   vercel env add VITE_API_BASE
   ```

## Project Structure

```
valro-ui/
├── src/
│   ├── App.jsx           # Main app component with task management
│   ├── App.css           # Styles for App component
│   ├── main.jsx          # React entry point
│   └── index.css         # Global styles
├── index.html            # HTML template
├── vite.config.js        # Vite configuration
├── package.json          # Dependencies
├── .env.example          # Environment template
└── README.md            # This file
```

## Features Breakdown

### Task Sidebar
- Lists all tasks with status badges
- Color-coded status (blue=processing, green=completed, red=error)
- Click to view task details
- Highlights selected task

### Task Creator
- Textarea for task description
- Submit with button or Ctrl+Enter
- Loading state during creation
- Validation and error handling

### Task Detail View
- Full task description and status
- Created/updated timestamps
- Agent response display
- Vendors contacted (if any)
- Quotes received (if any)
- Activity timeline with events

### Real-time Updates
- Selected task polls every 3 seconds
- Automatically refreshes task state
- Shows live status changes

## API Integration

The frontend expects these endpoints:

- `POST /tasks` - Create new task
- `GET /tasks` - List all tasks
- `GET /tasks/{id}` - Get task details

See [lambda-backend/README.md](../lambda-backend/README.md) for API documentation.

## Development Tips

### Testing Without Backend

If you don't have the backend deployed yet, you can mock the API:

```javascript
// In App.jsx, replace fetch calls with:
const mockData = {
  tasks: [
    {
      id: "1",
      description: "Find a landscaper in Charlotte under $300",
      status: "completed",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      events: [
        { ts: new Date().toISOString(), message: "Task created", type: "info" }
      ]
    }
  ]
};
```

### Hot Module Replacement

Vite supports HMR out of the box. Changes to `.jsx` and `.css` files will update instantly.

### Browser DevTools

React Developer Tools extension is recommended:
- [Chrome](https://chrome.google.com/webstore/detail/react-developer-tools/fmkadmapgofadopljbjfkapdkoienihi)
- [Firefox](https://addons.mozilla.org/en-US/firefox/addon/react-devtools/)

## Troubleshooting

**CORS Errors:**
- Verify API Gateway has CORS enabled
- Check that Lambda returns proper CORS headers
- Use browser network tab to inspect preflight requests

**API Not Found:**
- Verify `VITE_API_BASE` is set correctly in `.env`
- Check API Gateway is deployed and accessible
- Test API directly with `curl` or Postman

**Build Errors:**
- Clear node_modules: `rm -rf node_modules && npm install`
- Clear Vite cache: `rm -rf node_modules/.vite`

**Polling Not Working:**
- Check browser console for errors
- Verify task ID is valid
- Ensure API returns proper JSON

## Performance

- Initial load: ~50KB (minified + gzipped)
- No external dependencies beyond React
- Optimized with Vite code splitting
- CSS is tree-shaken in production

## Browser Support

- Chrome/Edge (last 2 versions)
- Firefox (last 2 versions)
- Safari (last 2 versions)
- Mobile browsers (iOS Safari, Chrome Mobile)

## Future Enhancements

Possible improvements for production:

- [ ] WebSocket connection for real-time updates (replace polling)
- [ ] User authentication with Cognito
- [ ] Task filtering and search
- [ ] Export task history
- [ ] Dark mode toggle
- [ ] Notifications when quotes arrive
- [ ] Vendor ratings and reviews
- [ ] File attachments for tasks

## License

Part of the Valro POC project.
