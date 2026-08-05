# Maczoeker Migration Guide

This document describes how to set up the Maczoeker project on a new PC.

## Prerequisites

- Python 3.10+ installed
- Node.js 18+ and npm or yarn installed
- MongoDB running locally or accessible via connection string

## Steps to Set Up

### Step 1: Extract Archive

Extract `maczoeker-project.zip` to your desired location:

```bash
unzip maczoeker-project.zip
cd maczoeker
```

Or on Windows:
- Double-click the zip file
- Extract all files to a folder

### Step 2: Setup Backend (Python)

Navigate to the backend directory and create a virtual environment:

```bash
cd backend

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# or on Windows:
# .venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Setup Frontend (Node.js)

Navigate to the frontend directory:

```bash
cd ../frontend

# Install dependencies
npm install
# or if using yarn:
yarn install
```

### Step 4: Configure Environment Variables

#### Backend (.env)
Copy `.env.example` to `.env` and fill in your values:

```bash
cd backend
cp .env.example .env
# Edit .env with your configuration
nano .env  # or use any text editor
```

Required variables:
- `OPENAI_API_KEY` - Your OpenAI API key (optional)
- `MONGODB_URI` - MongoDB connection string (default: mongodb://localhost:27017)

#### Frontend (.env)
Copy `.env.example` to `.env`:

```bash
cd frontend
cp .env.example .env
```

### Step 5: Start MongoDB

Ensure MongoDB is running on your system. You can start it with:

```bash
# macOS with Homebrew
brew services start mongodb-community@7.0

# Or manually
mongod --dbpath /data/db
```

### Step 6: Run the Application

#### Option A: Using Makefile (Recommended)

From the project root:

```bash
# Start both backend and frontend
make dev

# Or start individually:
make backend-dev   # Start only backend
make frontend-dev  # Start only frontend
```

#### Option B: Manual Start

**Backend:**
```bash
cd backend
source .venv/bin/activate
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm start
# or
yarn start
```

The application will be available at `http://localhost:3000` (frontend) with the backend API at `http://localhost:8000`.

## Files Excluded from Archive

The archive excludes the following directories to keep it small:
- `.venv/` - Python virtual environment
- `node_modules/` - NPM dependencies
- `.git/` - Git repository (you should initialize a new repo on the target machine)

These will be recreated when you run the setup steps above.

## Troubleshooting

### MongoDB Connection Issues
- Ensure MongoDB is running: `mongosh --eval "db.runCommand({ ping: 1 })"`
- Check your `.env` file has the correct `MONGODB_URI`

### Python Dependencies
If you encounter issues with Playwright or Selenium:

```bash
# Install Playwright browsers
python -m playwright install
```

### Port Already in Use
- Backend (8000): Change `PORT` in `.env` or kill existing process: `lsof -ti:8000 | xargs kill`
- Frontend (3000): Change `PORT` in frontend `.env` or kill existing process: `lsof -ti:3000 | xargs kill`
