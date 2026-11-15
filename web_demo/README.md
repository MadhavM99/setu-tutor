SETU web app (frontend + backend) for Netlify
- index.html                     the app
- netlify/functions/api.mjs      backend: /api/signup /api/login /api/me /api/progress /api/calls /api/raju /api/health
- storage: Netlify Blobs (automatic, no database setup)
Env vars (Site configuration > Environment variables):
  LLM_API_KEY   required for Raju AI (e.g. Groq key)
  LLM_URL       optional, default https://api.groq.com/openai/v1
  LLM_MODEL     optional, default llama-3.3-70b-versatile
  SESSION_SECRET optional, any long random string
Deploy: drag this folder onto Netlify > Deploys, or: npx netlify-cli deploy --prod --dir . --functions netlify/functions
