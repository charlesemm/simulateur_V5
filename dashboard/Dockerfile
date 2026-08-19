# ── Dashboard CMU — build multi-étapes ──────────────────────────────────────

# Étape 1 : compilation Vite
FROM node:22-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps || npm install --legacy-peer-deps

COPY . .

# URL de l'API injectée au BUILD (obligatoire pour Vite)
ARG VITE_API_URL=http://127.0.0.1:8000
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Étape 2 : servir les fichiers statiques
FROM nginx:1.27-alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]