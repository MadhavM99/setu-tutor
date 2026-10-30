# Setu web app. Build: docker build -t setu .   Run: docker run -p 8501:8501 -v setu-data:/data setu
# Optional model server for Raju's lines: add -e GEMINI_API_KEY=<key>  (or -e SETU_LLM_URL=http://<gpu-box>:8000/v1 -e SETU_LLM_API_KEY=<secret>)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV SETU_STORE=/data/runs
VOLUME /data
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
