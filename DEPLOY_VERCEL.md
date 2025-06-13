# 🚀 Vercel Deployment Guide

## Quick Deploy to Vercel

### Step 1: Install Vercel CLI
```bash
npm install -g vercel
```

### Step 2: Login to Vercel
```bash
vercel login
```

### Step 3: Deploy Your API
```bash
# From your project directory
vercel

# Follow the prompts:
# - Set up and deploy? → Yes
# - Which scope? → Select your account
# - Link to existing project? → No
# - Project name? → real-estate-api (or your preferred name)
# - Directory? → ./ (current directory)
```

### Step 4: Add Environment Variables
```bash
# Add your Census API key
vercel env add CENSUS_API_KEY

# When prompted, enter your Census API key
# You can get one free at: https://api.census.gov/data/key_signup.html
```

### Step 5: Redeploy with Environment Variables
```bash
vercel --prod
```

## 🎯 Your API will be live at:
`https://your-project-name.vercel.app`

## 📝 Update OpenAPI Spec
After deployment, update your `openapi.yaml`:
```yaml
servers:
  - url: https://your-project-name.vercel.app
    description: Vercel Production Server
```

## 🔧 Vercel Advantages for APIs:
- ✅ **Free Tier**: Unlimited deployments, 100GB bandwidth
- ✅ **Global CDN**: Fast response times worldwide
- ✅ **Auto-scaling**: Handles traffic spikes automatically
- ✅ **Easy deployment**: Git integration, automatic deploys
- ✅ **Environment variables**: Secure configuration management

## 🚨 Important Notes:
- **Cold Starts**: First request may be slower (1-2 seconds)
- **Function Limits**: 10-second timeout for free tier
- **Memory**: 1024MB RAM limit for free tier

## 📊 Monitoring:
- Check your Vercel dashboard for:
  - Function execution times
  - Error rates
  - Bandwidth usage
  - Deployment status

## 🔄 Continuous Deployment:
Push to your GitHub repo and Vercel will automatically deploy:
```bash
git add .
git commit -m "Update API"
git push origin main
```

Your API will be automatically deployed and available at your Vercel URL! 