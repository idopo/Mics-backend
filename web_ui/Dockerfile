# Stage 1: build React SPA
FROM node:20-slim AS react-build
WORKDIR /app
COPY react-src/package*.json ./
RUN npm install
COPY react-src/ ./
RUN npm run build

# Stage 2: Python app
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=react-build /app/dist/ ./static/react/
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
