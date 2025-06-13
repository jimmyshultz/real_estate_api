# 🚀 Deployment Guide

## Quick Deploy Options

### Vercel (Recommended - Free)
See [DEPLOY_VERCEL.md](../DEPLOY_VERCEL.md) for detailed instructions.

### GitHub Actions Setup
See [GITHUB_ACTIONS_SETUP.md](../GITHUB_ACTIONS_SETUP.md) for automated deployment.

## Environment Setup

1. **Copy environment template**:
   ```bash
   cp env.example .env
   ```

2. **Get your Census API key**:
   - Visit: https://api.census.gov/data/key_signup.html
   - Add your key to `.env`

3. **For Vercel deployment**:
   - Get Vercel tokens from dashboard
   - Add to GitHub secrets (see GITHUB_ACTIONS_SETUP.md)

## Security Notes

- Never commit `.env` files
- Use GitHub secrets for production tokens
- Database files are auto-generated and ignored
- API keys are protected by `.gitignore` 