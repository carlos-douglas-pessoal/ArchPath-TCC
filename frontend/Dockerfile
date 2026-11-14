FROM node:24-bookworm-slim

ENV NODE_ENV=development

WORKDIR /app

COPY --chown=node:node package.json package-lock.json ./
RUN chown node:node /app

USER node

RUN npm ci

COPY --chown=node:node . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
