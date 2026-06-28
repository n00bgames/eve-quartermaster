FROM node:22-alpine

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend ./
COPY static ../static
CMD ["npm", "run", "dev", "--", "--port", "5173"]
