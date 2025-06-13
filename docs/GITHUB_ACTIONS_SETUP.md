# 🔄 GitHub Actions + Vercel Setup Guide

## Prerequisites
1. GitHub repository created
2. Vercel account and project set up
3. Vercel CLI installed locally

## Step 1: Get Vercel Tokens

### Get Vercel Token
1. Go to [Vercel Dashboard](https://vercel.com/account/tokens)
2. Click "Create Token"
3. Name it "GitHub Actions"
4. Copy the token (you'll need this for GitHub secrets)

### Get Project IDs
Run these commands locally:
```bash
# Login to Vercel
vercel login

# Link your project (if not already linked)
vercel link

# Get your project info
vercel project ls
```

Note down:
- **Project ID** (looks like: `prj_abc123...`)
- **Org ID** (looks like: `team_abc123...` or your username)

## Step 2: Add GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add these secrets:

| Secret Name | Value |
|-------------|-------|
| `VERCEL_TOKEN` | Your Vercel token from Step 1 |
| `VERCEL_ORG_ID` | Your Vercel organization ID |
| `VERCEL_PROJECT_ID` | Your Vercel project ID |

## Step 3: Test the Workflow

1. Push your code to GitHub:
```bash
git add .
git commit -m "Add GitHub Actions workflow"
git push origin main
```

2. Check the Actions tab in your GitHub repository
3. You should see the deployment workflow running

## Step 4: Verify Deployment

- **Production**: Automatically deploys on push to `main`/`master`
- **Preview**: Automatically deploys on pull requests
- Check your Vercel dashboard for deployment status

## 🔧 Workflow Features

### ✅ What the workflow does:
- **Automatic deployment** on every push to main/master
- **Preview deployments** for pull requests
- **PR comments** with preview URLs
- **Latest action versions** (checkout v4, setup-node v4, etc.)

### 🎯 Deployment Triggers:
- **Push to main/master** → Production deployment
- **Pull Request** → Preview deployment
- **Manual trigger** → Available in Actions tab

### 📊 Monitoring:
- Check **Actions** tab in GitHub for workflow status
- Check **Vercel Dashboard** for deployment status
- Preview URLs automatically posted to PRs

## 🚨 Troubleshooting

### Common Issues:

**1. "Vercel token not found"**
- Make sure you added `VERCEL_TOKEN` to GitHub secrets
- Verify the token is valid in Vercel dashboard

**2. "Project not found"**
- Check `VERCEL_PROJECT_ID` is correct
- Run `vercel project ls` to get the right ID

**3. "Organization not found"**
- Check `VERCEL_ORG_ID` is correct
- Use your username if it's a personal project

**4. Workflow not triggering**
- Make sure you're pushing to `main` or `master` branch
- Check the workflow file is in `.github/workflows/`

## 🔄 Manual Deployment

If you need to deploy manually:
```bash
# Deploy to production
vercel --prod

# Deploy preview
vercel
```

## 📝 Next Steps

After setup:
1. **Test the workflow** with a small change
2. **Update your OpenAPI spec** with the production URL
3. **Submit to RapidAPI** with your Vercel URL
4. **Monitor deployments** in both GitHub and Vercel

Your API will now automatically deploy to Vercel on every commit! 🚀 